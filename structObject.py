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
            print class_attr

            if len(class_bases) > 1:
                raise Exception("multiple super classes not implemented")
            _base = class_bases[0]
            
            if '_field_order' in class_attr and _base != structObject:
                raise Exception("Only subclasses of structObject may define '_field_order' attribute")
            elif '_field_order' not in class_attr and _base == structObject:
                raise Exception("Subclasses that extend structObject must define class attribute '_field_order'")
            elif '_field_order' not in class_attr:
                # superclass order assumed as subclass order
                class_attr['_field_order'] = _base._field_order
            _field_order = class_attr['_field_order']

            class_attr['__slots__'] = class_attr['_field_order']
            
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
                    raise Exception("Attribute '{}' included in '_field_order' but not defined".format(name))
                class_attr['_constructors'].append(class_attr[name])
                del(class_attr[name])

        return type.__new__(metaclass, class_name, class_bases, class_attr)

        
def _isinstance(self, obj, *args):
    "Convenience function to test obj against multiple types."
    for obj_type in args:
        if isinstance(obj,obj_type): return True
    return False

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
        #'_segments', # array, holds compiled structs, needed in case there is a substructure, variable array, string, or pascal
        '_byte_order',
        '_values'
    )
    _byte_order = None

    __metaclass__ = metaclassFactory

    def __init__(self, *args, **kargs):
        """Populate instance based on subclass scaffolding"""
        self._values = []
        if len(args) == 0 and len(kargs) == 0:
            for i,name in enumerate(self._field_order):
                constructor = getattr(self,'_constructors')[i]
                self._values.append(constructor(self))
        elif len(args) == 1 and _isinstance(args[0],str, buffer):
            pass # parse binary
        elif len(args) == 1 and _isinstance(args[0], list, tuple):
            for i,name in enumerate(self._field_order):
                constructor = getattr(self,'_constructors')[i]
                if i < len(args[0]):
                    if isinstance(args[0][i], constructor):
                        self._values.append(args[0][i])
                    else:
                        self._values.append(constructor(self,args[0][i]))
                else:
                    self._values.append(constructor(self))
            # check that len(args[0]) <= len(self)
            # note: current implementation won't navigate substructures
        elif len(args) == 1 and isinstance(args[0],dict):
            pass # populate named values, raise exception if key without attr
        else:
            for i,name in enumerate(self._field_order):
                constructor = getattr(self,'_constructors')[i]
                if i < len(args):
                    if isinstance(args[i], constructor):
                        self._values.append(args[i])
                    else:
                        self._values.append(constructor(self,args[i]))
                else:
                    self._values.append(constructor(self))
            for key, value in kargs.iteritems():
                i = self._field_order.index(key)
                constructor = getattr(self,'_constructors')[i]

                if isinstance(value, constructor):
                    self._values[i] = value
                else:
                    self._values[i] = constructor(self,value)
    
    def __len__(self): pass
    def __getattr__(self, name):
        if name in self._field_order:
            i = self._field_order.index(name)
            obj = self._values[i]
            if issubclass(obj.__class__, structField):
                return obj.get()
            elif issubclass(obj.__class__, structObject):
                return obj
        raise AttributeError("Attribute '{}' undefined for structObject".format(name))
            
    def __setattr__(self, name, value):
        if name.startswith('_'):
            object.__setattr__(self,name,value)
        elif name in self._field_order:
            i = self._field_order.index(name)
            obj = self._values[i]
            if hasattr(obj, 'set'):
                obj.set(value)
            else:
                self._values[i] = value # probably setting a substructure
                # TODO, make sure they're not abusing this
        else:
            raise AttributeError("Attribute '{}' undefined for structObject".format(name))
            
    def __getitem__(self, key): pass
        # support substructures
            # i.e. (test) obj.field.subfield1 == obj['field.subfield1']
    def __setitem__(self, key, item): pass
    def __iter__(self): pass
    def __contains__(self, key): pass
    
    def items(self): return zip(self.keys(),self.values())
    def keys(self): return self._field_order
    def values(self):
        l = []
        for name in self._field_order:
            l.append(self.__getattr__(name))
        return l
        #return [self.__getattr__(name) for name in self._field_order]

    def pack(self):
        s = ''
        for v in self._values:
            if isinstance(v, structField):
                s += struct.pack(self._byte_order + v.fmt, v.prep())
            elif isinstance(v, structObject):
                s += v.pack()
        return s
    # def iteritems(self): pass
    # def iterkeys(self): pass
    # def itervalues(self): pass

if __name__ == "__main__":
    from structField import *

    class Point(structObject):
        "Basic point class"
        _field_order = ('x','y')
        x = ctype_double()
        y = ctype_double()
    
    p = Point()
    print p.items()
    p.x = 5000.0
    p.y = 300.5
    print p.x, p.y
    print p.items(), p._values

    p = Point(5000.0, 300.5)
    print p.items(), p._values

    p = Point(y=300.5, x=5000.0)
    print p.items(), p._values

    p = Point(5000.0, y=300.5)
    print p.items(), p._values
    import binascii
    print binascii.hexlify(p.pack())

    class BoundingBox(structObject):
       _field_order = ('northwest','southeast')
       northwest = Point
       southeast = Point
    bb = BoundingBox(Point(0.0, 10.0), southeast=Point(15.0, 0.0))
    print bb.items()
    print "Getting stuff"
    print bb.northwest.keys()
    print bb.northwest.x
    print bb.northwest.y
    print bb.southeast.x


    class myHeader(structObject):
        _field_order = ('STX','model')
        STX = ctype_char(value='0x02')
        model = ctype_int()
        
    class myFooter(structObject):
        _field_order = ('ETX',)
        ETX = ctype_char(value='0x03')
            
    class BaseClass(structObject):
        _field_order = ('header','body','footer')
            
        header = myHeader
        body = None
        footer = myFooter
        
    class subClass(BaseClass):
        body = Point

    print subClass().items()