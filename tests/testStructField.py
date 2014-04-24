import sys
import unittest
import time
import calendar

sys.path += ['..']
from structField import *

class structFieldTests(unittest.TestCase):
    def testFactories(self):
        # make sure the factories run and return a class with the base structField
        self.assertEquals(ctype_pad().__base__,structField)
        self.assertEquals(ctype_char().__base__,structField)
        self.assertEquals(ctype_schar().__base__,structField)
        self.assertEquals(ctype_uchar().__base__,structField)
        self.assertEquals(ctype_bool().__base__,structField)
        self.assertEquals(ctype_short().__base__,structField)
        self.assertEquals(ctype_ushort().__base__,structField)
        self.assertEquals(ctype_int().__base__,structField)
        self.assertEquals(ctype_uint().__base__,structField)
        self.assertEquals(ctype_long().__base__,structField)
        self.assertEquals(ctype_ulong().__base__,structField)
        self.assertEquals(ctype_double().__base__,structField)
        self.assertEquals(ctype_float().__base__,structField)
        self.assertEquals(ctype_string().__base__,structField)

    def testFactoriesWithBadAttributeDef(self):
        "Tries setting a non statndard attribute with a factory"
        self.assertRaisesRegexp(Warning,"Unsupported attribute 'random_attr'",ctype_int,random_attr=None)

    def testStatic(self):
        field = ctype_int(value=10) # create a field definition with static value
        fieldInstance = field(None) # create instance
        fieldInstance = field(None,10) # create instance with static value
        self.assertEquals(fieldInstance.get(), 10)
        # try to create instance with value not equal to static value
        self.assertRaises(Exception, field, None, value=11)
        self.assertRaises(Exception, fieldInstance.set, 11)

    def testGetterSetter(self):
        field = ctype_uint(
            setter=calendar.timegm,
            getter=time.gmtime
        )
        fieldInstance = field(None)
        fieldInstance.unprep(13000000)
        self.assertEqual(fieldInstance.get(), time.gmtime(13000000))
        self.assertEqual(fieldInstance.prep(), 13000000)
        
    def testGenerator(self):
        self.fail('testGenerator() not yet implemented')

    def testValidator(self):
        def is_odd(s): return s % 2 != 0
        field = ctype_int(validator=[is_odd])
        fieldInstance = field(None,11) # should not raise error
        self.assertRaises(Exception, field, None, value=10)

    def testString(self):
        # using the 's' format there should be an exception raised if no length specified
        self.fail('testString() not yet implemented')

    def testPrep(self):
        field = ctype_int()
        fieldInstance = field(None,'1')
        self.assertRaises(Warning,fieldInstance.prep)

    def testUnprep(self):
        # static field should raise error if unprepped with different value
        field = ctype_int(value=10)
        fieldInstance = field(None, 10)
        self.assertRaises(Exception, fieldInstance.unprep, 15)

if __name__ == '__main__':
    unittest.main()
    