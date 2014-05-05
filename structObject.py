import struct
import inspect
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

            # some error handling
            if '_field_order' in class_attr and _base != structObject:
                raise Exception("Only subclasses of structObject may define '_field_order' attribute")
            elif '_field_order' not in class_attr and _base == structObject:
                raise Exception("Subclasses that extend structObject must define class attribute '_field_order'")
            elif '_field_order' not in class_attr:
                # superclass order assumed as subclass order
                class_attr['_field_order'] = _base._field_order
            _field_order = class_attr['_field_order']

            class_attr['__slots__'] = ()
            
            # default byte order uses native with standard sizes and no alignment
            if '_byte_order' not in class_attr and _base == structObject:
                class_attr['_byte_order'] = native
            elif '_byte_order' not in class_attr:
                class_attr['_byte_order'] = _base._byte_order
            _byte_order = class_attr['_byte_order']
                
            # make sure attributes are included in _field_order
            for key, val in class_attr.iteritems():
                # ignore private attributes and class methods (they're functions until we call type())
                if not key.startswith('_') and \
                    not inspect.isfunction(val) and \
                    key not in _field_order: 
                        raise Exception("Attribute '{}' not included in '_field_order'".format(key))

            class_attr['_constructors'] = []
            # makes sure attribute in _field_order are defined
            for i,name in enumerate(_field_order):
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
                elif issubclass(constructor, structObject):
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

class structObject(object):
    """The base class that scaffolding is used to build out

    Fields attributes:
    type
    value
    len - can be int or function that returns int, function should only use field previously defined
    """
    __slots__ = (
        '_field_order', # field order, reqired for any 'first generation' subclass
        '_constructors',
        '_segments', # array, holds compiled structs, needed in case there is a substructure, variable array, string, or pascal
        '_byte_order',
        '_values'
    )
    _byte_order = None

    __metaclass__ = metaclassFactory

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
        if len(args) == 1 and isinstance(args[0], (str, buffer)):
            _bin = args[0]
            args= []
                
        # TODO check that len(args[0]) <= len(self)
        if len(args) == 0 and len(kargs) == 0:
            for i, name in enumerate(self._field_order):
                constructor = self._constructors[i]
                if issubclass(constructor, structField):
                    self._values.append(constructor(self))
                elif issubclass(constructor, structObject):
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
                    if issubclass(constructor, structField):
                        self._values.append(constructor(self))
                    elif issubclass(constructor, structObject):
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
            elif issubclass(obj.__class__, structObject):
                return obj
        elif name == 'size':
            return self._size()
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
        else:
            raise AttributeError("Attribute '{}' undefined for structObject".format(name))
            
    def __getitem__(self, key):
        if isinstance(key, str):
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
        if isinstance(key, str):
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
    def keys(self): return self._field_order
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

        for key, value in kargs.iteritems():
            self.__setattr__(key,value)
    
    def unpack(self, value):
        offset = 0
        for seg in self._segments:
            if isinstance(seg, structSegment):
                values = seg.unpack(buffer(value,offset,seg.size))
                for i, field in enumerate(self._values[seg.slice]):
                    field.unprep(values[i])
                offset += seg.size
            elif isinstance(seg, int):
                self._values[seg].unpack(buffer(value,offset))
                offset += self._values[seg].size
    
    def pack(self):
        s = ''
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
        s = ''
        for v in self._values:
            if isinstance(v, structField):
                s += struct.pack(self._byte_order + v.fmt, v.prep())
            elif isinstance(v, structObject):
                s += v._pack()
        return s
    # def iteritems(self): pass
    # def iterkeys(self): pass
    # def itervalues(self): pass

class Empty(structObject):
    """Placeholder for fields intented to be defined in overloaded subclasses"""
    _field_order = []
    def __init__(self):
        raise NotImplementedError('None type fields must be implemented in subclasses')
        
        