import ifcopenshell
import uuid
from bim2sim.decision import ListDecision, BoolDecision, TextDecision, DictDecision


def get_all_property_sets(element):
    sets = {'Property_Sets': {},
            'Quantity_Sets': {}}

    for p_set in element.IsDefinedBy:
        if hasattr(p_set, 'RelatingPropertyDefinition'):
            name = p_set.RelatingPropertyDefinition.Name
            props = []
            if hasattr(p_set.RelatingPropertyDefinition, 'HasProperties'):
                for p in p_set.RelatingPropertyDefinition.HasProperties:
                    props.append(p.Name)
                sets['Property_Sets'][name] = props
            elif hasattr(p_set.RelatingPropertyDefinition, 'Quantities'):
                for p in p_set.RelatingPropertyDefinition.Quantities:
                    props.append(p.Name)
                sets['Quantity_Sets'][name] = props
    return sets


def get_property(element, property_set, property_name):
    data = None
    for PropertySet in element.IsDefinedBy:
        if PropertySet.RelatingPropertyDefinition.Name == property_set:
            if hasattr(PropertySet.RelatingPropertyDefinition, 'HasProperties'):
                for Property in PropertySet.RelatingPropertyDefinition.HasProperties:
                    if Property.Name == property_name:
                        data = Property
                        break
            if hasattr(PropertySet.RelatingPropertyDefinition, 'Quantities'):
                for Property in PropertySet.RelatingPropertyDefinition.Quantities:
                    if Property.Name == property_name:
                        data = Property
                        break

    return data


def get_set(element, property_set):
    data = None
    for PropertySet in element.IsDefinedBy:
        if PropertySet.RelatingPropertyDefinition.Name == property_set:
            data = PropertySet.RelatingPropertyDefinition

    return data


def ifc_instance_overwriter(ifc_file):
    """modifies the IfcProperty of a selected Instance, and creates a new ifc file with those changes"""
    ifc_switcher = {bool: 'IfcBoolean',
                    str: 'IfcText',
                    float: 'IfcReal',
                    int: 'IfcInteger'}
    quantity_switcher = {'Volume': ifc_file.createIfcQuantityVolume,
                         'Area': ifc_file.createIfcQuantityArea,
                         'Length': ifc_file.createIfcQuantityLength}

    owner_history = ifc_file.by_type("IfcOwnerHistory")[0]

    options_by = ["by_guid", "by_type"]
    by_decision = ListDecision("Select the method to search for an element:",
                               global_key='Instance finder',
                               choices=options_by,
                               allow_skip=False,
                               allow_load=True)
    by = by_decision.decide()
    value = str(input("Insert value for the %s Method:" % by))

    finder = getattr(ifc_file, by)
    try:
        element = finder(value)
    except RuntimeError:
        element = None

    if type(element) is list:
        elements_options = {i.Name: i.GlobalId for i in element}
        element_decision = DictDecision("Select the element to change:",
                                        global_key='Element GUID',
                                        choices=elements_options,
                                        allow_skip=False,
                                        allow_load=True)
        element = ifc_file.by_guid(element_decision.decide())

    if element is not None:
        property_set = str(input("Insert name for the property set"))
        property_name = str(input("Insert name for the property"))
        property_value = input("Insert value for the property")
        ifc_instance_overwriter(element, property_set, property_name, property_value, ifc_file)

        sets = get_all_property_sets(element)
        type_value_in_element = ifc_switcher.get(type(property_value))

        # quantity set overwrite
        if property_set in sets['Quantity_Sets']:
            # property overwrite:
            if property_name in sets['Quantity_Sets'][property_set]:
                property_to_edit = get_property(element, property_set, property_name)
                for attr, property_value in vars(property_to_edit).items():
                    if attr.endswith('Value'):
                        attr_to_edit = attr
                        break
                setattr(property_to_edit, attr_to_edit, property_value)
            # new property
            else:
                set_to_edit = get_set(element, property_set)
                quantity_function = ifc_file.createIfcQuantityLength
                for dimension in quantity_switcher:
                    if dimension in property_name:
                        quantity_function = quantity_switcher.get(dimension, ifc_file.createIfcQuantityLength)
                    new_quantity = quantity_function(property_name, None, None, property_value)
                    edited_quantities_set = list(set_to_edit.Quantities)
                    edited_quantities_set.append(new_quantity)
                    set_to_edit.Quantities = tuple(edited_quantities_set)
        # property set overwrite
        elif property_set in sets['Property_Sets']:
            # property overwrite:
            if property_name in sets['Property_Sets'][property_set]:
                property_to_edit = get_property(element, property_set, property_name)
                try:
                    property_to_edit.NominalValue.wrappedValue = property_value
                except ValueError:  # double, boolean, etc error
                    pass
            # new property
            else:
                set_to_edit = get_set(element, property_set)
                new_property = ifc_file.createIfcPropertySingleValue(
                    property_name, None, ifc_file.create_entity(type_value_in_element, property_value),
                    None)
                edited_properties_set = list(set_to_edit.HasProperties)
                edited_properties_set.append(new_property)
                set_to_edit.HasProperties = tuple(edited_properties_set)
        #new property set, new property
        else:
            new_property = ifc_file.createIfcPropertySingleValue(
                property_name, None, ifc_file.create_entity(type_value_in_element, property_value),
                None)
            new_properties_set = ifc_file.createIfcPropertySet(create_guid(), owner_history,
                                                               property_set, None, [new_property])
            ifc_file.createIfcRelDefinesByProperties(create_guid(), owner_history, None, None,
                                                     [element], new_properties_set)


def create_guid():
    return ifcopenshell.guid.compress(uuid.uuid1().hex)


def get_source_tool(instance):
    source_tool = None
    if hasattr(instance, 'source_tool'):
        if instance.source_tool.startswith('Autodesk'):
            source_tool = 'Autodesk Revit 2019 (DEU)'
        elif instance.source_tool.startswith('ARCHICAD'):
            source_tool = 'ARCHICAD-64'
        else:
            instance.logger.warning('No source tool for the ifc file found')
    return source_tool


name_file = "AC20-FZK-Haus.ifc"
ifc_file = ifcopenshell.open(name_file)

decision_bool = BoolDecision("Do you want to add changes to the ifc file %s" % name_file,
                             allow_save=True,
                             allow_load=True)
use = decision_bool.decide()

if use is True:
#     options_by = ["by_guid", "by_type"]
#     by_decision = ListDecision("Select the method to search for an element:",
#                                global_key='Instance finder',
#                                choices=options_by,
#                                allow_skip=False,
#                                allow_load=True)
#     by = by_decision.decide()
#     value = str(input("Insert value for the %s Method:" % by))
#
#     finder = getattr(ifc_file, by)
#     try:
#         element = finder(value)
#     except RuntimeError:
#         element = None
#
#     if type(element) is list:
#         elements_options = {i.Name: i.GlobalId for i in element}
#         element_decision = DictDecision("Select the element to change:",
#                                         global_key='Element GUID',
#                                         choices=elements_options,
#                                         allow_skip=False,
#                                         allow_load=True)
#         element = ifc_file.by_guid(element_decision.decide())
#
#     if element is not None:
#         property_set = str(input("Insert name for the property set"))
#         property_name = str(input("Insert name for the property"))
#         property_value = input("Insert value for the property")
#         ifc_instance_overwriter(element, property_set, property_name, property_value, ifc_file)
    ifc_instance_overwriter(ifc_file)
    s_continue = None
    while s_continue is not False:
        continue_bool = BoolDecision("Do you want to continue changing instances",
                                     allow_save=True,
                                     allow_load=True)
        s_continue = continue_bool.decide()

        if s_continue is True:
            ifc_instance_overwriter(ifc_file)

    ifc_file.write('AC20-FZK-Haus_modified.ifc')





