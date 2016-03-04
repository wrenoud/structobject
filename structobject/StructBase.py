STRUCT_OBJECT_COUNTER = 0

class virtual(object):
    def __init__(self, func=None):
        self.func = func

    def __get__(self):
        if self.func is not None:
            raise Exception(
                "Trying to call virtual method, {} must be implemented in a subclass".format(self.func.__name__))
        else:
            raise Exception("Trying to access virtual object, object must be defined in a subclass")


class StructBase(object):
    """Descriptor class used for modeling a binary field or a fixed array of fields

    """
    _partial_class = False
    _flat = True

    def __init__(self, *args, **kargs):
        global STRUCT_OBJECT_COUNTER
        self._id = STRUCT_OBJECT_COUNTER = STRUCT_OBJECT_COUNTER + 1

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

    size = virtual()