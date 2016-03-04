import sys
sys.path.append("..\\")

from structobject import *

class StructArrayBase(object):
    _python_type = list

    def flat(self):
        return self._flat

    def __init__(self, object_type=None, len=None, default=None, getter=None, setter=None, value=None):
        self._length = len
        self.object_type = object_type

        self._flat = False

    def __get__(self, parent, parent_type=None):
        if parent is not None:
            # kansas city shuffle
            # retrieve values from parent, for now we'll masquerade as this parent's child
            if id(self) not in parent._values:
                # hasn't been initialized in parent, set all values to none
                # self.__set__(parent, None)
                parent._values[id(self)] = []
            self._values = parent._values[id(self)]
        return self

    def __set__(self, parent, value):
        # create empty dict in parent
        if issubclass(value.__class__, self.__class__):
            # copy pointer to outside values
            parent._values[id(self)] = value._values
        elif issubclass(value.__class__, list):
            parent._values[id(self)] = value
        elif issubclass(value.__class__, tuple):
            parent._values[id(self)] = list(value)
        else:
            # find my name to tell user
            name = ''
            for key in parent._field_order:
                if id(parent.__class__.__dict__[key]) == id(self):
                    name = key
                    break
            raise TypeError("'{}' must be of type '{}', given '{}'".format(name, self.__class__.__name__, value.__class__.__name__))

    def __len__(self):
        pass
    def __getitem__(self, key):
        if isinstance(key, int):
            obj = self._values[key]
            if issubclass(self.object_type.__class__, StructFieldBase):
                return obj.get()
            elif issubclass(self.object_type.__class__, StructObjectBase):
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
        if issubclass(self.object_type.__class__, StructFieldBase):
            obj = self.object_type(self._parent,*args)
        elif issubclass(self.object_type.__class__, StructObjectBase):
            obj = self.object_type(*args,**kargs)
        self._values.append(obj)

    @property
    def size(self):
        if issubclass(self.object_type.__class__, StructFieldBase):
            return self.object_type.size * len(self.__len__())
        elif issubclass(self.object_type.__class__, StructObjectBase) and self.object_type.flat():
            return self.object_type.size * len(self.__len__())
        else:
            size = 0
            for obj in self._values:
                size += obj.size
            return size


if __name__ == "__main__":
    import unittest

    class StructObjectBaseTests(unittest.TestCase):
        def testSize(self):
            class DoubleList(StructObjectBase):
                _field_order = ('doubles',)
                doubles = StructArrayBase(ctype_double(), 6)

            d = DoubleList()
            print(d.doubles.size)

    unittest.main()