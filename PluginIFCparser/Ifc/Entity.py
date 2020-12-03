from ClassRegistry import ifc_definition
from Misc import find_matching_paren_pair

@ifc_definition
class Entity:
    """
    An ENTITY definition in an Express schema
    """

    def __init__(self, classname, defname, defspec, parser):
        self.classname = classname
        self.defname = defname
        
        self.is_abstract = False
        self.supertype_of = None
        self.subtype_of = None

        # try parsing an inheritance specification statement
        while defspec:
            if defspec.startswith("ABSTRACT "):
                self.is_abstract = True
                defspec = defspec[9:].lstrip()
                continue

            if defspec.startswith("SUPERTYPE OF ("):
                (open_pos, close_pos) = find_matching_paren_pair(defspec)
                self.supertype_of = defspec[open_pos + 1:close_pos]
                defspec = defspec[close_pos + 1:].lstrip()
                continue

            if defspec.startswith("SUBTYPE OF ("):
                (open_pos, close_pos) = find_matching_paren_pair(defspec)
                self.subtype_of = defspec[open_pos + 1:close_pos]
                defspec = defspec[close_pos + 1:].lstrip()
                continue

            raise SyntaxError("Cannot interpret defspec '{val}' in Type {n}".format(val=defspec, n=self.defname))

        # parse the body
        current_section = "DECLARATION"
        self.clauses = {current_section: []} # key: 'DECLARATION', 'INVERSE', 'DERIVE', 'UNIQUE', 'WHERE', value: []
        s = ""
        while True:
            if not s:
                s = parser.read_statement(permit_eof=False, zap_whitespaces=True)
            if s == "END_ENTITY":
                break

            # try catching the section headers
            if s.startswith("INVERSE "):
                current_section = "INVERSE"
                s = s[8:]
                continue

            if s.startswith("DERIVE "):
                current_section = "DERIVE"
                s = s[7:]
                continue

            if s.startswith("UNIQUE "):
                current_section = "UNIQUE"
                s = s[7:]
                continue

            if s.startswith("WHERE "):
                current_section = "WHERE"
                s = s[6:]
                continue

            # try splitting the clause to 'clausename: clausebody'
            colon_pos = s.find(":")
            if colon_pos > 0:
                clausename = s[:colon_pos].rstrip()
                if not current_section in self.clauses:
                    self.clauses[current_section] = []

                self.clauses[current_section].append( {
                    "name": clausename,
                    "value": s[colon_pos + 1:].lstrip()
                })
                s = ""
                continue

            # out of ideas
            raise SyntaxError("Cannot interpret body '{val}' in Type {n}".format(val=s, n=self.defname))


    def __str__(self):
        return "Entity({dn}), is_abstract={a}, subtype_of={sub}, supertype_of={sup}\n{decls}".format(
                dn=self.defname,
                a=self.is_abstract,
                sub=self.subtype_of,
                sup=self.supertype_of,
                decls="\n".join(map(lambda d: "\t<{n}:{v}>".format(n=d["name"], v=d["value"]), self.clauses["DECLARATION"])))


# vim: set sw=4 ts=4 et:
