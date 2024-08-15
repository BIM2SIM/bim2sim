(elements_structure)=

# Elements

## Functionality

As we want to provide the generation of models for multiple simulation tools and
domains, we don't go with a direct 1:1 mapping of IFC to simulation models.
Instead, we created the `elements` structure that allows us to gather relevant
information from different sources in the IFC and store them in a structure that
is created with the specific goal to parametrize simulation models.

## Mapping

The general steps of mapping IFC entity to element class are divided as follows.

1. selecting the element class according to `IfcType` or `PredefinedType` of the
   IFC
   entity.
2. validation of the properties of the Ifc entity according to the requirements
   of the element class (final, if validation successful)
3. validation of properties like name and description of the Ifc entity based on
   regular expressions, whether other element class is applicable
4. determine the element class via [decision](decisions) system, if no or
   several classes come into question.
5. possibly specify the class later based on additional information

When mapping IFC to a simulation orientated structure three types of mapping
occur:

* 1:many (1 IFC type is mapped to multiple `elements`)
* many:1 (multiple IFC types are mapped to 1 `element`)
* 1:1 mapping (1 IFC type is mapped to 1 `element`)

The more complicated first two cases are described with an example below.

### 1:many Mapping

For simple explanation lets use the `IfcWall`. In simulation environments for
BPS we need to differ between inner walls and outer walls. In IFC this is done
by a property which might be found `isExternal` in the corresponding
PropertySet `Pset_WallCommon` as it's optional. We can also use relating
SpaceBoundary to find if the wall is external or internal. But in any way we
need to map it into two different `bim2sim` classes: `InnerWall`
and `OuterWall`.
This would be a 1:many mapping. Another example would be 'IfcSlab' which can be
a `Roof`, `Floor` or `GroundFloor` in the simulation world depending on their
`PredefinedType` in IFC.

### many:1 Mapping

A good example for many:1 is the `Roof` class of `bim2sim`. Depending on it's
predefined type either the `IfcSlab` or `IfcRoof` can be a `Roof` instance for
simulation.

## Element Types

We created different element types for different purposes. The most relevant
base classes are:

* [IFCBased](IFCBased)
* [RelationBased](RelationBased)
* [ProductBased](ProductBased)

`IfcBased` is the base class that defines how to handle the mapping between IFC
and `bim2sim`.
`RelationBased` covers non `IfcProduct` types like `IfcRelSpaceBoundary`
or `IfcDistributionPort`, while `IfcProductBased` covers all IFC entities that
inherit `IfcProduct`.
For detailed information please have a look at the code documentation
of [elements](element). The way we gather the information in a uniform way is
described in [attributes](attributes).
