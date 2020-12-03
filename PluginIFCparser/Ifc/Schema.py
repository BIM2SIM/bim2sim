from ClassRegistry import ifc_definition

@ifc_definition
class Schema:
    """
    An Express schema containing various classes of definitions

    Here 'classes' refer to the top-level entities of the schema:
    - TYPE: enumeration or aliased data types
    - ENTITY: type class declaration
    - FUNCTION:
    - RULE:

    These are stored in a 2-level map, the 1st level being the 'class'
    and the 2nd level being the name of the definition, eg.:

    - self.classes["TYPE"]["IfcTextAlignment"] = an instance of 'Type' class
    - self.classes["ENTITY"]["IfcCartesianPoint"] = an instance of 'Entity' class
    - and so on

    The class 'GenericDefinition' acts as fallback while parsing, it
    catches any definition without interpreting its content.
    """

    def __init__(self, classname, defname, defspec, parser):
        self.classname = classname
        self.defname = defname
        self.classes = {}

        while True:
            s = parser.read_statement(permit_eof=False, zap_whitespaces=True)
            if s == "END_SCHEMA":
                break

            d = parser.parse_definition(s)
            if not d.classname in self.classes:
                self.classes[d.classname] = {}

            self.classes[d.classname][d.defname] = d


    def __str__(self):
        return "Schema({dn})".format(dn=self.defname)

# vim: set sw=4 ts=4 et:
