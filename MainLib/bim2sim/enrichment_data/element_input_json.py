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

    name = "propiedad"
    enrich_values = {}
    value = {}
    choices = [
        ("p1", "diameter"),
        ("p2", "diameter"),
        ("p1", "ancho")
    ]
    values = [3, 2, 7]
    ot = dict(zip(choices, values))
    # check if element has enrich parameter-value?
    for enrich_parameter in attrs_enrich:
        if hasattr(instance, enrich_parameter):
            if getattr(instance, enrich_parameter) in attrs_enrich[enrich_parameter]:
                enrich_values = attrs_enrich[enrich_parameter][str(getattr(instance, enrich_parameter))]
        else:
            decision = DictDecision("Multiple possibilities found",
                                    choices=ot,
                                    output=enrich_values,
                                    output_key=enrich_parameter,
                                    global_key="%s_%s.%s" % (instance.ifc_type, instance.guid, name),
                                    allow_skip=True, allow_load=True, allow_save=True,
                                    collect=False, quick_decide=not True)
            decision.decide()
            value = decision.value

    # if not:

    # which enrich_parameter?
    # which parameter value?
    print("")

    return value
    # return enrich_values

