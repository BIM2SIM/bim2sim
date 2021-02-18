from PluginIFCparser.Ifc.ClassRegistry import ifc_class, ifc_abstract_class, ifc_fallback_class

@ifc_abstract_class
class IfcEntity:
    """
    Generic IFC entity, only for subclassing from it
    """

    def __init__(self, rtype, args):
        """
        rtype: Resource type
        args: Arguments in *reverse* order, so you can just args.pop() from it
        """
        self.rtype = rtype
    
    def __str__(self):
        return self.rtype

    def __json__(self):
        return {'rtype': self.rtype}


@ifc_fallback_class
class IfcGenericEntity(IfcEntity):
    """
    Generic IFC entity: type and args
    """

    def __init__(self, rtype, args):
        IfcEntity.__init__(self, rtype, args)
        self.args = args
        self.args.reverse()
    
    def __str__(self):
        return "Gen<{sup}>{a}".format(
                sup=IfcEntity.__str__(self),
                a=self.args)


@ifc_class
class IfcScalarValue(IfcEntity):
    def __init__(self, rtype, args):
        IfcEntity.__init__(self, rtype, args)
        self.value = args.pop()
    
    def __str__(self):
        return str(self.value)

@ifc_class
class BOOLEAN(IfcScalarValue):
    pass

@ifc_class
class REAL(IfcScalarValue):
    pass

@ifc_class
class BINARY(IfcScalarValue):
    pass

@ifc_class
class INTEGER(IfcScalarValue):
    pass

@ifc_class
class NUMBER(IfcScalarValue):
    pass

@ifc_class
class STRING(IfcScalarValue):
    pass

@ifc_class
class LOGICAL(IfcScalarValue):
    pass

@ifc_class
class ENUM(IfcScalarValue):
    pass


class Omitted:
    """
    Marked with '*' it states that some supertype had defined that attribute, but in the subtype it is a derived
    (calculated) value, so it no longer makes sense to explicitely assign value to it.
    """
    # TODO: Haven't tried if it can be handled 'just as expected'
    def __init__(self):
        pass
    
    def __str__(self):
        return "<omitted>"

    def __json__(self):
        return None

# class-level, enough to reference, no need to create multiple instances (doesn't hurt though)
omitted = Omitted()


class Reference:
    """
    Refers to another entity by its index
    """
    def __init__(self, index):
        self.index = index

    def __str__(self):
        return "<#{idx}>".format(idx=self.index)

    def __json__(self):
        return {'ref': self.index}


class EnumValue:
    """
    Item from some set of enumerated values.
    """
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return "<.{val}.>".format(val=self.value)

    def __json__(self):
        return self.value

@ifc_class
class STEPHeader(IfcEntity):
    def __init__(self):
        IfcEntity.__init__(self, "STEPHeader", [])
        self.fields = {}

    def add(self, e):
        self.fields[e.rtype] = e

    def __str__(self):
        return "STEPHeader({f})".format(f=", ".join(map(lambda f: "{n}: {v}".format(n=f[0], v=str(f[1])), self.fields.iteritems())))


# vim: set sw=4 ts=4 et:
