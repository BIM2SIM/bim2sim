classes = dict()
definitions = dict()

def ifc_class(cls):
    """
    Decorator for implicitely registering an IFC class
    """
    classes[cls.__name__.upper()] = cls
    return cls


def ifc_abstract_class(cls):
    """
    Decorator for implicitely registering an abstract IFC class
    NOTE: for testing we register them too
    """
    classes[cls.__name__.upper()] = cls
    return cls


def ifc_fallback_class(cls):
    """
    Decorator for the fallback class
    """

    if "*" in classes:
        raise ImportError("Already registered {oc} as fallback, cannot register {nc}".format(
            oc=classes["*"].__name__,
            nc=cls.__name__))
    classes["*"] = cls
    return cls


def create_entity(rtype, args):
    if rtype in classes:
        return classes[rtype](rtype, args)

    if not "*" in classes:
        raise SyntaxError("Cannot create {nc} and there is no fallback class".format(nc=rtype))
    return classes["*"](rtype, args)


def ifc_definition(cls):
    """
    Decorator for implicitely registering an IFC definition
    """
    definitions[cls.__name__.upper()] = cls
    return cls


def ifc_fallback_definition(cls):
    """
    Decorator for the fallback class
    """

    if "*" in definitions:
        raise ImportError("Already registered {oc} as fallback, cannot register {nc}".format(
            oc=definitions["*"].__name__,
            nc=cls.__name__))
    definitions["*"] = cls
    return cls


def create_definition(classname, defname, defspec, parser):
    x = definitions
    if classname in definitions:
        x = definitions[classname](classname, defname, defspec, parser)
        return x

    if not "*" in definitions:
        raise SyntaxError("Cannot create {nc} and there is no fallback definition".format(nc=classname))
    return definitions["*"](classname, defname, defspec, parser)

# vim: set sw=4 ts=4 et:
