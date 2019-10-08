from bim2sim.enrichment_data.data_class import DataClass, Enrich_class
from bim2sim.workflow import Workflow


def load_element_ifc(element, ele_ifc, enrich_parameter, parameter_value, dataclass):
    """
    this function fills a data class object, with the information found in the
    enrichment data, based on the ifc type and year.
    """
    binding = dataclass.element_bind
    for a in binding:
        if binding[a]["ifc_type"] == ele_ifc:
            for b in binding[a][enrich_parameter]:
                if b == str(parameter_value):
                    for c in binding[a][enrich_parameter][b]:
                        setattr(element, str(c),
                                binding[a][enrich_parameter][b][c])


def load_element_class(element, ele_class, enrich_parameter, parameter_value, dataclass):
    """
    this function fills a data class object, with the information found in the
    enrichment data, based on the class, parameter and parameter value.
    """
    binding = dataclass.element_bind
    for a in binding:
        if binding[a]["class"] == ele_class:
            for b in binding[a][enrich_parameter]:
                if b == str(parameter_value):
                    for c in binding[a][enrich_parameter][b]:
                        setattr(element, str(c),
                                binding[a][enrich_parameter][b][c])


def enrich_by(attrs_enrich, instance, decisions):
    """
    this function compare the information found on the enrichment file and add it
    to the instances to be enriched, in case the instance doesn't have the corresponding
    attribute
    """
    n_instance = 0
    n_attribute = 0
    if bool(attrs_enrich) is True:
        attrs_instance = {}
        for a in instance.__dir__():
            if a in attrs_enrich:
                attrs_instance[a] = getattr(instance, a)

        for prop in attrs_instance:
            if bool(attrs_enrich) is True:
                if attrs_instance[prop] is None:
                    if not attrs_enrich[prop] is None:
                        setattr(instance, prop + "_enriched", attrs_enrich[prop])
                        decisions.write("-------------the attribute %s from %s enriched successfully\n" % (prop, attrs_instance["name"]))
                        n_attribute += 1
                    else:
                        decisions.write("The enrichment attribute %s from %s is "
                                         "missing or doesn´t exist in the enrichment file\n" % (prop, attrs_instance["name"]))
            else:
                decisions.write("There's no enrichment data for the attribute %s from %s\n" % (prop, attrs_instance["name"]))
    else:
        decisions.write("No enrichment parameters for the instance %s\n" % instance.name)

    if n_attribute != 0:
        n_instance = 1
    return n_attribute, n_instance
