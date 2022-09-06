def with_metaclass(meta, *bases):
    """Create a base class with a metaclass. For 2/3 compatibility."""

    class metaclass(meta):
        __call__ = type.__call__
        __init__ = type.__init__

        def __new__(cls, name, this_bases, d):
            if this_bases is None:
                return type.__new__(cls, name, (), d)
            return meta(name, bases, d)

    return metaclass("NewBase", None, {})


def make_memoryview(obj, offset=-1, size=-1):
    """Uses Python2 buffer syntax to make memoryview"""
    if offset < 0:
        return memoryview(obj)
    elif size < 0:
        return memoryview(obj)[offset:]
    else:
        return memoryview(obj)[offset:offset + size]


string_types = (bytes, str)
