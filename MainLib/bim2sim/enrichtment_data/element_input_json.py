"Loading from element classes - Boiler"

def load_element(element, ele_name, data_class):
#name identification
    binding = data_class.element_bind

    for id, ele in binding.items():
        if id != "version":
# how to generalize for all the elements?
            if ele["name"] == ele_name:

                element.element_id = id
                element.name = ele["name"]
                element.volume = ele["volume"]
                element.nom_power = ele["nom_power"]
                element.efficiency = ele["efficiency"]

def load_element_id(element, ele_id, data_class):
#id identification
    binding = data_class.element_bind

    for id, ele in binding.items():
        if id!= "version":
            #generalization
            if id == ele_id:

                element.element_id = id
                element.name = ele["name"]
                element.volume = ele["volume"]
                element.nom_power = ele["nom_power"]
                element.efficiency = ele["efficiency"]



