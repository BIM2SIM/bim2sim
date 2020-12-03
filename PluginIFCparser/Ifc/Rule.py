from ClassRegistry import ifc_definition

@ifc_definition
class Rule:
    """
    A RULE definition in an Express schema
    NOTE: Parsed only as deep as necessary
    """

    def __init__(self, classname, defname, defspec, parser):
        self.classname = classname
        if not defspec.startswith("FOR"):
            raise SyntaxError("Specification of Rul {dn} should start with 'FOR'".format(dn=defname))
        self.defname = defname
        self.defspec = defspec

        # process constraints, FIXME: now just skip them
        while True:
            s = parser.read_statement(permit_eof=False, zap_whitespaces=True)
            if s == "END_RULE":
                break

    def __str__(self):
        return "Rule({dn}) {ds}".format(dn=self.defname, ds=self.defspec)

# vim: set sw=4 ts=4 et:
