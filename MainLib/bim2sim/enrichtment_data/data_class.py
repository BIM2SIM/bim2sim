import os
import sys
import json
import project


v = sys.version_info
if v >= (2, 7):
    try:
        FileNotFoundError
    except:
        FileNotFoundError = IOError

project = project.PROJECT

class DataClass(object):
#todo @dco short docu
    def __init__(self, used_param='1'):

        self.used_parameters = used_param
        self.element_bind = None
        if self.used_parameters == '1':
            self.path_te = os.path.join(project.source, 'inputs',
                                        'TypeBuildingElements.json')
            self.load_te_binding()
        elif self.used_parameters is None:
            pass
        self.element_bind = None

    def load_te_binding(self):
        """
          #todo @dco short docu      #te: type element
        :return:
        """

        if self.path_te.endswith("json"):
                try:
                    with open(self.path_te, 'r+') as f:
                        self.element_bind = json.load(f)
                except json.decoder.JSONDecodeError:
                    print("Your TypeElements file seems to be broken.")
        else:
            print("Your TypeElements file has the wrong format.")




