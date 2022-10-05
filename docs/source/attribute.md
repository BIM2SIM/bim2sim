(attribute)=
# Attribute
## Which problem is addressed by attributes?
To parametrize simulation models different types of parameters are needed. A 
BIM model and specifically an IFC model offers multiple sources for the 
requested information. Let's assume that we need the net area of a wall. This 
information can either be obtained from:
* the official IFC specified `QuantitySet` 'Qto_WallBaseQuantities/NetSideArea'
* the unofficial, but typical in ArchiCAD used 'BaseQuantities'/NetSideArea'
* any other PropertySet where the BIM modeller might have stored the information
* the calculation of the Space Boundary area of the wall
* nowhere, because the information simply does not exist in the model (might not be the case for this example)

To resolve this problem of multiple available sources and even parameters which
will be not included in the model at all the `Attribute` system provides a solution.

## How does it work?

