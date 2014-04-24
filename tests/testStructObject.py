import sys
import unittest

sys.path += ['..']
from structObject import *

class structObjectTests(unittest.TestCase):
    # if length is specified it should be an array or 's'
    def testOrder(self):
        # exception should be raised if '_order' not defined in subclass
        # exception should be raise if '_order' defined in subclass that isn't first decendant of structObject
        pass
# no exception should be raised if parent has '_order' defined

# trying to define a class with multiple parents should raise exception

# subclass shouldn't redefine order, exception should be raised

# if field attribute is not int or function should raise exception
# edge case, sub sub class has variable segment dependant on field defined in super, is this accesable?

if __name__ == '__main__':
    unittest.main()
    