(attributes)=
# Attributes
## Which problem is addressed by attributes?
To parametrize simulation models, different types of parameters are needed. A 
BIM model and specifically an IFC model offers multiple sources for the 
requested information. Let's assume that we need the `net_area` of a wall. This 
information can either be obtained from:
* the official IFC specified `QuantitySet` `Qto_WallBaseQuantities/NetSideArea`
* the unofficial, but typical in ArchiCAD used `BaseQuantities'/NetSideArea`
* any other PropertySet where the BIM modeller might have stored the information
* the calculation of the Space Boundary area of the wall
* nowhere, because the information simply does not exist in the model (might not be the case for this example)

To resolve this problem of multiple available sources and even parameters which
will be not included in the BIM model at all the `Attribute` system provides a solution.

## Concept / How does it work?
Simulation required informations that are potentially available in the BIM model
are stored in an [Attribute](attribute.md) at the corresponding [element](element).

E.g. the already mentioned `net_area` is  implemented by the following lines in 
the the class `OuterWall`:

```python

net_area = attribute.Attribute(
    default_ps=("Qto_WallBaseQuantities", "NetSideArea"),
    functions=[BPSProduct.get_net_bound_area],
    unit=ureg.meter ** 2
)
```
This way bim2sim knows where to look for in the IFC file and which function to 
use if no information exists in the IFC file. Also the unit in which the value 
should be stored is provided as m².  See
[_get_value function of attribute](_get_value) documentation for more detailed 
description which other ways are implemented to obtain a value.

## How are the attributes managed? 
To manage the different attributes every bim2sim [element](element) instance 
owns an instance of the [AttributeManager](AttributeManager) which is stored under `element.attributes`.
This manager manages the values and current status of the [Attributes](attribute.md). 

If an information can't be obtained by the implemented ways in
[_get_value function of attribute](_get_value) of attribute its status will be
changed to `NOT_AVAILABLE`. As some information are mandatory to parametrize a
simulation model, we implemented the concept of [Decisions](Decision)
which is basically a structured way to obtain information from the user. To make 
sure that all relevant information exists, a parameter can be 
[requested](request). This way a [Decisions](Decision) will be created if the 
status of the corresponding attribute is `NOT_AVAILABLE`.

// todo: flow chart with mermaid. To use mermaid: https://github.com/mgaitan/sphinxcontrib-mermaid#markdown-support

The [AttributeManager](AttributeManager) uses the status of each attribute to
store if an attribute was already requested. To trigger all decisions for the 
already requested attributes to finally obtain the corresponding values the 
final tasks before exporting to a simulation model should always trigger the
[](get_pending_attribute_decisions) function of [element](element). This
implementation was made to bundle the decisions at the end of the process if 
possible. 

## When to use `attributes`?

There are multiple ways to calculate and store information in a bim2sim
`element`. Following you will find some guidelines when to use which way.

### bim2sim `attribute`
The specialized bim2sim `attribute` system should be used when:

* Values need to be obtained from different sources (IFC attributes, IFC PropertySets, enrichment data, etc.)
* Physical units (via pint) need to be managed
* Automatic validation and type checking is required
* Values need to be traceable (status, data source)
* Missing values should be supplemented via user interaction (Decisions)

### Python properties
Python properties are created using the inbuilt decorator `@property`. Properties should be used when:

* None of the features by the bim2sim `attribute` system is needed
* Computed values should be determined on-demand
* Getter/setter logic is needed
* Attribute-like access to methods is desired
* Validation or transformation is necessary when reading/writing

Example for the usage of property:
```python
class Circle:
    def __init__(self, radius):
        self._radius = radius
    
    @property
    def area(self):
        return 3.14 * self._radius ** 2
    
    @property
    def radius(self):
        return self._radius
        
    @radius.setter
    def radius(self, value):
        if value < 0:
            raise ValueError("Radius must be positive")
        self._radius = value
```

### Class attributes
* When every instance of the class has the same value 
* When you want to share the value of this attribute through all instances of this class

An example would be the counter of created instances of this class:
```python
class MyClass:
    instance_count = 0

    def __init__(self):
        MyClass.instance_count += 1
```

### Instance attributes
* If every instance of the class should have it's own value
* If the value is always needed and will stay the same for the lifetime of the 
object
The most common way is to put information into instance attributes by add a 
value or the link to a method to calculate this value to the `__init__` function:
```python
class MyElement(element):
    def __init__(self, value):
        self.value = value  # constant instance attribute
        self.value_2 = self.calc_valuve_2()

    def calc_value_2(self):
        return 1+2
```
