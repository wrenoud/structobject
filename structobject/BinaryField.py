import inspect
import struct

try:
    from .compatibility import with_metaclass, string_types
except:
    from compatibility import with_metaclass, string_types

native = b'='
little_endian = b'<'
big_endian = b'>'
network = b'!'


class virtual(object):
    def __init__(self, func=None):
        self.func = func

    def __get__(self):
        if self.func is not None:
            raise Exception(
                "Trying to call virtual method, {} must be implemented in a subclass".format(self.func.__name__))
        else:
            raise Exception("Trying to access virtual object, object must be defined in a subclass")


class BinaryBase(object):
    """Descriptor class used for modeling a binary field or a fixed array of fields
    
    Any instance that is intended to contain a single value should be assigned i.e.

        class MyFieldClass(BinaryField):
            _format = "<B"

        class MyBinaryStructure(BinaryField):
            field1 = MyFieldClass()
            field2 = MyFieldClass()
            

    """

    _generator = None
    _python_type = None
    _partial_class = False
    _flat = True

    @virtual
    def __get__(self, parent, parent_type=None):
        pass

    @virtual
    def __set__(self, parent, value):
        pass

    def flat(self):
        return self._flat

    @virtual
    def pack(self, parent=None):
       pass

    @virtual
    def unpack(self, bindata, parent=None):
        pass


class BinaryFieldBase(BinaryBase):
    """
    Acts as a descriptor class for a class attribute in a BinaryObjectBase
    """
    _format = virtual()  # a struct Format String, see https://docs.python.org/3.5/library/struct.html#format-strings

    def AddSetter(self, func):
        if self._setters is None:
            self._setters = []
        self._setters.append(func)

    def AddGetter(self, func):
        if self._getters is None:
            self._getters = []
        self._getters.append(func)

    def AddValidator(self, func):
        if self._validators is None:
            self._validators = []
        self._validators.append(func)

    def __init__(self, default=None, getter=None, setter=None, value=None):
        self._structs = [struct.Struct(self._format)]
        self._default = None
        self._setters = None
        self._getters = None
        self._validators = None

        if default is not None: self._default = default
        if getter is not None: self.AddGetter(getter)
        if setter is not None: self.AddSetter(setter)
        if value is not None:
            self._default = value

            def match_value(x):
                return x == value

            self.AddValidator(match_value)

    def __get__(self, parent, parent_type=None):
        if parent is None:
            return self
        elif id(self) in parent._values:
            return parent._values[id(self)]

    def __set__(self, parent, value):
        if value is None:
            parent._values[id(self)] = self._default
        else:
            if self._validators is not None:
                self.validate(value)
            parent._values[id(self)] = value

    def validate(self, value):
        if self._validators is not None:
            for validator in self._validators:
                if not validator(value):
                    raise Exception("Failed validator: {} with value {}".format(validator.__name__, value))

    def prep(self, parent):
        """Runs Setters on value to prepare for serialization

        Args:
            parent: the parent object so the descriptor can look up the value
        """
        _tmp = self.__get__(parent)
        if self._setters is not None:
            for setter in self._setters:
                _tmp = setter(_tmp)
        return _tmp

    def unprep(self, parent):
        """Runs Getters on deserialized value

        Args:
            parent: the parent object so the descriptor can look up and set value
        """
        if self._getters is not None:
            _tmp = self.__get__(parent)
            for getter in self._getters:
                _tmp = getter(_tmp)
            self.__set__(parent, _tmp)

    @property
    def size(self):
        return self._structs[0].size


def field_list(parent_field, name, parent ='self'):
    unpack_field_list = ''
    pack_field_list = ''

    address = '{}.{}'.format(parent, name)

    for field_name in parent_field._field_order:
        field = parent_field.__class__.__dict__[field_name]

        if issubclass(field.__class__, BinaryFieldBase):
            unpack_field_list += "{0}.{1}, ".format(address, field_name)
            pack_field_list += "{0}.__class__.__dict__['{1}'].prep({0}), ".format(address, field_name)

        if issubclass(field.__class__, BinaryObjectBase):
            _unpack, _pack = field_list(field, field_name, address)

            unpack_field_list += _unpack
            pack_field_list += _pack

    return unpack_field_list, pack_field_list


class BinaryObjectMeta(type):
    def __new__(mcs, class_name, class_bases, class_attr):
        if class_name == "BinaryObjectBase":
            # we don't need to do anything to the abstract super class, so skip this
            return type.__new__(mcs, class_name, class_bases, class_attr)
        else:
            if len(class_bases) > 1:
                raise Exception("Multiple super classes not implemented")
            _base = class_bases[0]

            is_subclass_of_base = _base == BinaryObjectBase

            # ensure _field_order is defined, and only once per subclass tree
            if '_field_order' in class_attr and not is_subclass_of_base:
                raise Exception("Only subclasses of BinaryObjectBase may define '_field_order' attribute")
            elif '_field_order' not in class_attr and is_subclass_of_base:
                raise Exception("Subclasses that extend BinaryObjectBase must define class attribute '_field_order'")
            elif '_field_order' not in class_attr:
                # superclass order assumed as subclass order
                class_attr['_field_order'] = _base._field_order

            # migrate any superclass fields into subclass
            if not is_subclass_of_base:
                for key in class_attr['_field_order']:
                    if key not in class_attr:
                        class_attr[key] = _base.__dict__[key]

            # ensure attributes are included in _field_order
            for key, val in class_attr.items():
                # ignore private attributes (prefixed with '_') and
                # class methods (they're functions until we call type())
                if not (key.startswith('_') or inspect.isfunction(val) or not (key not in class_attr['_field_order'])):
                    raise Exception("Attribute '{}' not included in '_field_order'".format(key))

            # default byte order uses native with standard sizes and no alignment
            if '_byte_order' not in class_attr and is_subclass_of_base:
                class_attr['_byte_order'] = native
            elif '_byte_order' not in class_attr:
                class_attr['_byte_order'] = _base._byte_order

            # check if all attributes are flat, we set a struct format string if they are
            class_attr['_flat'] = True
            class_attr['_partial_class'] = False
            for key in class_attr['_field_order']:
                if class_attr[key] is None:
                    class_attr['_partial_class'] = True
                elif not class_attr[key].flat():
                    class_attr['_flat'] = False
                    break

            if not class_attr['_partial_class']:
                # create unpack function
                class_attr['_structs'] = []
                unpack_func = 'def _unpack_from(self, data, offset = 0):\n'
                pack_func = 'def _pack(self):\n\tdata = b\'\'\n'

                partial_struct = class_attr['_byte_order']
                unpack_field_list = ''
                pack_field_list = ''
                partial_idx = 0
                for i,key in enumerate(class_attr['_field_order']):
                    field = class_attr[key]

                    if field is None:
                        continue
                    elif issubclass(field.__class__, BinaryFieldBase):
                        partial_struct += field._format
                        unpack_field_list += "self.{}, ".format(key)
                        pack_field_list += "self.__class__.__dict__['{}'].prep(self), ".format(key)
                    elif issubclass(field.__class__, BinaryObjectBase) and field.flat() and field._byte_order == class_attr['_byte_order']:
                        # build up list of child fields
                        _unpack, _pack  = field_list(field, key)
                        unpack_field_list += _unpack
                        pack_field_list += _pack

                        partial_struct += field._structs[0].format[1:] # trim byte order
                    elif issubclass(field.__class__, BinaryObjectBase) and (not field.flat() or field._byte_order != class_attr['_byte_order']):
                        if len(partial_struct) > 1:
                            struct_idx = len(class_attr['_structs'])
                            class_attr['_structs'].append(struct.Struct(partial_struct))

                            unpack_func += '\n\tsz = self._structs[{0}].size\n'.format(struct_idx)
                            unpack_func += '\t' + unpack_field_list + ' = self._structs[{0}].unpack_from(data, offset)\n'.format(struct_idx)
                            unpack_func += '\toffset += sz\n'

                            pack_func += '\n\tdata += self._structs[{}].pack({})\n'.format(struct_idx, pack_field_list[:-2])

                            partial_struct = class_attr['_byte_order']
                            unpack_field_list = ''
                            partial_idx = i

                        # ask the child to unpack itself
                        unpack_func += '\n\tself.{}._unpack_from(data, offset)\n'.format(key)
                        unpack_func += '\toffset += self.{}.size\n'.format(key)

                        # ask the child to pack itself
                        pack_func += '\n\tdata += self.{}._pack()\n'.format(key)
                    else:
                        print (field)
                        print (field.__class__)
                        print (field.__dict__)


                if len(partial_struct) > 1:
                    struct_idx = len(class_attr['_structs'])
                    class_attr['_structs'].append(struct.Struct(partial_struct))

                    unpack_func += '\t' + unpack_field_list + ' = self._structs[{0}].unpack_from(data, offset)\n'.format(struct_idx)
                    #unpack_func += '\toffset += sz\n'


                    pack_func += '\n\tdata += self._structs[{}].pack({})\n'.format(struct_idx, pack_field_list[:-2])

                pack_func += '\treturn data\n'
    
                class_attr['unpack_func_string'] = unpack_func
                class_attr['pack_func_string'] = pack_func

                exec(unpack_func, globals(), class_attr)
                exec(pack_func, globals(), class_attr)

            cls = type.__new__(mcs, class_name, class_bases, class_attr)

            return cls


class BinaryObjectBase(with_metaclass(BinaryObjectMeta, BinaryBase)):
    _structs = []
    _field_order = ()

    def AddSetter(self, func, field_name):
        if field_name in self._field_order:
            self.__class__.__dict__[field_name].AddSetter(func)
        else:
            raise AttributeError("{} is not an attribute of {}".format(field_name, self.__class__.__name__))

    def AddGetter(self, func, field_name):
        if field_name in self._field_order:
            self.__class__.__dict__[field_name].AddSetter(func)
        else:
            raise AttributeError("{} is not an attribute of {}".format(field_name, self.__class__.__name__))

    def AddValidator(self, func, field_name):
        if field_name in self._field_order:
            self.__class__.__dict__[field_name].AddSetter(func)
        else:
            raise AttributeError("{} is not an attribute of {}".format(field_name, self.__class__.__name__))

    def flat(self):
        return len(self._structs) == 1

    def __new__(cls, *args, **kargs):
        self = super(BinaryObjectBase, cls).__new__(cls)
        self._values = {}  # have to set this before init
        return self

    def __init__(self, *args, **kargs):
        if self._partial_class:
            raise NotImplementedError('{} has NoneType fields that must be implemented in a subclass'.format(self.__class__.__name__))

        # handle special cases where list or dict used
        if len(args) == 1 and isinstance(args[0], (list, tuple)):
            args = args[0]
        elif len(args) == 1 and isinstance(args[0],dict):
            kargs = args[0]
            args=[]

        # check for binary data
        if len(args) == 1 and isinstance(args[0], string_types + (memoryview,)):
            self.unpack(args[0])
        elif len(args) > 0 or len(kargs) > 0:
            for i, field_name in enumerate(self._field_order):
                # assign order parameter and defaults for remainder
                if i < len(args):
                    self.__setattr__(field_name, args[i])
            if len(kargs) > 0:
                self.update(kargs)

    def __get__(self, parent, parent_type=None):
        if parent is not None:
            # kansas city shuffle
            # retrieve values from parent, for now we'll masquerade as this parent's child
            if id(self) not in parent._values:
                # hasn't been initialized in parent, set all values to none
                # self.__set__(parent, None)
                parent._values[id(self)] = {}
            self._values = parent._values[id(self)]
        return self

    def __set__(self, parent, value):
        # create empty dict in parent
        if issubclass(value.__class__, self.__class__):
            # copy pointer to outside values
            parent._values[id(self)] = value._values
        else:
            # find my name to tell user
            name = ''
            for key in parent._field_order:
                if id(parent.__class__.__dict__[key]) == id(self):
                    name = key
                    break
            raise TypeError("'{}' must be of type '{}', given '{}'".format(name, self.__class__.__name__, value.__class__.__name__))

    def __setitem__(self, key, value):
        if isinstance(key, string_types):
            if '.' in key:
                field_names = key.split('.')
                obj = self.__getattribute__(field_names[0])
                for field_name in field_names[1:-1]:
                    obj = obj.__getattribute__(field_name)
                obj.__setattr__(field_names[-1], value)
            else:
                self.__setattr__(key, value)
        elif isinstance(key, int):
            if key < len(self._field_order):
                self.__setattr__(self._field_order[key], value)
            else:
                raise IndexError("Index: {} not in object".format(key))
        elif isinstance(key, slice):
            field_names = self._field_order[key]
            for i, field_name in enumerate(field_names):
                self.__setattr__(field_name, value[i])
        else:
            raise Exception("Unrecognized index: {}".format(key))

    def __getitem__(self, key):
        if isinstance(key, string_types):
            if '.' in key:
                _field_names = key.split('.')
                obj = self.__getattribute__(_field_names[0])
                for _field_name in _field_names[1:]:
                    obj = obj.__getattribute__(_field_name)
                return obj
            else:
                return self.__getattribute__(key)
        elif isinstance(key, int):
            if key < len(self._field_order):
                return self.__getattribute__(self._field_order[key])
            else:
                raise IndexError("Index: {} not in object".format(key))
        elif isinstance(key, slice):
            result = []
            for field_name in self._field_order[key]:
                field = self.__class__.__dict__[field_name]
                if issubclass(field.__class__, BinaryFieldBase):
                    result.append(field.__get__(self, self.__class__))
                elif issubclass(field.__class__, BinaryObjectBase):
                    result.append(field)
            return result
        else:
            raise KeyError("Unrecognized key: {}".format(key))

    def __len__(self):
        return len(self._field_order)

    @property
    def size(self):
        sz = 0
        if self.flat():
            sz = self._structs[0].size
        else:
            for key in self._field_order:
                sz += self.__class__.__dict__[key].size()
        return sz

    def keys(self):
        return self._field_order

    def values(self):
        values = []
        for key in self._field_order:
            values.append(self.__getattribute__(key))
        return values

    def items(self):
        return zip(self._field_order, self.values())

    def unpack(self, bindata, alt=False):
        self._unpack_from(memoryview(bindata))
        self.unprep()

    def unpack_from(self, bindata, offset = 0):
        self._unpack_from(bindata, offset)
        self.unprep()

    def pack(self):
        return self._pack()

    def field_instance(self, field_name):
        return self.__class__.__dict__[field_name]

    def unprep(self):
        for field_name in self._field_order:
            field = self.__class__.__dict__[field_name]
            if issubclass(field.__class__, BinaryFieldBase) and field._getters is not None:
                field.unprep(self)
            elif issubclass(field.__class__, BinaryObjectBase):
                field.unprep()
            else:
                pass

    def update(self, *args, **kargs):
        "Same functionality as dict.update(). "
        # if unnamed parameters used lets update the kargs and work from there
        if len(args) == 1:
            if isinstance(args[0], dict):
                # named parameters take precedence
                _tmp = args[0]
                _tmp.update(kargs)
                kargs = args[0]
            elif isinstance(args[0], (list, tuple)):
                # named parameters take precedence
                _tmp = dict(args[0])
                _tmp.update(kargs)
                kargs = _tmp
            else:
                raise TypeError("parameter type '{}' not supported by update".format(args[0].__class__.__name__))
        elif len(args) > 1:
            raise TypeError('update expected at most 1 arguments, got {}'.format(len(args)))

        for key, value in kargs.items():
            self.__setattr__(key,value)

class ctype_pad(BinaryFieldBase):
    """padding byte"""
    _format = b'x'
    _python_type = str


class ctype_char(BinaryFieldBase):
    """string of length 1"""
    _format = b'c'
    _python_type = str


class ctype_schar(BinaryFieldBase):
    """signed char"""
    _format = b'b'
    _python_type = int


class ctype_uchar(BinaryFieldBase):
    """unsigned char"""
    _format = b'B'
    _python_type = int


class ctype_bool(BinaryFieldBase):
    """boolean value"""
    _format = b'?'
    _python_type = bool


class ctype_short(BinaryFieldBase):
    """short"""
    _format = b'h'
    _python_type = int


class ctype_ushort(BinaryFieldBase):
    """unsigned short"""
    _format = b'H'
    _python_type = int


class ctype_int(BinaryFieldBase):
    """signed integer"""
    _format = b'i'
    _python_type = int


class ctype_uint(BinaryFieldBase):
    """unsigned integer"""
    _format = b'I'
    _python_type = int


class ctype_long(BinaryFieldBase):
    """signed long"""
    _format = b'l'
    _python_type = int


class ctype_ulong(BinaryFieldBase):
    """unsigned long"""
    _format = b'L'
    _python_type = int


class ctype_double(BinaryFieldBase):
    """double"""
    _format = b'd'
    _python_type = float


class ctype_float(BinaryFieldBase):
    """float"""
    _format = b'f'
    _python_type = float


if __name__ == '__main__':

    if False:
        import timeit

        class test(BinaryObjectBase):
            _field_order = ('field1', 'field2')
            field1 = ctype_int()
            field2 = ctype_int()

        class test2(BinaryObjectBase):
            _field_order = ('base', 'field3')
            base = test()
            field3 = ctype_int()

        t = test()
        t.field1 = 3
        t.field2 = 4
        print(t.keys(), t.values())


        tt = test2()
        tt2 = test2()
        tt.base.field2 = 1000
        print(tt.base.field2, tt2.base.field2)
        tt2.base.field2 = 2000
        print(tt.base.field2, tt2.base.field2)
        tt2.base = t
        print(tt.base.field2, tt2.base.field2)
        t.field2 = 5
        print(tt.base.field2, tt2.base.field2)

        class container(object):
            def __init__(self):
                self.t = test()
                self.t.field1 = 1
        c = container()

        print(c.t.field1)

        t = test(2,1)
        print (t.values())

        t = test()
        t.update([('field1',1),('field2',3)])
        print (t.values())

        #print(t.pack())

        t.unpack(b'\x01\x00\x00\x00\x03\x00\x00\x00')
        print(t.values())

        print(timeit.timeit("t.unpack(b'\\x01\\x00\\x00\\x00\\x03\\x00\\x00\\x00', True)", setup="from __main__ import t", number=1000))
        print(timeit.timeit("t.unpack(b'\\x01\\x00\\x00\\x00\\x03\\x00\\x00\\x00', False)", setup="from __main__ import t", number=1000))

        t2 = test()
        t2.unpack(b'\x01\x00\x00\x00\x03\x00\x00\x00', True)
        print(t2.values())


    import sys
    import unittest
    import struct
    import calendar
    import time

    class Point(BinaryObjectBase):
        "Basic point class"
        _field_order = ('x','y')
        x = ctype_double()
        y = ctype_double()

    class Point3D(BinaryObjectBase):
        "Basic point class"
        _field_order = ('x','y','z')
        x = ctype_double()
        y = ctype_double()
        z = ctype_double()

    class BoundingBox(BinaryObjectBase):
        _field_order = ('northwest','southeast')
        northwest = Point()
        southeast = Point()


    class BinaryObjectBaseTests(unittest.TestCase):
        # if length is specified it should be an array or 's'
        def testOrder(self):
            # exception should be raised if '_order' not defined in subclass
            # exception should be raise if '_order' defined in subclass that isn't first decendant of BinaryObjectBase
            pass

        def testInitSetByAttribute(self):
            p = Point()
            self.assertEqual(list(p.items()),[('x', None), ('y', None)])
            p.x = 5000.0
            p.y = 300.5
            self.assertEqual(list(p.items()),[('x', 5000.0), ('y', 300.5)])

        def testInitImplicitOrder(self):
            p = Point(5000.0, 300.5)
            self.assertEqual(list(p.items()),[('x', 5000.0), ('y', 300.5)])

        def testInitExplicitNames(self):
            p = Point(y=300.5, x=5000.0)
            self.assertEqual(list(p.items()),[('x', 5000.0), ('y', 300.5)])

        def testInitMixedOrdering(self):
            p = Point(5000.0, y=300.5)
            self.assertEqual(list(p.items()),[('x', 5000.0), ('y', 300.5)])

        def testInitImplicitList(self):
            p = Point((5000.0, 300.5))
            self.assertEqual(list(p.items()),[('x', 5000.0), ('y', 300.5)])

        def testInitExplicitDict(self):
            p = Point({'x': 5000.0, 'y': 300.5})
            self.assertEqual(list(p.items()),[('x', 5000.0), ('y', 300.5)])

        def testPack(self):
            p = Point(5000.0, 300.5)
            self.assertEqual(p.pack(), struct.pack('dd', 5000.0, 300.5))

        def testPackWithSubstructure(self):
            bb = BoundingBox(Point(0.0, 10.0), southeast=Point(15.0, 0.0))
            self.assertEqual(bb.pack(), struct.pack(b'dddd', 0.0, 10.0, 15.0, 0.0))

        def testPackWithSetter(self):
            field = ctype_uint(
                setter=calendar.timegm,
                getter=time.gmtime
            )
            class Generic(BinaryObjectBase):
                _field_order = ('timestamp',)
                timestamp = field

            t = Generic(timestamp=time.gmtime(100))
            self.assertEqual(t.pack(), struct.pack('I', 100))

        def testUnpackWithGetter(self):
            field = ctype_uint(
                setter=calendar.timegm,
                getter=time.gmtime
            )
            class Generic(BinaryObjectBase):
                _field_order = ('timestamp',)
                timestamp = field

            t = Generic(struct.pack('I', 100))
            self.assertEqual(t.timestamp, time.gmtime(100))

        def testGetItemWithString(self):
            bb = BoundingBox(Point(0.0, 10.0), southeast=Point(15.0, 0.0))
            self.assertEqual(bb['northwest.y'], 10.0)
            self.assertEqual(bb.northwest['y'], 10.0)

        def testGetItemWithInt(self):
            p = Point(5000.0, 300.5)
            self.assertEqual(p[1], 300.5)
            self.assertRaises(IndexError, p.__getitem__, 3)

        def testGetItemWithSlice(self):
            p = Point(5000.0, 300.5)
            self.assertEqual(p[:], [5000.0, 300.5])
            self.assertEqual(p[:1], [5000.0])
            self.assertEqual(p[1:], [300.5])

        def testGetItemWithObj(self):
            p = Point(5000.0, 300.5)
            self.assertRaises(Exception, p.__getitem__, int)

        def testSetItemWithString(self):
            bb = BoundingBox()
            bb['northwest.y'] = 15.0
            self.assertEqual(bb.northwest.y, 15.0)
            bb.northwest['y'] = 20.0
            self.assertEqual(bb.northwest.y, 20.0)

        def testSetItemWithInt(self):
            p = Point()
            p[1] = 300.5
            self.assertEqual(p.y, 300.5)
            self.assertRaises(IndexError, p.__setitem__, 3, 500.0)

        def testSetItemWithSlice(self):
            p = Point()
            p[:] = [5000.0, 300.5]
            self.assertEqual(p.values(), [5000.0, 300.5])
            p[:1] = [5000.0]
            self.assertEqual(p.x, 5000.0)
            p[1:] = [300.5]
            self.assertEqual(p.y, 300.5)

        def testSetItemWithObj(self):
            p = Point()
            self.assertRaises(Exception, p.__setitem__, int)

        def testOverloading(self):
            class GenericBoundingBox(BinaryObjectBase):
                _field_order = ('northwest','southeast')
                northwest = None
                southeast = None

            class BoundingBox3D(GenericBoundingBox):
                northwest = Point3D()
                southeast = Point3D()

            bb = BoundingBox3D(Point3D(10.0,20.0,30.0))
            self.assertEqual(bb.northwest.z, 30.0)

        def testOverloadingNotImplemented(self):
            class GenericBoundingBox(BinaryObjectBase):
                _field_order = ('northwest','southeast')
                northwest = None
                southeast = None
            self.assertRaises(NotImplementedError,GenericBoundingBox)

        def testInitWithWrongObjectTypeForField(self):
            self.assertRaises(TypeError, BoundingBox, Point3D())

        def testSetAttrWithWrongObjectTypeForField(self):
            bb = BoundingBox()
            p = Point3D()
            self.assertRaises(TypeError, bb.__setattr__,'northwest', p)

        def testUpdateWithDict(self):
            p = Point()
            p.update({'y':300.5,'x':5000.0})
            self.assertEqual(list(p.items()),[('x', 5000.0), ('y', 300.5)])

        def testUpdateWithList(self):
            p = Point()
            p.update([('y',300.5),('x',5000.0)])
            self.assertEqual(list(p.items()),[('x', 5000.0), ('y', 300.5)])

        def testUpdateWithNamed(self):
            p = Point()
            p.update(y=300.5,x=5000.0)
            self.assertEqual(list(p.items()),[('x', 5000.0), ('y', 300.5)])

        def testUpdateWithBoth(self):
            p = Point()
            p.update({'y':300.5},x=5000.0)
            self.assertEqual(list(p.items()),[('x', 5000.0), ('y', 300.5)])
            p.update([('y',400.5)],x=6000.0)
            self.assertEqual(list(p.items()),[('x', 6000.0), ('y', 400.5)])

        def testUpdateWithBothOrderPrecidence(self):
            p = Point()
            p.update({'x':6000.0},x=5000.0)
            self.assertEqual(p.x,5000.0)

        def testUpdateWithBadType(self):
            p = Point()
            self.assertRaises(TypeError, p.update, 5000.0)

        def testUpdateWithTooManyParameters(self):
            p = Point()
            self.assertRaisesRegex(TypeError, "update expected at most 1 arguments, got 2", p.update, 5000.0, 6000.0)

        def testSize(self):
            bb = BoundingBox()
            self.assertEqual(bb.size,32)

        def testUnpack(self):
            s = struct.pack('dddd', 0.0, 10.0, 15.0, 0.0)
            bb = BoundingBox(s)
            self.assertEqual(list(bb.northwest.items()),[('x', 0.0), ('y', 10.0)])
            self.assertEqual(list(bb.southeast.items()),[('x', 15.0), ('y', 0.0)])

        def testLen(self):
            bb = BoundingBox()
            p = Point3D()
            self.assertEqual(len(bb),2)
            self.assertEqual(len(p),3)

        def testOverloadingFixesIssue1(self):
            # covers fix #1
            class GenericDatagram(BinaryObjectBase):
                _field_order = ('STX','timestamp','body','ETX')
                STX = ctype_uchar(value=0x02)
                timestamp = ctype_uint()
                body = None
                ETX = ctype_uchar(value=0x03)

            class BoundingBoxDatagram(GenericDatagram):
                body = BoundingBox()

            bbgram = BoundingBoxDatagram(timestamp=100)
            self.assertEqual(bbgram.timestamp, 100)

        def testOverloadingWithFieldOrderRaisesException(self):
            class Generic(BinaryObjectBase):
                _field_order = ('myfield',)
                myfield = None
            with self.assertRaises(Exception):
                class Overload(Generic):
                    _field_order = ('myfield',)
                    myfield = Point

        def testNoFieldOrderRaisesException(self):
            with self.assertRaises(Exception):
                class Generic(BinaryObjectBase):
                    myfield = None

        def testSlotsWithOverloading(self):
            class BetterBoundingBox(BoundingBox):
                __slots__ = ('area',)
                def __init__(self, *args, **kargs):
                    super(BetterBoundingBox,self).__init__(*args, **kargs)

                    self.area = (self.southeast.x - self.northwest.x) * \
                                (self.northwest.y - self.southeast.y)
            bb = BetterBoundingBox(Point(0,10),Point(10,0))
            self.assertEqual(bb.area, 100)

    unittest.main()

