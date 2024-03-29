"""
Expected Usage


# should return a custom class
myfieldclass = ctype_double(
    default = 45.0
)

# should return an instance
myfield = myfieldclass()
myfieldclass()
"""


class structField(object):
    """

    Note: structObject's metaclass will make sure this is a deep copy and set the _parent

    Parameters:
    fmt - struct format character
    default - default if value not sets
    getter - conversion function on value after unpack
    setter - conversion function of value before pack
    generator - a special function that takes the parent instance as parameter
    validator - validation function called on __set__
    value - initializing with a value sets the field as static
    """
    __slots__ = (
        '_parent',
        # 'fmt',
        'python_type',
        'value',
        'getter',
        'setter',
        'generator',
        'validator',
        'doc')

    _static = False  # bool, indicates weith value can be set

    def __init__(self, _parent, init_value=None):
        self._parent = _parent

        # defaults
        # self._variable_length = False
        # self.setter = [lambda x: x,]
        # self.getter = [lambda x: x,]
        # self.generator = None
        # self.validator = []

        # note that some instances may have generators, but we won't block setting
        # the value until after initialization in case this is a value being read

        # if the subclass didn't initialize self.value we need to do that
        # before trying to access it

        if self._static == False:
            self.value = None
            if init_value == None:
                self.set(self.default)
            else:
                self.set(init_value)
        elif init_value != None and self.value != init_value:
            raise Exception("Can't store value for static field")

    def get(self, raw=False):
        # if self.generator != None && raw == False:
        #    return self.generator[0](self._parent)
        # else:
        return self.value

    def set(self, value):
        if self._static:
            raise AttributeError('Static field is not writeable')
        # elif self.generator != None:
        # raise AttributeError('Generated field is not writeable')
        else:
            if self.validator is not None:
                for val in self.validator:
                    if not val(value):
                        raise Exception("Validation error, given value {}".format(value))

            self.value = value

    def prep(self):
        if self.generator is not None:
            val = self.generator[0](self._parent)
        else:
            val = self.get()
        if self.setter is not None:
            _tmp = self.setter[0](val)
        else:
            _tmp = val
        if not isinstance(_tmp, self.python_type):
            raise Warning("{} is not of type {}, trying coercion".format(self.get(), type(self.python_type())))
            _tmp = self.python_type(_tmp)
        return _tmp

    def unprep(self, value):
        if self.getter is not None:
            _tmp = self.getter[0](value)
        else:
            _tmp = value
        if self._static:
            if _tmp != self.get():
                raise Exception(
                    "Value ({}) does not match expected ({}) {}".format(value, self.get(), self.__class__.__name__))
            else:
                pass  # looks good
        else:
            self.set(_tmp)
        # TODO generator
        # TODO if static should match value


# attributes (passed into the factories as named parameters) that all
# subclassses have in common
_standard_parameters = [
    'len',
    'value',
    'getter',
    'setter',
    'generator',
    'validator',
    'doc']


def attrib_housekeeping(default_attrib, user_attrib, special_attrib):
    """Utility function for the structField factory functions.
    
    Ensures that the attributes (as parameters) passed into the factory are allowed values."""
    allowed = _standard_parameters + special_attrib
    for key, value in user_attrib.items():
        if key not in allowed:
            raise Warning("Unsupported attribute '{}'".format(key))

    # ok, lets add the attributes to the default
    default_attrib.update(user_attrib)

    if 'value' in default_attrib:
        default_attrib["_static"] = True

    # now we just have to touch up a couple attributes
    if 'setter' in default_attrib:
        default_attrib['setter'] = (default_attrib['setter'],)
    else:
        default_attrib['setter'] = None
    if 'getter' in default_attrib:
        default_attrib['getter'] = (default_attrib['getter'],)
    else:
        default_attrib['getter'] = None
    if 'generator' in default_attrib:
        default_attrib['generator'] = (default_attrib['generator'],)
    else:
        default_attrib['generator'] = None
    if 'validator' in default_attrib:
        default_attrib['validator'] = default_attrib['validator']
    else:
        default_attrib['validator'] = None

    default_attrib["_variable_length"] = False


def ctype_pad(**kargs):
    special_parameters = []
    obj_dict = {
        '__slots__': (),
        'fmt': 'x',
        'default': 0x00,
        'python_type': str,
        'doc': 'padding byte',
    }
    attrib_housekeeping(obj_dict, kargs, special_parameters)
    return type('ctype_pad', (structField,), obj_dict)


def ctype_char(**kargs):
    special_parameters = []
    obj_dict = {
        '__slots__': (),
        'fmt': 'c',
        'default': 0x00,
        'python_type': str,
        'doc': 'string of length 1',
    }
    attrib_housekeeping(obj_dict, kargs, special_parameters)
    return type('ctype_char', (structField,), obj_dict)


def ctype_schar(**kargs):
    special_parameters = []
    obj_dict = {
        '__slots__': (),
        'fmt': 'b',
        'default': 0,
        'python_type': int,
        'doc': 'signed char',
    }
    attrib_housekeeping(obj_dict, kargs, special_parameters)
    return type('ctype_schar', (structField,), obj_dict)


def ctype_uchar(**kargs):
    special_parameters = []
    obj_dict = {
        '__slots__': (),
        'fmt': 'B',
        'default': 0,
        'python_type': int,
        'doc': 'unsigned char',
    }
    attrib_housekeeping(obj_dict, kargs, special_parameters)
    return type('ctype_uchar', (structField,), obj_dict)


def ctype_bool(**kargs):
    special_parameters = []
    obj_dict = {
        '__slots__': (),
        'fmt': '?',
        'default': False,
        'python_type': bool,
        'doc': 'boolean value',
    }
    attrib_housekeeping(obj_dict, kargs, special_parameters)
    return type('ctype_bool', (structField,), obj_dict)


def ctype_short(**kargs):
    special_parameters = []
    obj_dict = {
        '__slots__': (),
        'fmt': 'h',
        'default': 0,
        'python_type': int,
        'doc': 'short',
    }
    attrib_housekeeping(obj_dict, kargs, special_parameters)
    return type('ctype_short', (structField,), obj_dict)


def ctype_ushort(**kargs):
    special_parameters = []
    obj_dict = {
        '__slots__': (),
        'fmt': 'H',
        'default': 0,
        'python_type': int,
        'doc': 'unsigned short',
    }
    attrib_housekeeping(obj_dict, kargs, special_parameters)
    return type('ctype_ushort', (structField,), obj_dict)


def ctype_int(**kargs):
    special_parameters = []
    obj_dict = {
        '__slots__': (),
        'fmt': 'i',
        'default': 0,
        'python_type': int,
        'doc': 'signed integer',
    }
    attrib_housekeeping(obj_dict, kargs, special_parameters)
    return type('ctype_int', (structField,), obj_dict)


def ctype_uint(**kargs):
    special_parameters = []
    obj_dict = {
        '__slots__': (),
        'fmt': 'I',
        'default': 0,
        'python_type': int,
        'doc': 'unsigned integer',
    }
    attrib_housekeeping(obj_dict, kargs, special_parameters)
    return type('ctype_uint', (structField,), obj_dict)


def ctype_long(**kargs):
    special_parameters = []
    obj_dict = {
        '__slots__': (),
        'fmt': 'l',
        'default': 0,
        'python_type': int,
        'doc': 'signed long',
    }
    attrib_housekeeping(obj_dict, kargs, special_parameters)
    return type('ctype_long', (structField,), obj_dict)


def ctype_ulong(**kargs):
    special_parameters = []
    obj_dict = {
        '__slots__': (),
        'fmt': 'L',
        'default': 0,
        'python_type': int,
        'doc': 'unsigned long',
    }
    attrib_housekeeping(obj_dict, kargs, special_parameters)
    return type('ctype_ulong', (structField,), obj_dict)


def ctype_double(**kargs):
    special_parameters = []
    obj_dict = {
        '__slots__': (),
        'fmt': 'd',
        'default': 0.0,
        'python_type': float,
        'doc': 'double',
    }
    attrib_housekeeping(obj_dict, kargs, special_parameters)
    return type('ctype_double', (structField,), obj_dict)


def ctype_float(**kargs):
    special_parameters = []
    obj_dict = {
        '__slots__': (),
        'fmt': 'f',
        'default': 0.0,
        'python_type': float,
        'doc': 'float',
    }
    attrib_housekeeping(obj_dict, kargs, special_parameters)
    return type('ctype_float', (structField,), obj_dict)


def ctype_string(**kargs):
    special_parameters = ['len']
    obj_dict = {
        '__slots__': (),
        'fmt': 's',
        'default': 0x00,
        'len': 1,
        'python_type': str,
        'doc': 'string',
    }
    attrib_housekeeping(obj_dict, kargs, special_parameters)
    return type('ctype_string', (structField,), obj_dict)
