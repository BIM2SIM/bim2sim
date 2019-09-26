import os
import sys
import json
from bim2sim.project import PROJECT as project
import inspect

v = sys.version_info
if v >= (2, 7):
    try:
        FileNotFoundError
    except:
        FileNotFoundError = IOError

# elements_data = inspect.getmembers(elements)


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

    def json_filler(self, elements_data):
        data_update = json.load(open(self.path_te))
        default = None
        new_data = dict(data_update)
        for a in data_update:
            for b in data_update[a]:
                if b != "class" and b != "ifc_type":
                    for c in data_update[a][b]:
                        for obj in elements_data:
                            name = obj
                            if inspect.isclass(elements_data[obj]):
                                if name not in new_data:
                                    if name != "cached_property":
                                        new_data[name] = {}
                                        new_data[name]["class"] = name
                                        if hasattr(obj, "ifc_type"):
                                            new_data[name]["ifc_type"] = elements_data[obj].ifc_type
                                        new_data[name][b] = {}
                                        new_data[name][b][c] = {}
                                        new_data[name][b][c]["name"] = name + "_enrichment_" + c
                                        parameters = elements_data[obj].findables
                                        for parameter in parameters:
                                            new_data[name][b][c][parameter] = default
                                else:
                                    if b not in new_data[name]:
                                        new_data[name][b] = {}
                                    if c not in new_data[name][b]:
                                        new_data[name][b][c] = {}
                                        new_data[name][b][c]["name"] = name + "_enrichment_" + c
                                        parameters = elements_data[obj].findables
                                        for parameter in parameters:
                                            new_data[name][b][c][parameter] = default
                                    else:
                                        parameters = elements_data[obj].findables
                                        for parameter in parameters:
                                            if parameter not in new_data[name][b][c]:
                                                new_data[name][b][c][parameter] = default

        with open(self.path_te, 'w') as f:
            json.dump(new_data, f, indent=4)




