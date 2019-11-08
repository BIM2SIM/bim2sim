import inspect

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


def load_element_class(instance, enrich_parameter, parameter_value, dataclass):
    """
    this function fills a data class object, with the information found in the
    enrichment data, based on the class, parameter and parameter value.
    """
    attrs_enrich = {}
    ele_class = str(instance.__class__)[
                         str(instance.__class__).rfind(".") + 1:str(instance.__class__).rfind("'")]
    binding = dataclass.element_bind

    for a in binding:
        if binding[a]["class"] == ele_class:
            for b in binding[a][enrich_parameter]:
                if b == str(parameter_value):
                    for c in binding[a][enrich_parameter][b]:
                        attrs_enrich[str(c)] = binding[a][enrich_parameter][b][c]

    return attrs_enrich



# def finder_enrichment(element, name):
