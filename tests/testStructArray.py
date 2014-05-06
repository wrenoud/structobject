import unittest
import struct
import sys

sys.path += ['..']
from src import *

class Point(structObject):
    "Basic point class"
    _field_order = ('x','y')
    x = ctype_double()
    y = ctype_double()

class Path(structObject):
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
        self.assertEqual(p.points[0].items(), [('x',0.0),('y',10.0)])
    
    def testPack(self):
        p = Path()
        p.points.append(0.0,10.0)
        self.assertEqual(p.pack(), struct.pack('Idd',1,0.0,10.0))
        
    
    def testUnpack(self):
        p = Path(struct.pack('Idddd',2,0.0,10.0,10.0,20.0))
        self.assertEqual(p.points[0].items(), [('x',0.0),('y',10.0)])
        self.assertEqual(p.points[1].items(), [('x',10.0),('y',20.0)])
        self.assertEqual(p.point_count, 2)
        
    
        
if __name__ == '__main__':
    unittest.main()