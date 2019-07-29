import os
import sys
import json
import project
import inspect


v = sys.version_info
if v >= (2, 7):
    try:
        FileNotFoundError
    except:
        FileNotFoundError = IOError

project = project.PROJECT

class Enrich_class(object):
    """
    Data class object, for storing the information obtained from the enrichment
    data (for the enrichment of 1 element)
    """
    pass


class DataClass(object):
    """
    Class for Enrichment method, that loads the enrichment data from a
    file (source_path), it can support various enrichment parameters
    """

    def __init__(self, used_param='1'):

        self.used_parameters = used_param
        self.element_bind = None
        if self.used_parameters == '1':
            self.path_te = os.path.join(project.source, 'inputs',
                                        'TypeBuildingElements.json')
            self.load_te_binding()
        elif self.used_parameters is None:
            self.element_bind = None

    def load_te_binding(self):
        """
        binding from the enrichment data, it can support various formats
        te: Type element
        """

        if self.path_te.endswith("json"):
                try:
                    with open(self.path_te, 'r+') as f:
                        self.element_bind = json.load(f)
                except json.decoder.JSONDecodeError:
                    print("Your TypeElements file seems to be broken.")
        else:
            print("Your TypeElements file has the wrong format.")

    def json_filler(self, year, elements):
        data_update = json.load(open(self.path_te))

        for name_obj, obj in inspect.getmembers(elements):
            if inspect.isclass(obj):
                name = str(obj)[str(obj).find(".") + 1:str(obj).rfind("'")]
                if name not in data_update:
                    if name != "decorators.cached_property":
                        data_update[name] = {}
                        data_update[name]["class"] = name
                        if hasattr(obj, "ifc_type"):
                            data_update[name]["ifc_type"] = obj.ifc_type
                        data_update[name]["statistical_year"] = {}
                        data_update[name]["statistical_year"][year] = {}
                        data_update[name]["statistical_year"][year]["name"] = name + "_enrichment_" + year
                        parameters = obj.__dict__
                        for parameter in parameters:
                            if not (parameter.endswith("__") or parameter == "findables" or parameter == "ifc_type"):
                                data_update[name]["statistical_year"][year][parameter] = 0
                else:
                    if year not in data_update[name]["statistical_year"]:
                        data_update[name]["statistical_year"][year] = {}
                        data_update[name]["statistical_year"][year]["name"] = name + "_enrichment_" + year
                        parameters = obj.__dict__
                        for parameter in parameters:
                            if not (parameter.endswith("__") or parameter == "findables" or parameter == "ifc_type"):
                                data_update[name]["statistical_year"][year][parameter] = 0
                    else:
                        parameters = obj.__dict__
                        for parameter in parameters:
                            if not (parameter.endswith("__") or parameter == "findables" or parameter == "ifc_type"):
                                if parameter not in data_update[name]["statistical_year"][year]:
                                    data_update[name]["statistical_year"][year][parameter] = 0

        print(data_update)

        with open(self.path_te, 'w') as f:
            json.dump(data_update, f, indent=4)




