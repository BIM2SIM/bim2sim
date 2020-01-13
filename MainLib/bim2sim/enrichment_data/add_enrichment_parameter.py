"""Program that allows the user to add new parameters of enrichment to the items on the database
for example: (statistical year, type, heat pump...)"""
import json
from bim2sim.ifc2python import elements
import inspect


elements_data = elements.__dict__


def filler(data_update, enriched_element, parameter, parameter_value):
    """fills the empty spaces which corresponds to the desired
    element, parameter and parameter value"""
    data_update[enriched_element][parameter][parameter_value] = {}
    data_update[enriched_element][parameter][parameter_value]["name"] = enriched_element \
                                                                        + "_enrichment_" + parameter_value
    for obj in elements_data[enriched_element].findables:
        enrichment = obj
        value = input("Enter the value for the enrichment of {} or press enter "
                      "to add \"None\" as default ".format(enrichment))
        if value:
            data_update[enriched_element][parameter][parameter_value][enrichment] = value
        else:
            data_update[enriched_element][parameter][parameter_value][enrichment] = None


def new_enrichment_parameter(file_path):
    """function that adds the information to the json file based on the next structure as an example:
     "Boiler": ------------------------------------------> enriched_element
        "class": "Boiler",
        "ifc_type": "IfcBoiler",
        "statistical_year":------------------------------> parameter
            "2000":--------------------------------------> parameter value
                "name": "Boiler_enrichment_2000",
                "water_volume": 0.008,
                "min_power": 16,
                "rated_power": 16,
                "efficiency": 0.97
        "Heat_pump":------------------------------> parameter
            "2kW":---------------------------------------> parameter value
                "name": "Boiler_enrichment_2kW",
                "water_volume": 0.008,
                "min_power": 16,
                "rated_power": 16,
                "efficiency": 0.97
    """
    enriched_element = None
    elements_available = []
    for element in elements_data:
        if inspect.isclass(elements_data[element]):
            elements_available.append(element)
    while enriched_element is None:
        enriched_element = input("Enter the element to which you would like to add a parameter: ")
        if enriched_element not in elements_data:
            enriched_element = None
            print("The desired element to be enriched is not in the data base,"
                  " try the following elements: \n", ', '.join(elements_available))
    parameter = ""
    parameter_value = ""
    while not parameter:
        parameter = input("Enter the enrichment parameter to add: ")
    while not parameter_value:
        parameter_value = input("Enter the parameter value to add: ")
    data_update = json.load(open(file_path))

    if enriched_element in data_update:
        if parameter in data_update[enriched_element]:
            if parameter_value in data_update[enriched_element][parameter]:
                print("The value for the selected parameter to add, already exists")
            else:
                filler(data_update, enriched_element, parameter, parameter_value)
        else:
            data_update[enriched_element][parameter] = {}
            filler(data_update, enriched_element, parameter, parameter_value)

    else:
        data_update[enriched_element] = {}
        data_update[enriched_element][parameter] = {}
        filler(data_update, enriched_element, parameter, parameter_value)

    with open(file_path, 'w') as f:
        json.dump(data_update, f, indent=4)


path = 'D:\\dja-dco\\Projects\\MainLib\\bim2sim\\inputs\\TypeBuildingElements.json'
new_enrichment_parameter(path)