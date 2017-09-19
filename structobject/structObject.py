import struct
import inspect

try:
    from .compatibility import with_metaclass, string_types
    from .structField import structField
except:
    from compatibility import with_metaclass, string_types
    from structField import structField

native = '='
little_endian = '<'
big_endian = '>'
network = '!'

class metaclassFactory(type):
    """Builds the subclasses of structObject"""

    def __new__(metaclass, class_name, class_bases, class_attr):
        """Implements subclass scaffolding onto base and returns built class

        Parameters:
        metaclass - this class!!
        class_name - name of the sub class to build
        class_bases - the super classes of the class to build
        class_attr - subclass attributes (like __dict__ but for the class, not an instance)
        """

        # we don't need to do anything to the abstract super class, so skip this
        if class_name != 'structObject':
            if len(class_bases) > 1:
                raise Exception("multiple super classes not implemented")
            _base = class_bases[0]

            # make sure _field_order is defined, and only once per superclass
            if '_field_order' in class_attr and _base != structObject:
                raise Exception("Only subclasses of structObject may define '_field_order' attribute")
            elif '_field_order' not in class_attr and _base == structObject:
                raise Exception("Subclasses that extend structObject must define class attribute '_field_order'")
            elif '_field_order' not in class_attr:
                # superclass order assumed as subclass order
                class_attr['_field_order'] = _base._field_order
            _field_order = class_attr['_field_order']
            
            # update slots to include all superclass attributes
            if '__slots__' not in class_attr:
                class_attr['__slots__'] = ()
            _slots = set(class_attr['__slots__'])
            for cls in _base.__mro__:
                if cls != structObject:
                    _slots.update(getattr(cls,"__slots__",[]))
            class_attr['__slots__'] = list(_slots)
            
            # default byte order uses native with standard sizes and no alignment
            if '_byte_order' not in class_attr and _base == structObject:
                class_attr['_byte_order'] = native
            elif '_byte_order' not in class_attr:
                class_attr['_byte_order'] = _base._byte_order
            _byte_order = class_attr['_byte_order']
                
            # make sure attributes are included in _field_order
            for key, val in class_attr.items():
                # ignore private attributes and class methods (they're functions until we call type())
                if not key.startswith('_') and \
                    not (inspect.isfunction(val) or type(val).__name__ == 'cython_function_or_method') and \
                    key not in _field_order:
                        raise Exception("Attribute '{}' not included in '_field_order'".format(key))

            class_attr['_constructors'] = []
            # makes sure attribute in _field_order are defined
            for i,name in enumerate(_field_order):
                if name in ["size"]:
                    raise Exception("'{}' is a reserved attribute".format(name))
                if name not in class_attr:
                    if _base != structObject:
                        # grab from superclass if this is an overloaded subclass
                        constructor = _base._constructors[i]
                    else:
                        raise Exception("Attribute '{}' included in '_field_order' but not defined".format(name))
                else:
                    constructor = class_attr[name]
                    del(class_attr[name])
                if constructor == None:
                    class_attr['_constructors'].append(Empty)
                else:
                    class_attr['_constructors'].append(constructor)

            # compile segments
            class_attr['_segments'] = []
            fmt = _byte_order
            start = 0
            for i,name in enumerate(_field_order):
                constructor = class_attr['_constructors'][i]
                if issubclass(constructor, structField) and not constructor._variable_length:
                    fmt += constructor.fmt
                else: #if issubclass(constructor, (structObject,structArray)):
                    if len(fmt) > 1:
                        class_attr['_segments'].append(structSegment(fmt,start,i))
                        fmt = _byte_order
                    class_attr['_segments'].append(i)
                    start = i + 1
            if len(fmt) > 1:
                class_attr['_segments'].append(structSegment(fmt,start,i+1))
        return type.__new__(metaclass, class_name, class_bases, class_attr)

class structSegment(struct.Struct):
    __slots__ = ('slice')

    def __init__(self, fmt, start, end):
        super(structSegment, self).__init__(fmt)
        self.slice = slice(start, end)

def printItem(item, tab = 0):
    key = item[0]
    val = item[1]
    rep = "{}{}: ".format("\t"*tab, key)
    if isinstance(val, structArray):
        if val.object_type.__name__ == 'ctype_char':
            rep += "\"{}\"\n".format("".join([c.decode("latin-1") for c in val]))
        else:
            rep += "\n"
            for i, subitem in enumerate(val):
                if isinstance(subitem, structObject):
                    rep += "{}[{}]\n".format("\t"*(tab+1), i)
                    for subsubitem in subitem.items():
                        rep += printItem(subsubitem, tab + 2)
                else:
                    rep +="{}[{}] {}\n".format("\t"*(tab+1), i, subitem)
    elif isinstance(val, structObject):
        rep += "\n"
        for subitem in val.items():
            rep += printItem(subitem, tab + 1)
    else:
        try:
            items = val.items()
            rep += "\n"
            for subitem in items:
                rep += printItem(subitem, tab + 1)
        except:
            rep += "{}\n".format(val)
    return rep

class structObject(with_metaclass(metaclassFactory,object)):
    """The base class that scaffolding is used to build out

    Fields attributes:
    type
    value
    len - can be int or function that returns int, function should only use field previously defined
    """
    __slots__ = (
        '_values',
        '_bindata'
    )
    _field_order = ()
    _segments = ()
    _constructors = ()
    _byte_order = None

    def __init__(self, *args, **kargs):
        """Populate instance based on subclass scaffolding"""
        self._values = []

        # handle special cases where list or dict used
        if len(args) == 1 and isinstance(args[0], (list, tuple)):
            args = args[0]
        elif len(args) == 1 and isinstance(args[0],dict):
            kargs = args[0]
            args=[]

        # TODO this is the dumb way to populate, generates defaults first
        _bin = ''
        if len(args) == 1 and isinstance(args[0], string_types + (memoryview,)):
            _bin = args[0]
            args= []
                
        # TODO check that len(args[0]) <= len(self)
        if len(args) == 0 and len(kargs) == 0:
            for i, name in enumerate(self._field_order):
                constructor = self._constructors[i]
                if issubclass(constructor, (structField,structArray)):
                    self._values.append(constructor(self))
                else: #if issubclass(constructor, structObject):
                    self._values.append(constructor())
        else:
            for i,name in enumerate(self._field_order):
                # assign order parameter and defaults for remainder
                constructor = self._constructors[i]
                if i < len(args):
                    value = args[i]
                    if issubclass(constructor, structField):
                        self._values.append(constructor(self,value))
                    elif issubclass(constructor, structObject):
                        if isinstance(value, constructor):
                            self._values.append(value)
                        else:
                            raise TypeError("'{}' must be of type '{}', given '{}'".format(name,constructor.__name__, value.__class__.__name__))
                else:
                    if issubclass(constructor, (structField,structArray)):
                        self._values.append(constructor(self))
                    else: #if issubclass(constructor, structObject):
                        self._values.append(constructor())
            if len(kargs) > 0:
                self.update(kargs)
            
        if _bin != '':
            self.unpack(_bin)
            
    def _index(self, name):
        "Returns the index of the given named field"
        return self._field_order.index(name)
    
    def __len__(self):
        return len(self._field_order)
    
    def _size(self):
        # returns the binary length, accessable through object attribute .size
        s = 0
        for seg in self._segments:
            if isinstance(seg, structSegment):
                s += seg.size
            elif isinstance(seg, int):
                s += self._values[seg].size
        return s
            
    def __getattr__(self, name):
        if name in self._field_order:
            i = self._index(name)
            obj = self._values[i]
            if issubclass(obj.__class__, structField):
                return obj.get()
            else: #if issubclass(obj.__class__, (structObject, structArray)):
                return obj
        elif name == 'size':
            return self._size()
        else:
            return self.__getattribute__(name)
            #return self.__class__.__dict__[name].__get__(self)
        raise AttributeError("Attribute '{}' undefined for structObject".format(name))
            
    def __setattr__(self, name, value):
        if name.startswith('_'):
            object.__setattr__(self,name,value)
        elif name in self._field_order:
            i = self._index(name)
            constructor = self._constructors[i]
            if issubclass(constructor, structField):
                self._values[i].set(value)
            elif issubclass(constructor, structObject):
                if isinstance(value, constructor):
                    self._values[i] = value # probably setting a substructure
                else:
                    raise TypeError("'{}' must be of type '{}', given '{}'".format(name,constructor.__name__, value.__class__.__name__))
        elif name in self.__slots__:
            object.__setattr__(self,name,value)
            #self.__class__.__dict__[name].__set__(self, value)
        else:
            raise AttributeError("Attribute '{}' undefined for structObject".format(name))
            
    def __getitem__(self, key):
        if isinstance(key, string_types):
            if '.' in key:
                _field_names = key.split('.')
                obj = self.__getattr__(_field_names[0])
                for _field_name in _field_names[1:]:
                    obj = obj.__getattr__(_field_name)
                return obj
            else:
                return self.__getattr__(key)
        elif isinstance(key, int):
            if key < len(self._field_order):
                return self.__getattr__(self._field_order[key])
            else:
                raise IndexError("Index: {} not in object".format(key))
        elif isinstance(key, slice):
            _return = []
            _objs = self._values[key]
            for obj in _objs:
                if issubclass(obj.__class__, structField):
                    _return.append(obj.get())
                elif issubclass(obj.__class__, structObject):
                    _return.append(obj)
            return _return
        else:
            raise Exception("Unrecognized index: {}".format(key))
        # support substructures
            # i.e. (test) obj.field.subfield1 == obj['field.subfield1']
    def __setitem__(self, key, item):
        if isinstance(key, string_types):
            if '.' in key:
                _field_names = key.split('.')
                obj = self.__getattr__(_field_names[0])
                for _field_name in _field_names[1:-1]:
                    obj = obj.__getattr__(_field_name)
                obj.__setattr__(_field_names[-1], item)
            else:
                return self.__setattr__(key, item)
        elif isinstance(key, int):
            if key < len(self._field_order):
                return self.__setattr__(self._field_order[key], item)
            else:
                raise IndexError("Index: {} not in object".format(key))
        elif isinstance(key, slice):
            _fields = self._field_order[key]
            for i, _field in enumerate(_fields):
                self.__setattr__(_field, item[i])
        else:
            raise Exception("Unrecognized index: {}".format(key))
            
    #def __iter__(self): pass
    #def __contains__(self, key): pass
    
    def items(self): return zip(self.keys(),self.values())
    def keys(self): return self._field_order[:]
    def values(self):
        l = []
        for name in self._field_order:
            l.append(self.__getattr__(name))
        return l
        #return [self.__getattr__(name) for name in self._field_order]

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
    
    def unpack(self, bindata):
        self._bindata = bindata
        offset = 0
        for seg in self._segments:
            if isinstance(seg, structSegment):
                values = seg.unpack(memoryview(bindata)[offset:offset+seg.size])
                for i, field in enumerate(self._values[seg.slice]):
                    try:
                        field.unprep(values[i])
                    except Exception as e:
                        print (self.__class__.__name__)
                        raise e
            elif isinstance(seg, int):
                seg = self._values[seg]
                seg.unpack(memoryview(bindata)[offset:])
            offset += seg.size

        #log(self.__class__.__name__, offset, self.size)
    
    def pack(self):
        s = bytes("", "ASCII")
        for seg in self._segments:
            if isinstance(seg, structSegment):
                prepped_items = []
                for item in self._values[seg.slice]:
                    prepped_items.append(item.prep())
                s += seg.pack(*prepped_items)
            elif isinstance(seg, int):
                s += self._values[seg].pack()
        return s

    def _pack(self):
        "Old style packing, goes element by element"
        s = bytes("", "ASCII")
        for v in self._values:
            if isinstance(v, structField):
                s += struct.pack(self._byte_order + v.fmt, v.prep())
            elif isinstance(v, structArray):
                s += v.pack()
            elif isinstance(v, structObject):
                s += v._pack()
        return s
    # def iteritems(self): pass
    # def iterkeys(self): pass
    # def itervalues(self): pass

    def __str__(self):
        rep = "{}:\n".format(self.__class__.__name__)
        for item in self.items():
            rep += printItem(item, 1)
        return rep


class Empty(structObject):
    """Placeholder for fields intented to be defined in overloaded subclasses"""
    _field_order = []
    def __init__(self):
        raise NotImplementedError('None type fields must be implemented in subclasses')


class structArray(object):
    # needs to implement size, pack, unpack, get/set-item
    
    __slots__ = (
        'object_type',
        '_variable_length', # used for future support of array types, indicates field should not be included in static segment
        '_parent',
        '_values',
        '_item_size',
        'len'
    )
    
    def __init__(self, _parent):
        self._parent = _parent
        self._values = []
        
        try:
            self.len
        except:
            self.len = None
            
        if isinstance(self.len, int):
            self._variable_length = False
        else:
            self._variable_length = True
        
    def __len__(self):
        return len(self._values)    
    
    @property
    def size(self):
        if issubclass(self.object_type, structField):
            return self._item_size * self.__len__()
        else:
            size = 0
            for obj in self._values:
                size += obj.size
            return size
        
        
    def __getitem__(self, key):
        if isinstance(key, int):
            obj = self._values[key]
            if issubclass(self.object_type, structField):
                return obj.get()
            else:
                return obj
        elif isinstance(key, slice):
            values = []
            for i in range(*key.indices(self.__len__())):
                values.append(self.__getitem__(i))
            return values
        else:
            raise Exception("Unrecognized index: {}".format(key))
        
    def __setitem__(self, key, value):
        if isinstance(key, int):
            if key < len(self._values):
                self._values[key].set(value)
            else:
                raise IndexError("Index: {} not in object".format(key))
        elif isinstance(key, slice):
            for i, index in enumerate(key.indices(self.__len__())):
                self._values[index].set(value[i])
        else:
            raise Exception("Unrecognized index: {}".format(key))

    def append(self, *args, **kargs):
        if issubclass(self.object_type, structField):
            obj = self.object_type(self._parent,*args)
        else:
            obj = self.object_type(*args,**kargs)
        self._values.append(obj)
        
    def pack(self):
        if issubclass(self.object_type, structField):
            return struct.pack(str(self.__len__())+self.object_type.fmt, *self._values)
        elif issubclass(self.object_type, structObject):
            s = bytes("", "ASCII")
            for val in self._values:
                s += val.pack()
            return s

    def unpack(self, bindata):
        if self.len != None:
            if isinstance(self.len[0], int):
                count = self.len[0]
            else:
                count = self.len[0](self._parent)
        else:
            count = len(bindata) - len(bindata) % self._item_size
        
        if issubclass(self.object_type, structField):
            # lets just unpack these all at once
            fmt = str(count)+self.object_type.fmt
            values = struct.unpack(fmt, bindata[0:count*self._item_size])
            for value in values:
                self.append(value)
        else:
            offset = 0
            for i in range(count):
                self.append(memoryview(bindata)[offset:])
                offset += self._values[-1].size
            

def struct_array(**kargs):
    obj_dict = {
        '__slots__':(),
    }
    obj_dict.update(kargs)
    if issubclass(obj_dict['object_type'], structField):
        obj_dict['_item_size'] = struct.calcsize(obj_dict['object_type'].fmt)
    elif issubclass(obj_dict['object_type'], structObject):
        obj_dict['_item_size'] = obj_dict['object_type']().size
    
    if 'len' in obj_dict:
        obj_dict['len'] = (obj_dict['len'],) # protect from becomeing class method
    
    return type('struct_array',(structArray,), obj_dict)
    
