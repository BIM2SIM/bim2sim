from ClassRegistry import ifc_definition

@ifc_definition
class Function:
    """
    A FUNCTION definition in an Express schema
    NOTE: Parsed only as deep as necessary
    """

    def __init__(self, classname, defname, defspec, parser):
        self.classname = classname
        self.defname = defname
        self.defspec = defspec

        # process body, FIXME: now just skip it
        while True:
            s = parser.read_statement(permit_eof=False, zap_whitespaces=True)
            if s == "END_FUNCTION":
                break

    def __str__(self):
        return "Function({dn}) {ds}".format(dn=self.defname, ds=self.defspec)

# vim: set sw=4 ts=4 et:
