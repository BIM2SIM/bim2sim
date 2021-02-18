from PluginIFCparser.Ifc.ClassRegistry import ifc_definition
import re

@ifc_definition
class Type:
    """
    A TYPE definition in an Express schema
    NOTE: Parsed only as deep as necessary
    """

    def __init__(self, classname, defname, defspec, parser):
        self.classname = classname
        if not defspec.startswith("="):
            raise SyntaxError("Specification of Type {dn} should start with '='".format(dn=defname))
        self.defname = defname
        defspec = defspec[1:].lstrip()

        # don't care about string length
        if defspec.startswith("STRING("):
            defspec = "STRING"

        if defspec.startswith("ARRAY ") or defspec.startswith("LIST ") or defspec.startswith("SET "):
            self.ttype = "LIST"
            # nothing to do, iterative types are implicitely parsed as list
            pass
        elif defspec.startswith("ENUMERATION OF ("):
            self.ttype = "ENUM"
            self.defspec = re.sub('[(,)]', '', defspec.strip('ENUMERATION OF ')).split()
            pass
        elif defspec.startswith("SELECT ("):
            self.ttype = "UNION"
            # doesn't occur either, refs are parsed implicitely
            pass
        else:
            self.ttype = "SCALAR"
            self.basetype = defspec;
            pass

        # process constraints, FIXME: now just skip them
        while True:
            s = parser.read_statement(permit_eof=False, zap_whitespaces=True)
            if s == "END_TYPE":
                break

    def __str__(self):
        return "Type({dn}) {ds}".format(dn=self.defname, ds=self.defspec)

# vim: set sw=4 ts=4 et:
