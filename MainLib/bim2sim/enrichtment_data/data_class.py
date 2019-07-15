import warnings
import xml.etree.ElementTree as et
import os
import sys
import json
import collections
import utilities as utils


v = sys.version_info
if v >= (2, 7):
    try:
        FileNotFoundError
    except:
        FileNotFoundError = IOError

class DataClass(object):

    def __init__(self, used_year='1'):

        self.used_parameters = used_year
        self.element_bind = None
        if self.used_parameters == '1':
            self.path_te = utils.get_full_path("TypeBuildingElements.json")
            self.load_te_binding()
        elif self.used_parameters is None:
            pass
        self.element_bind = None

    def load_te_binding(self): #te: type element
        if self.path_te.endswith("json"):
            self.path_te = os.path.join(
                'D:/01_GitHub/bim2sim-coding/MainLib/bim2sim/enrichtment_data')
            if os.path.isfile(self.path_te):
                try:
                    with open(self.path_te, 'r+') as f:
                        self.element_bind = json.load(f)
                except json.decoder.JSONDecodeError:
                    print("Your TypeElements file seems to be broken.")
            else:
                with open(self.path_te, 'w') as f:
                    self.element_bind = collections.OrderedDict()
                    self.element_bind["version"] = "0.7"
        else:
            print("Your TypeElements file has the wrong format.")




