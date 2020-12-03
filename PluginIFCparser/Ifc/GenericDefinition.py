from ClassRegistry import ifc_fallback_definition

@ifc_fallback_definition
class GenericDefinition:
    """
    Generic catch-all type for unhandled classes in an Express schema
    """

    def __init__(self, classname, defname, defspec, parser):
        self.classname = classname
        self.defname = defname
        self.defspec = defspec

    def __str__(self):
        return "Gen<{cn}>({dn}) {ds}".format(cn=self.classname, dn=self.defname, ds=self.defspec)

# vim: set sw=4 ts=4 et:
