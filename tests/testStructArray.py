from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest
import struct
import sys

sys.path.append("..\\")

from structobject import *

class Point(structobject):
    "Basic point class"
    _field_order = ('x','y')
    x = ctype_double()
    y = ctype_double()

class Path(structobject):
    _field_order = ('point_count','points')
    # the number of points in the path
    point_count = ctype_uint(
        generator = lambda self: len(self.points)
    )
    # the points
    points = struct_array(
        object_type = Point,
        len = lambda self: self.point_count
    )

class structArrayTests(unittest.TestCase):
   
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
        class generic_string(structobject):
            _field_order = ('text',)
            text=struct_array(object_type=ctype_char())
        
        s = bytes('Hello World',"ASCII")
        o = generic_string(bytes('Hello World',"ASCII"))
        self.assertEqual(o.text[:], [chr(x) for x in s])
        
if __name__ == '__main__':
    unittest.main()