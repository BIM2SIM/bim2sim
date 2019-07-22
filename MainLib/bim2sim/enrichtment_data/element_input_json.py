"Loading from element classes - Boiler"


def load_element_ifc(element, ele_ifc, year, dataclass):
#ifc identification and year
    binding = dataclass.element_bind
    for a,b in binding.items():
        if a != 'version':
            if b["statistical_year"]== year and b["ifc_type"] == ele_ifc:
                print(b)
                for c,d in b.items():
                    setattr(element, str(c), d)