from bim2sim.decision import DictDecision, BoolDecision, ListDecision


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
    # 1. check if want to enrich instance
    first_decision = BoolDecision(
        question="Do you want for %s_%s to be enriched" % (instance.ifc_type, instance.guid),
        collect=False)
    first_decision.decide()
    first_decision.collection.clear()
    first_decision.stored_decisions.clear()
    if not first_decision.value:
        return {}

    ele_class = str(instance.__class__)[
                str(instance.__class__).rfind(".") + 1:str(instance.__class__).rfind("'")]
    binding = dataclass.element_bind
    attrs_enrich = binding[ele_class]
    del attrs_enrich["class"]

    # 2. check if element has enrich parameter-value?
    for enrich_parameter in attrs_enrich:
        if hasattr(instance, enrich_parameter):
            if getattr(instance, enrich_parameter) in attrs_enrich[enrich_parameter]:
                return attrs_enrich[enrich_parameter][str(getattr(instance, enrich_parameter))]

    # 3. check if general enrichment - construction year
    general_decision = BoolDecision(
        question="Do you want for this instance to be enriched by construction year %s" % instance.enrich_parameter,
        collect=False)
    general_decision.decide()
    general_decision.collection.clear()
    general_decision.stored_decisions.clear()
    if general_decision.value:
        if "statistical_year" in attrs_enrich:
            if instance.enrich_parameter in attrs_enrich["statistical_year"]:
                return attrs_enrich["statistical_year"][instance.enrich_parameter]

    # 4. ask for enrichment parameter and values
    options = {}
    options_enrich_parameter = list(attrs_enrich.keys())
    # no enrichment exists
    if len(options_enrich_parameter) < 1:
        return {}
    # only one enrich_parameter
    elif len(options_enrich_parameter) == 1:
        options_parameter_value = list(attrs_enrich[options_enrich_parameter[0]])
        if len(options_parameter_value) == 1:
            return attrs_enrich[options_enrich_parameter[0]][options_parameter_value[0]]
        else:
            for i in range(len(options_parameter_value)):
                options[options_enrich_parameter[0], i] = options_parameter_value[i]
            decision = DictDecision("Multiple possibilities found",
                                    choices=options,
                                    output_key="enrich_parameter",
                                    global_key="%s_%s.Enrich_Parameter" % (instance.ifc_type, instance.guid),
                                    allow_skip=True, allow_load=True, allow_save=True,
                                    collect=False, quick_decide=not True)
            decision.decide()
            return attrs_enrich[options_enrich_parameter[0]][str(decision.value)]
    # many enrich parameter
    else:
        for i in range(len(options_enrich_parameter)):
            options["Enrich Parameter", i] = options_enrich_parameter[i]
        decision1 = DictDecision("Multiple possibilities found",
                                 choices=options,
                                 output_key="enrich_parameter",
                                 global_key="%s_%s.Enrich_Parameter" % (instance.ifc_type, instance.guid),
                                 allow_skip=True, allow_load=True, allow_save=True,
                                 collect=False, quick_decide=not True)
        decision1.decide()
        value_d1 = decision1.value
        decision1.collection.clear()
        decision1.stored_decisions.clear()
        options_parameter_value = list(attrs_enrich[value_d1])
        # one parameter value
        if len(options_parameter_value) == 1:
            return attrs_enrich[value_d1][options_parameter_value[0]]
        # many parameter values
        else:
            options = {}
            for i in range(len(options_parameter_value)):
                options[value_d1, i] = options_parameter_value[i]
            decision2 = DictDecision("Multiple possibilities found",
                                     choices=options,
                                     output_key=".Parameter_Value",
                                     global_key="%s_%s.Parameter_Value" % (instance.ifc_type, instance.guid),
                                     allow_skip=True, allow_load=True, allow_save=True,
                                     collect=False, quick_decide=not True)
            decision2.decide()
            return attrs_enrich[str(decision1.value)][str(decision2.value)]

