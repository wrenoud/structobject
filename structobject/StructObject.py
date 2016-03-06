import inspect
import types
import struct

from .StructField import *

try:
    from .compatibility import with_metaclass, string_types
except:
    from compatibility import with_metaclass, string_types

native = b'='
little_endian = b'<'
big_endian = b'>'
network = b'!'


def field_list(parent_field, name, parents=[]):
    unpack_field_list = ''
    pack_field_list = ''

    local_parents = parents + [name]

    for field_name in parent_field._field_order:
        field = parent_field.__class__.__dict__[field_name]

        if issubclass(field.__class__, StructFieldBase):
            unpack_field_list += "self._values['{}']['{}'], ".format("']['".join(parent for parent in local_parents),field_name)
            pack_field_list += "self._values['{}']['{}'], ".format("']['".join(parent for parent in local_parents),field_name)

        if issubclass(field.__class__, StructObjectBase):
            _unpack, _pack = field_list(field, field_name, local_parents)

            unpack_field_list += _unpack
            pack_field_list += _pack

    return unpack_field_list, pack_field_list


class StructObjectMeta(type):
    def __new__(mcs, class_name, class_bases, class_attr):
        if class_name == "StructObjectBase":
            # we don't need to do anything to the abstract super class, so skip this
            return type.__new__(mcs, class_name, class_bases, class_attr)
        else:
            if len(class_bases) > 1:
                raise Exception("Multiple super classes not implemented")
            _base = class_bases[0]

            is_subclass_of_base = _base == StructObjectBase

            # get the field order, either from parent class, or inferred if descendant of base
            if not is_subclass_of_base:
                # superclass order assumed as subclass order
                class_attr['_field_order'] = _base._field_order
            else:
                # we'll need to infer the field order ourself
                fields = []
                for key, attr in class_attr.items():
                    if issubclass(attr.__class__, StructBase):
                        fields.append((key, attr._id))
                # sort by id
                fields = sorted(fields, key=lambda item: item[1])
                # grab names
                class_attr['_field_order'] = [item[0] for item in fields]

            # set names for child class fields
            for key, val in class_attr.items():
                if issubclass(class_attr[key].__class__, StructBase):
                    class_attr[key]._name = key

            # migrate any superclass fields into subclass
            if not is_subclass_of_base:
                for key in class_attr['_field_order']:
                    if key not in class_attr:
                        class_attr[key] = _base.__dict__[key]

            # ensure attributes are included in _field_order
            for key, val in class_attr.items():
                # ignore private attributes (prefixed with '_') and
                # class methods (they're functions until we call type())
                if not (key.startswith('_') or inspect.isfunction(val) or (issubclass(class_attr[key].__class__, StructBase) and key in class_attr['_field_order'])):
                    raise Exception("Class attribute '{}' is not not a sublass of StructBase, it's order cannot be determined.".format(key))

            # default byte order uses native with standard sizes and no alignment
            if '_byte_order' not in class_attr and is_subclass_of_base:
                class_attr['_byte_order'] = native
            elif '_byte_order' not in class_attr:
                class_attr['_byte_order'] = _base._byte_order

            # check if all attributes are flat, we set a struct format string if they are
            class_attr['_flat'] = True
            class_attr['_partial_class'] = False
            class_attr['_non_field'] = []
            for key in class_attr['_field_order']:
                if isinstance(class_attr[key], none):
                    class_attr['_partial_class'] = True
                elif not class_attr[key].flat():
                    class_attr['_flat'] = False

                if not issubclass(class_attr[key].__class__, StructFieldBase):
                    class_attr['_non_field'].append(key)

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

                    if isinstance(field, none):
                        continue
                    elif issubclass(field.__class__, StructFieldBase):
                        partial_struct += field.format
                        unpack_field_list += "self._values['{}'], ".format(key)
                        pack_field_list += "self._values['{}'], ".format(key)
                    elif issubclass(field.__class__, StructObjectBase) and field.flat() and field._byte_order == class_attr['_byte_order']:
                        # build up list of child fields
                        _unpack, _pack  = field_list(field, key)
                        unpack_field_list += _unpack
                        pack_field_list += _pack

                        partial_struct += field._structs[0].format[1:] # trim byte order
                    else:
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



                if len(partial_struct) > 1:
                    struct_idx = len(class_attr['_structs'])
                    class_attr['_structs'].append(struct.Struct(partial_struct))

                    unpack_func += '\t' + unpack_field_list + ' = self._structs[{0}].unpack_from(data, offset)\n'.format(struct_idx)
                    #unpack_func += '\toffset += sz\n'

                    pack_func += '\n\tdata += self._structs[{}].pack({})\n'.format(struct_idx, pack_field_list[:-2])

                pack_func += '\treturn data\n'
    
                class_attr['unpack_func_string'] = unpack_func
                class_attr['pack_func_string'] = pack_func

                print (unpack_func)
                print (pack_func)

                exec(unpack_func, globals(), class_attr)
                exec(pack_func, globals(), class_attr)

            cls = type.__new__(mcs, class_name, class_bases, class_attr)

            return cls


class StructObjectBase(with_metaclass(StructObjectMeta, StructBase)):
    _structs = []
    _field_order = ()
    _partial_class = False
    _flat = True

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
        self = super(StructObjectBase, cls).__new__(cls)
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

        for field_name in self._non_field:
            self.__setattr__(field_name, None)

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
            if self._name not in parent._values:
                # hasn't been initialized in parent, set all values to none
                # self.__set__(parent, None)
                parent._values[self._name] = {}
            self._values = parent._values[self._name]
        return self

    def __set__(self, parent, value):
        # create empty dict in parent
        if value is None:
            parent._values[self._name] = {}
            for field_name in self._non_field:
                self.__setattr__(field_name, None)

        elif issubclass(value.__class__, self.__class__):
            # copy pointer to outside values
            parent._values[self._name] = value._values
        else:
            # find my name to tell user
            name = ''
            for key in parent._field_order:
                if parent.__class__.__dict__[key]._name == self._name:
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
            raise Exception("Unrecognized index: {} ({})".format(key, type(key)))

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
                if issubclass(field.__class__, StructFieldBase):
                    result.append(field.__get__(self, self.__class__))
                elif issubclass(field.__class__, StructObjectBase):
                    result.append(field)
            return result
        else:
            raise KeyError("Unrecognized index: {} ({})".format(key, type(key)))

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

    def unpack_from(self, bindata, offset=0):
        self._unpack_from(bindata, offset)

    def pack(self):
        return self._pack()

    def _pack_pack(self):
        data = b''

        data += self._structs[0].pack(self._values['x'], self._values['y'])
        return data

    def field_instance(self, field_name):
        return self.__class__.__dict__[field_name]

    def unprep(self):
        for field_name in self._field_order:
            field = self.__class__.__dict__[field_name]
            if issubclass(field.__class__, StructFieldBase) and field._getters is not None:
                field.unprep(self)
            elif issubclass(field.__class__, StructObjectBase):
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

    def flat(self):
        return self._flat




if __name__ == '__main__':

    if False:
        import timeit

        class test(StructObjectBase):
            _field_order = ('field1', 'field2')
            field1 = ctype_int()
            field2 = ctype_int()

        class test2(StructObjectBase):
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

