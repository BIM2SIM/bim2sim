def load_element_ifc(element, ele_ifc, year, dataclass):
    """
    this function fills a data class object, with the information found in the
    enrichment data, based on the ifc type and year.
    """
    binding = dataclass.element_bind
    for a in binding:
        if binding[a]["ifc_type"] == ele_ifc:
            for b in binding[a]["statistical_year"]:
                if b == str(year):
                    for c in binding[a]["statistical_year"][b]:
                        setattr(element, str(c),
                                binding[a]["statistical_year"][b][c])

def load_element_class(element, ele_class, year, dataclass):
    """
    this function fills a data class object, with the information found in the
    enrichment data, based on the class and year.
    """
    binding = dataclass.element_bind
    for a in binding:
        if binding[a]["class"] == ele_class:
            for b in binding[a]["statistical_year"]:
                if b == str(year):
                    for c in binding[a]["statistical_year"][b]:
                        setattr(element, str(c),
                                binding[a]["statistical_year"][b][c])
