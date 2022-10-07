(attribute)=
# Attribute
## Which problem is addressed by attributes?
To parametrize simulation models different types of parameters are needed. A 
BIM model and specifically an IFC model offers multiple sources for the 
requested information. Let's assume that we need the `net_area` of a wall. This 
information can either be obtained from:
* the official IFC specified `QuantitySet` 'Qto_WallBaseQuantities/NetSideArea'
* the unofficial, but typical in ArchiCAD used 'BaseQuantities'/NetSideArea'
* any other PropertySet where the BIM modeller might have stored the information
* the calculation of the Space Boundary area of the wall
* nowhere, because the information simply does not exist in the model (might not be the case for this example)

To resolve this problem of multiple available sources and even parameters which
will be not included in the BIM model at all the `Attribute` system provides a solution.

## Concept / How does it work?
Simulation required informations that are potentially available in the BIM model
are stored in an [Attribute](Attribute) at the corresponding [element](element).

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
use if no information exists in the IFC file. Also so unit in which the value 
should be stored is provided as m².  See [Attributes](Attribute) documentation 
for more detailed description which other ways are implemented to obtain a value.

## How are the attributes managed? 
To manage the different attributes every bim2sim [element](element) instance 
owns an instance of the [AttributeManager](AttributeManager) which is stored under `element.attributes`, 
which manages the values and current status of the [Attributes](Attribute). As
not all needed attribute information might be present inside the IFC we 
implemented the concept of [Decisions](Decision) which is basically a structured
way to obtain information from the user. For more information regarding Decisions
please read the corresponding information. The [AttributeManager](AttributeManager) 
uses the status of each attribute to store if an attribute was already requested. 
To trigger all decisions for the already requested attributes to finally obtain 
the corresponding values the final tasks before exporting to a simulation model
should always trigger the [](get_pending_attribute_decisions) function of
[element](element). 
This implementation was made to bundle the decisions at the end of the process 
if possible. 



