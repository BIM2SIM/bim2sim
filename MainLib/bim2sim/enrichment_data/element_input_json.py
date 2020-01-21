from bim2sim.decision import BoolDecision, ListDecision


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


def load_element_class(instance, dataclass):
    """
    this function fills a data class object, with the information found in the
    enrichment data, based on the class, parameter and parameter value.
    """

    ele_class = str(instance.__class__)[
                str(instance.__class__).rfind(".") + 1:str(instance.__class__).rfind("'")]
    binding = dict(dataclass.element_bind)
    if ele_class in binding:
        attrs_enrich = dict(binding[ele_class])
        del attrs_enrich["class"]
    else:
        return {}

    # check if element has enrich parameter-value?
    for enrich_parameter in attrs_enrich:
        if hasattr(instance, enrich_parameter):
            if getattr(instance, enrich_parameter) in attrs_enrich[enrich_parameter]:
                return attrs_enrich[enrich_parameter][str(getattr(instance, enrich_parameter))]

    return attrs_enrich
