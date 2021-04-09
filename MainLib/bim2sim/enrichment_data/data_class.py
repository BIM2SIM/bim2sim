import os
import sys
import json
from pathlib import Path

import bim2sim

v = sys.version_info
if v >= (2, 7):
    try:
        FileNotFoundError
    except:
        FileNotFoundError = IOError

# elements_data = inspect.getmembers(elements)


class DataClass(object):
    """
    Class for Enrichment method, that loads the enrichment data from a
    file (source_path), it can support various enrichment parameters
    """
    assets = Path(bim2sim.__file__).parent / 'assets'

    def __init__(self, used_param):

        self.used_parameters = used_param
        self.element_bind = None
        if self.used_parameters == 1:
            self.path_te = self.assets / 'enrichment' / 'TypeBuildingElements.json'
            self.load_te_binding()
        elif self.used_parameters == 2:
            self.path_te = os.path.join(self.assets, 'MaterialTemplates',
                                        'MaterialTemplates.json')
            # self.path_te = project.assets / 'MaterialTemplates' / 'MaterialTemplates.json'
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

