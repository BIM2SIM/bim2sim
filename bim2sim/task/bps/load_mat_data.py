import scipy.io
from ebcpy.data_types import TimeSeriesData
import json

#t = ebcpy.modelica.simres.loadsim(mat_file, constants_only=False)

class Bim2simInterface(object):

    def __init__(self,
                 mat_file,
                 json_file):
        """

        Args:
            mat_file ():
            json_file ():
        """
        self.mat_file = mat_file
        self.json_file = json_file

# Öffnen der JSON-Datei und Laden der Daten

    def read_mapping_json(self):
        """

        Returns:

        """
        with open(self.json_file, "r") as file:
            json_data = json.load(file)

        # Lesen der Daten aus der JSON-Datei
        space_dict = {}
        i = 1
        for key, value in json_data.items():
            usage_dict= {}
            space_guids_dict = {}
            space_guids = value["space_guids"]
            usage = value["usage"]
            usage_dict["usage"] = usage
            space_guids_dict["space_guids"] = space_guids
            if i not in space_dict:
                space_dict[i] = {}
            space_dict[i].update(space_guids_dict)
            space_dict[i].update(usage_dict)
            i = i + 1
        return space_dict

    def read_dymola_matlab(self):
        """

        Returns:

        """
        tsd = TimeSeriesData(self.mat_file)
        # Assuming you have already extracted the variable data
        time_column = tsd.index

        # Zeige alle Variablen in der MATLAB-Datei an
        variable_names = tsd.get_variable_names()
        variable_dict = {}
        for variable_name in variable_names:
            value_dict = {}
            variable_list = variable_name.split(".")
            if variable_list[0] == "multizone":
                if variable_list[1].find("PHeater") > -1 or variable_list[1].find("PCooler") > -1:
                    var = variable_list[1]
                    variable_values = tsd[variable_name]
                    variable = var[:var.find("[")]
                    zone = var[var.find("[")+1:var.rfind("]")]
                    if zone not in variable_dict:
                        #variable_dict[zone] = {}
                        variable_dict[zone] = {"time": time_column}
                    value_dict[variable] = variable_values.values

                    variable_dict[zone].update(value_dict)
        return variable_dict

    def merge_dict(self, variable_dict, space_dict):
        """

        Args:
            variable_dict ():
            space_dict ():
        """
        for key1, key2 in zip(variable_dict.keys(), space_dict.keys()):
            time = variable_dict[key1]["time"]
            space_dict[key2]["time"] = time
            PCooler = variable_dict[key1]["PCooler"]

            space_dict[key2]["PCooler"]= PCooler
            PHeater = variable_dict[key1]["PHeater"]
            space_dict[key2]["PHeater"] = PHeater
        return space_dict


if __name__ == '__main__':
    dym_mat_file = "C:/02_Masterarbeit/12_result/bim2sim/AC20-FZK-Haus/matlab_results/FZKHaus.mat"
    dym_json_file = "C:/02_Masterarbeit/12_result/bim2sim/AC20-FZK-Haus/matlab_results/tz_mapping.json"

    int_bim2sim = Bim2simInterface(mat_file = dym_mat_file,
                                    json_file = dym_json_file)

    space_dict = int_bim2sim.read_mapping_json()
    variable_dict = int_bim2sim.read_dymola_matlab()
    bim2sim_dict = int_bim2sim.merge_dict(variable_dict=variable_dict, space_dict=space_dict)



