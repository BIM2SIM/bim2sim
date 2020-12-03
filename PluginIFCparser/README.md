# IFC Parser

Yet another parser for ISO 10303-11 / EXPRESS schemas and IFC files.

Yes, I know, IfcOpenShell is a great project, full respect to the team behind it, really, it's just not what I needed and not
how I need it (python hooks, a *working* string un-escaping, etc.), and I don't intend to fix it / mess it up.

So here we are, yet another parser.

This whole IFC thing is ... complex, so this parser can't be much simpler either, only it can contain the complexity so the
caller doesn't have to deal with it.

First of all, there is no such single thing that '*the* IFC format', but there are several versions of it, and each version
is specified by a fully machine-readable schema file. The format of these schema files is described in ISO 10303-11 / EXPRESS,
and these files have the extension `.EXP`.

So, in order to generate an **IFC parser** for a particular version, we need to have its schema file and we need a schema
parser. More precisely, a schema **converter**, that reads the schema and produces the python parser classes for the IFC entity
classes described by it.

The basic syntax of the schemas and of the IFC files is very similar, so the schema converter and the parsers it generates
share quite a lot of code. But you need to process the schema file only once, and then you have the parser that processes the
IFC files directly.

It's in python, so it'll be somewhat slower than the native implementations, and it's a DOM parser, so it'll read the whole
file at once, and this puts a limit on how big files you can process with it.

On the other hand, it's completely automated from the official schema specification to the parsed entity list, so it is as
future-proof as it can be.


## Usage (for the impatient)

Read the IFC 4.1 schema and generate the parser classes from it:

```
./convert_schema.py -s schemas/IFC4x1_FINAL.exp -m Ifc/Ifc_All.py
```

Parse a `.ifc` data file and dump its content, with the header information, in JSON format:

```
./dump_data.py -f data/Template.ifc -H -j
```


## Classes of the converter and the parser


### `Database`

Dirty and ad-hoc, almost as the .ifc file format, but the good part is that all the dirt is contained in this one, the rest
reflect the class hierarchy quite cleanly, without dealing with the wire representation.


### `Misc`

The rest of the auxiliary things that are unrelated of the input format, like wrapper types for extremal value `Omitted`,
`Reference` (they can only be resolved after reading the whole file), and `EnumValue`.

Needed only internally, so you will need to touch it only if you are defining new `IfcWhatever` classes.

Also here is the 'dispatcher'-constructor that takes a string and returns an instance of the appropriate class from it.

For being able to construct instances by their class name (as string), there is a class registry, in `ClassRegistry.py`,
see below.

**IMPORTANT** The constructors of these classes take two args: the resource type and the arg list, and this arg list is in
**reverse** order!

In IFC the subclasses store their specific arguments after the ones of the superclasses, so

* a subclass constructor will start by calling the superclass constructor with the same args, 
* the superclass constructor will *pull* off its args from the start of the original wire-format arglist, and
* leave the rest for the subclass,
* which will parse them as soon as it returned from the superclass constructor

Though pulling elements from the start of a list is possible, but not that cheap as popping off from its end, and it also
requires more typing which means more mistakes.

So the constructor dispatcher simply reverses the list before passing to the appropriate constructor, and this way they can
just use `pop()` in its natural meaning.


### `IfcEntity`

Regardless of its name, `IfcRoot` is **not** the root of all classes, eg.
[IfcRepresentationItem](http://www.buildingsmart-tech.org/ifc/IFC2x4/rc2/html/schema/ifcgeometryresource/lexical/ifcrepresentationitem.htm)
and all its descendants (like
[IfcCartesianPoint](http://www.buildingsmart-tech.org/ifc/IFC2x4/rc2/html/schema/ifcgeometryresource/lexical/ifccartesianpoint.htm))
are completely independent of it.

At the moment, there is no reason for having a common root, but this almost empty class pains me less now than having to
introduce it later when we'll have hundreds of classes.

So here we have it.


### `IfcGenericEntity`

A catch-all for the not-yet-handled types, just stores its arglist without interpreting it.

The goal is that we should never need it, but if there is some not-yet-covered class, it shouldn't stop us from parsing the
rest (and keeping this weirdo as well).


### `Ifc<Whatever>`

Straightforward representations of the IFC types.


### `@ifc_class`, `@ifc_abstract_class`, `@ifc_fallback_class`

These decorators are in `ClassRegistry.py`, and they implicitely register the class when the file is loaded.

This way the class lookup by name is done automatically and as it uses a dict, it is even faster than the manual approach.

Just don't forget to explicitely import your classes in `Database.py` as the module will only be registered when it is loaded,
and will be loaded when it is used, and will be used only if registered :), so an explicite import is needed anyway.

These decorators are intensely used by the classes in `Ifc_All.py`, which is generated from the schema definition files.


## Schema-to-Python converter

Jotting in the parser classes for the > 800 IFC ENTITY types manually is even less fun than how it sounds (trust me, I did it
for 30-some of them while honing the python class representation), and we didn't even mention that the standard evolves, so it
should be performed regularly.

What we need is a tool that eats the express schema file and generates the python parser classes.

That is quite similar to the data parser itself:

|                              | Data Parser               | Schema Converter                   |
| ---------------------------- | ------------------------- | ---------------------------------- |
| the input file               | .ifc data file            | .exp schema file                   |
| the input file defines       | instances                 | entities                           |
| ...like                      | 'Beam123' is an 'IfcBeam' | 'IfcBeam' is an 'ENTITY'           |
| input file syntax            | stepfile format           | express file format                |
| input structure described by | the schema                | [ISO 10303-11](https://en.wikipedia.org/wiki/EXPRESS_(data_modeling_language))| 
| a parser class eats          | data of an instance       | description of a class             |
| a parser class produces      | an output record          | a parser class for the Data Parser |

So the converter parses schema definitions and produces parser classes, that parse data files and produces object instances.

Though .exp syntax differs from the .ifc syntax, but mostly in the small details only (eg. comment markers), so the Schema
Converter is very similar to the Data Parser.

So much similar, that they share quite a lot of code that would've been a shame to duplicate...


### The schema-to-parser conversion process

It starts with the schemas:

* [2.4rc4](http://www.buildingsmart-tech.org/ifc/IFC2x4/rc4/express/IFC4RC4.exp)
* [4.1final](http://www.buildingsmart-tech.org/ifc/IFC4x1/final/IFC4x1_FINAL.exp)

Choose the appropriate version, as *there are incompatible differences* between schema versions,
e.g. `IfcPresentationStyle` in 2.4 had two attributes `Name` and `ModelOrDraughting`, in 4.1 it has only `Name`.

The converter script is `convert_schema.py`, it expects a schema input (`-s schemafile.exp`), and produces a python module
(`-m modulefile.py`):

```
./convert_schema.py -s schemas/IFC4x1_FINAL.exp -m Ifc/Ifc_All.py
```

NOTE: The data files do contain the schema versions they need (eg. `FILE_SCHEMA(('IFC4'));`), so it would be nice to have
several schema versions available and use the appropriate one when reading the file.

However, this will require some major refactoring, like having separate class registries and choose the appropriate one in
runtime, which are still on the *TODO* list.



## The .ifc data parser

Compared to the stuff above, it is simple and straightforward:

* it uses the parser classes defined in `Ifc/Ifc_All.py`
* plus some built-in ones, see at the top
* snoops up the .ifc file statement by statement
* applies the appropriate parser to it
* collects the result
* **IMPLEMENTED UP TO THIS POINT**
* resolves the references
* and here we get all the data in a nice DOM structure

Then we can choose what to do with it
* what to send to the output
* in what format

Until then we can access the entities by their indices:
```
./dump_data.py -f data/Template.ifc -H -j
```

**NOTE**
When dumping objects as plain strings, lists won't call `__str__` of their content,
but their `__repr__`, so we'll get lines like this:

```
27: IFCDERIVEDUNIT:Elements:[<Ifc.IfcBase.Reference instance at 0x2a0fb24c>, <Ifc.IfcBase.Reference instance at 0x2a0fb28c>,
<Ifc.IfcBase.Reference instance at 0x2a0fb2ac>]:UnitType:<.THERMALCONDUCTANCEUNIT.>:UserDefinedType:None
```

It completely defeats the purpose, but this is a known and intended behaviour and it is definitely the most pythonic way,
as [Guido doesn't like the idea of lists calling `__str__`](https://www.python.org/dev/peps/pep-3140/)...

