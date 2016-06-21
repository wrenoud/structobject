from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest
import struct
import sys

sys.path.append("..\\")

from structobject import *

class Point(StructObjectBase):
    "Basic point class"
    x = FieldType.double()
    y = FieldType.double()

class Path(StructObjectBase):
    # the number of points in the path
    point_count = FieldType.uint(
        #generator = lambda self: len(self.points)
    )
    # the points
    points = StructArrayBase(
        object_type = Point(),
        len = lambda self: self.point_count
    )

class DoubleList(StructObjectBase):
    count = FieldType.uint(default=6)
    doubles = StructArrayBase(FieldType.double(), 6)

class structArrayTests(unittest.TestCase):

    def testAppendSimpleObject(self):
        d = DoubleList()

        d.doubles.append(3)
        d.doubles.append(4)

        self.assertEqual(d.doubles[1], 4)

    def testAppend(self):
        p = Path()
        p.points.append(0.0,10.0)
        self.assertEqual(list(p.points[0].items()), [('x',0.0),('y',10.0)])
    
    def testPack(self):
        p = Path()
        p.points.append(0.0,10.0)
        self.assertEqual(p.pack(), struct.pack('Idd',1,0.0,10.0))
        
    
    def testUnpack(self):
        p = Path(struct.pack('Idddd',2,0.0,10.0,10.0,20.0))
        self.assertEqual(list(p.points[0].items()), [('x',0.0),('y',10.0)])
        self.assertEqual(list(p.points[1].items()), [('x',10.0),('y',20.0)])
        self.assertEqual(p.point_count, 2)
        
    def testObjectTypeStructFieldWOLenIssue6(self):
        class generic_string(StructObjectBase):
            text=StructArrayBase(object_type=FieldType.char())
        
        s = bytes('Hello World',"ASCII")
        o = generic_string(bytes('Hello World',"ASCII"))
        self.assertEqual(o.text[:], [bytes(chr(x), "ASCII") for x in s])

    def testBadObjectType(self):
        with self.assertRaises(Exception):
            StructArrayBase(object_type = Point)

if __name__ == '__main__':
    unittest.main()