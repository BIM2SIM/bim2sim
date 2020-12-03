from ClassRegistry import ifc_class, ifc_abstract_class
from IfcBase import IfcEntity, BOOLEAN, REAL, BINARY, INTEGER, NUMBER, STRING, LOGICAL
from Misc import parse_uuid

@ifc_class
class time_stamp_text(STRING):
    pass

@ifc_class
class schema_name(STRING):
    pass

@ifc_class
class context_name(STRING):
    pass

@ifc_class
class exchange_structure_identifier(STRING):
    pass

@ifc_class
class section_name(exchange_structure_identifier):
    pass

@ifc_class
class language_name(exchange_structure_identifier):
    pass


@ifc_class
class SECTION_CONTEXT(IfcEntity):
    def __init__(self, rtype, args):
        IfcEntity.__init__(self, rtype, args)
        self.section = args.pop()
        self.context_identifiers = args.pop()

    def __str__(self):
        return "{sup}:section:{section}:context_identifiers:{context_identifiers}".format(
                sup=IfcEntity.__str__(self),
                section=self.section,
                context_identifiers=self.context_identifiers,
                )


@ifc_class
class SCHEMA_POPULATION(IfcEntity):
    def __init__(self, rtype, args):
        IfcEntity.__init__(self, rtype, args)
        self.external_file_identifications = args.pop()

    def __str__(self):
        return "{sup}:external_file_identifications:{external_file_identifications}".format(
                sup=IfcEntity.__str__(self),
                external_file_identifications=self.external_file_identifications,
                )


@ifc_class
class FILE_NAME(IfcEntity):
    def __init__(self, rtype, args):
        IfcEntity.__init__(self, rtype, args)
        self.name = args.pop()
        self.time_stamp = args.pop()
        self.author = args.pop()
        self.organization = args.pop()
        self.preprocessor_version = args.pop()
        self.originating_system = args.pop()
        self.authorization = args.pop()

    def __str__(self):
        return "{sup}:name:{name}:time_stamp:{time_stamp}:author:{author}:organization:{organization}:preprocessor_version:{preprocessor_version}:originating_system:{originating_system}:authorization:{authorization}".format(
                sup=IfcEntity.__str__(self),
                name=self.name,
                time_stamp=self.time_stamp,
                author=self.author,
                organization=self.organization,
                preprocessor_version=self.preprocessor_version,
                originating_system=self.originating_system,
                authorization=self.authorization,
                )


@ifc_class
class FILE_POPULATION(IfcEntity):
    def __init__(self, rtype, args):
        IfcEntity.__init__(self, rtype, args)
        self.governing_schema = args.pop()
        self.determination_method = args.pop()
        self.governed_sections = args.pop()

    def __str__(self):
        return "{sup}:governing_schema:{governing_schema}:determination_method:{determination_method}:governed_sections:{governed_sections}".format(
                sup=IfcEntity.__str__(self),
                governing_schema=self.governing_schema,
                determination_method=self.determination_method,
                governed_sections=self.governed_sections,
                )


@ifc_class
class FILE_DESCRIPTION(IfcEntity):
    def __init__(self, rtype, args):
        IfcEntity.__init__(self, rtype, args)
        self.description = args.pop()
        self.implementation_level = args.pop()

    def __str__(self):
        return "{sup}:description:{description}:implementation_level:{implementation_level}".format(
                sup=IfcEntity.__str__(self),
                description=self.description,
                implementation_level=self.implementation_level,
                )


@ifc_class
class SECTION_LANGUAGE(IfcEntity):
    def __init__(self, rtype, args):
        IfcEntity.__init__(self, rtype, args)
        self.section = args.pop()
        self.default_language = args.pop()

    def __str__(self):
        return "{sup}:section:{section}:default_language:{default_language}".format(
                sup=IfcEntity.__str__(self),
                section=self.section,
                default_language=self.default_language,
                )


@ifc_class
class FILE_SCHEMA(IfcEntity):
    def __init__(self, rtype, args):
        IfcEntity.__init__(self, rtype, args)
        self.schema_identifiers = args.pop()

    def __str__(self):
        return "{sup}:schema_identifiers:{schema_identifiers}".format(
                sup=IfcEntity.__str__(self),
                schema_identifiers=self.schema_identifiers,
                )

# vim: set sw=4 ts=4 et:
