def load_element_ifc(element, ele_ifc, year, dataclass):
    """
    this function fills a data class object, with the information found in the
    enrichment data, based on the ifc type and year.
    """
    binding = dataclass.element_bind
    for a, b in binding.items():
        if a != 'version':
            if b["statistical_year"] == year and b["ifc_type"] == ele_ifc:
                for c,d in b.items():
                    setattr(element, str(c), d)