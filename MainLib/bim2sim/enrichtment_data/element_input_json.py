"Loading from element classes - Boiler"


def load_element_ifc(element, ele_ifc, year, data_class):
#ifc identification and year
    binding = data_class.element_bind

    for id, ele in binding.items():
        if id!= "version":
            if ele["ifc_type"] == ele_ifc and ele["statistical_year"] == year:
                if ele_ifc["ifc_type"] == "IfcBoiler":
                    element.element_id = id
                    element.name = ele["name"]
                    element.water_volume = ele["water_volume"]
                    element.min_power = ele["min_power"]
                    element.rated_power = ele["rated_power"]
                    element.efficiency = ele["efficiency"]
                if ele_ifc["ifc_type"] == "IfcPump":
                    element.element_id = id
                    element.name = ele["name"]
                    element.rated_power = ele["rated_power"]
                    element.rated_height = ele["rated_height"]
                    element.rated_volume_flow = ele["rated_volume_flow"]
                    element.diameter = ele["diameter"]
                else:
                    print("No enrichment data stored to this ifc type")



