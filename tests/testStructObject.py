import sys
import unittest
import struct

sys.path += ['..']
from structObject import *
from structField import *

class Point(structObject):
    "Basic point class"
    _field_order = ('x','y')
    x = ctype_double()
    y = ctype_double()

class structObjectTests(unittest.TestCase):
    # if length is specified it should be an array or 's'
    def testOrder(self):
        # exception should be raised if '_order' not defined in subclass
        # exception should be raise if '_order' defined in subclass that isn't first decendant of structObject
        pass

    def testInitSetByAttribute(self):
        p = Point()
        self.assertEqual(p.items(),[('x', 0.0), ('y', 0.0)])
        p.x = 5000.0
        p.y = 300.5
        self.assertEqual(p.items(),[('x', 5000.0), ('y', 300.5)])

    def testInitImplicitOrder(self):
        p = Point(5000.0, 300.5)
        self.assertEqual(p.items(),[('x', 5000.0), ('y', 300.5)])

    def testInitExplicitNames(self):
        p = Point(y=300.5, x=5000.0)
        self.assertEqual(p.items(),[('x', 5000.0), ('y', 300.5)])

    def testInitMixedOrdering(self):
        p = Point(5000.0, y=300.5)
        self.assertEqual(p.items(),[('x', 5000.0), ('y', 300.5)])

    def testInitImplicitList(self):
        p = Point((5000.0, 300.5))
        self.assertEqual(p.items(),[('x', 5000.0), ('y', 300.5)])

    def testInitExplicitDict(self):
        p = Point({'x':5000.0, 'y':300.5})
        self.assertEqual(p.items(),[('x', 5000.0), ('y', 300.5)])

    def testBinaryDouble(self):
        p = Point(5000.0, 300.5)
        self.assertEqual(p.pack(), struct.pack('dd', 5000.0, 300.5))
        
# no exception should be raised if parent has '_order' defined

# trying to define a class with multiple parents should raise exception

# subclass shouldn't redefine order, exception should be raised

# if field attribute is not int or function should raise exception
# edge case, sub sub class has variable segment dependant on field defined in super, is this accesable?

if __name__ == '__main__':
    unittest.main()
    