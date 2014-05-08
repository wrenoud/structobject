structObject
============

A verbose pythonic semantic for describing binary data structures and associated python objects.

Basic Usage
-----------

For this first example we're going to define a simple 2D point with the attributes `x` and `y`representing binary doubles.

```Python
class Point(structObject):
    "Basic point class"
    _field_order = ('x','y')
    x = ctype_double()
    y = ctype_double()
```

Object instances of the `Point` class, which extends the `structObject`, can be initialized in several different ways. First, omitting any parameters the instance will be populated with default values (here we haven't specified defaults so 0.0 is assumed). The attributes can be assigned values after initialization.

```Python
>>> p = Point() # create default instance
>>> print p.items()
[('x',0.0), ('y', 0.0)]
>>> p.x = 5000.0 # set x
>>> p.y = 300.5 # set y
>>> print p.items()
[('x',5000.0), ('y', 300.5)]
```
Alternately, the object can be initialized with our values. The parameter order should match the order specified in the class attribute `_field_order`.
```Python
>>> p = Point(5000.0, 300.5)
>>> print p.items()
[('x',5000.0), ('y', 300.5)]
```

Or we can use the attribute names if we forgot the order.

```Python
>>> p = Point(y=300.5, x=5000.0)
>>> print p.items()
[('x',5000.0), ('y', 300.5)]
```

Or mix the two (just remeber that after the first named parameter subsequent parameters will have to be named as well).

```Python
>>> p = Point(5000.0, y=300.5)
>>> print p.items()
[('x',5000.0), ('y', 300.5)]
```

To get the binary representation just call the class method `pack`

```Python
>>> p.pack()
'\x00\x00\x00\x00\x00\x88\xb3@\x00\x00\x00\x00\x00\xc8r@'
```

Lastly, we can initialize with a binary string.

```Python
>>> p = Point(binary_data)
>>> print p.items()
[('x',5000.0), ('y', 300.5)]
```

Using Substructures
-------------------

We're going to reuse the `Point` class to describe a rectangular bounding box with two attributes, the northwest and southeast corners.

```Python
class BoundingBox(structObject):
    _field_order = ('northwest','southeast')
    northwest = Point
    southeast = Point
```

Seriously, it's that easy. Let's initialize one of these.

```Python
>>> bb = BoundingBox()
>>> print bb.items()
[('northwest', <Point object>), ('southeast',  <Point object>)]
```

Let's try that again but with some points

```Python
>>> bb = BoundingBox(Point(0.0, 10.0), Point(15.0, 0.0))
>>> print bb.northwest.y
10.0
>>> print bb.southeast.x
15.0
```

Overloading
-----------

Subclasses of structObject can be extended and overloaded. This can be especially handy if you have a standard structure that you don't want to redefine.

Here we're going to make a simple datagram structure with a start and end flag, a timestamp and some arbitrary body that we'll overload in a second.

```Python
class GenericDatagram(structObject):
    _field_order = ('STX','timestamp','body','ETX')
    STX = ctype_uchar(value=0x02)
    timestamp = ctype_uint()
    body = None
    ETX = ctype_uchar(value=0x03)
```

Now that we have generic datagram lets make it a wrapper on the BoundingBox structure we defined earlier as an extension of the GenericDatagram structure.

```Python
class BoundingBoxDatagram(GenericDatagram):
    body = BoundingBox
```

That's it. Lets create one of this. We'll set the timestamp and get the binary.

```Python
>>> p = BoundingBoxDatagram()
>>> p.timestamp = time.time()
>>> p.items()
[('STX', 2), ('timestamp', 1398373100.412985), ('body', <__main__.BoundingBox object at 0xb713f3c4>), ('ETX', 3)]
>>> p.pack()
'\x02\xeczYS\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x03'
```

Arrays of Substructures
-----------------------
Now we're going to reuse the point structure to describe a path as a series of points with a description.

```Python
class Path(structObject):
    _field_order = ('description','point_count','points')
    # a nice description of the path
    description = ctype_string(
        len = 25
    )
    # the number of points in the path
    point_count = ctype_uint(
        generator = lambda self: len(self.points)
    )
    # the points
    points = structArray(
        object_type = Point,
        len = lambda self: self.point_count
    )
```

The inline function for length (`len`) is called before a binary read (unpack) and is used for determining the read length.

The generator on `point_count` is only called after the full structure is read.

Explicit Byte Order
-------------------

Up to now we've omitted specifying the byte order. As with python's builtin module `struct`, the systems native byte order will be assumed unless otherwise specified. Lets take the `Point` class and add in the byte order explicitely.

```Python
class Point(structObject):
    "Basic point class"
    _field_order = ('x','y')
    _byte_order = little_endian
    x = ctype_double()
    y = ctype_double()
```

Custom Computed Attributes
------

```Python
class BetterBoundingBox(BoundingBox):
    __slots__ = ('area',)
    def __init__(self, *args, **kargs):
        super(BetterBoundingBox,self).__init__(*args, **kargs)
        
        self.area = (self.southeast.x - self.northwest.x) * \
                    (self.northwest.y - self.southeast.y)
```

Note that we need to pass through the `args` and `kargs` to the superclass initializing function.
Additionally any custom attributes need to listed in `__slots__`.

Lets try it out.

```Python
>>> bb = BetterBoundingBox(Point(0,10),Point(10,0))
>>> print bb.area
100
```