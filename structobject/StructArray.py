import sys
sys.path.append("..\\")

from .StructObject import *

class StructArrayBase(StructBase):
    _python_type = list

    def flat(self):
        return self._flat

    def __init__(self, object_type=None, len=None, default=None, getter=None, setter=None, value=None):
        self._length = len
        self.object_type = object_type

        if not issubclass(object_type.__class__, StructBase):
            raise Exception("Not an instance of a class that subclasses StructBase")

        self._flat = False

    def __get__(self, parent, parent_type=None):
        if parent is not None:
            # kansas city shuffle
            # retrieve values from parent, for now we'll masquerade as this parent's child
            if self._name not in parent._values:
                # hasn't been initialized in parent, set all values to none
                # self.__set__(parent, None)
                parent._values[self._name] = []
            self._values = parent._values[self._name]
        return self

    def __set__(self, parent, value):
        # create empty dict in parent
        if value is None:
            self._values = parent._values[self._name] = []
        elif issubclass(value.__class__, self.__class__):
            # copy pointer to outside values
            parent._values[self._name] = value._values
        elif issubclass(value.__class__, list):
            parent._values[self._name] = value
        elif issubclass(value.__class__, tuple):
            parent._values[self._name] = list(value)
        else:
            raise TypeError("'{}' must be of type '{}', given '{}'".format(self._name, self.__class__.__name__, value.__class__.__name__))

    def __len__(self):
        return len(self._values)

    def __getitem__(self, key):
        if isinstance(key, int):
            obj = self._values[key]
            if issubclass(self.object_type.__class__, StructFieldBase):
                return self.object_type.unprep(obj)
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
                self._values[key] = self.object_type.prep(value)
            else:
                raise IndexError("Index: {} not in object".format(key))
        elif isinstance(key, slice):
            for i, index in enumerate(key.indices(self.__len__())):
                self._values[index] = self.object_type.prep(value[i])
        else:
            raise Exception("Unrecognized index: {}".format(key))

    def append(self, *args, **kargs):
        if issubclass(self.object_type.__class__, StructFieldBase):
            obj = self.object_type.prep(args[0])
        elif issubclass(self.object_type.__class__, StructObjectBase):
            # TODO: this is ineficient, it creates a new descriptor for each item
            obj = self.object_type.__class__(*args,**kargs)
        self._values.append(obj)

    @property
    def size(self):
        if issubclass(self.object_type.__class__, StructFieldBase):
            return self.object_type.size * self.__len__()
        elif issubclass(self.object_type.__class__, StructObjectBase) and self.object_type.flat():
            return self.object_type.size * self.__len__()
        else:
            size = 0
            for obj in self._values:
                size += obj.size
            return size

    def _unpack_from(self, bindata, parent, offset=0):
        if self._length != None:
            if isinstance(self._length, int):
                count = self._length
            else:
                count = self._length(parent)
        else:
            count = len(bindata) - len(bindata) % self.object_type.size

        if issubclass(self.object_type.__class__, StructFieldBase):
            # lets just unpack these all at once
            fmt = bytes(str(count), "ASCII") + self.object_type.format
            self._values = parent._values[self._name] = struct.unpack(fmt, bindata[0:count*self.object_type.size])
        elif issubclass(self.object_type.__class__, StructObjectBase):
            for i in range(count):
                self.append(memoryview(bindata)[self.size:])

    def _pack(self):
        if issubclass(self.object_type.__class__, StructFieldBase):
            return struct.pack(str(self.__len__())+self.object_type.fmt, *self._values)
        elif issubclass(self.object_type.__class__, StructObjectBase):
            s = bytes("", "ASCII")
            for val in self._values:
                s += val.pack()
            return s