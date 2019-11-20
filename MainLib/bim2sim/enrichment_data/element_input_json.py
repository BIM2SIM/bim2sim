from bim2sim.decision import DictDecision


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
    attrs_enrich = {}
    ele_class = str(instance.__class__)[
                str(instance.__class__).rfind(".") + 1:str(instance.__class__).rfind("'")]
    binding = dataclass.element_bind

    for a in binding:
        if binding[a]["class"] == ele_class:
            for b in binding[a]:
                if isinstance(binding[a][b], dict):
                    attrs_enrich[b] = {}
                    for c in binding[a][b]:
                        attrs_enrich[b][c] = binding[a][b][c]

    x = 0
    x.properties = []
    x.ifc_type = "Ifc"
    x.guid = "0041"
    name = "hola"
    enrich_values = {}
    # check if element has enrich parameter-value?
    for enrich_parameter in attrs_enrich:
        if hasattr(instance, enrich_parameter):
            if getattr(instance, enrich_parameter) in attrs_enrich[enrich_parameter]:
                enrich_values = attrs_enrich[enrich_parameter][str(getattr(instance, enrich_parameter))]
        # else:
        #     decision = DictDecision("Multiple possibilities found",
        #                             choices=attrs_enrich,
        #                             output=x.properties,
        #                             output_key=name,
        #                             global_key="%s_%s.%s" % (x.ifc_type, x.guid, name),
        #                             allow_skip=True, allow_load=True, allow_save=True)
        #                             # collect=collect_decisions, quick_decide=not collect_decisions)

    # if not:
    # which enrich_parameter?
    # which parameter value?
    print("")
    return enrich_values

