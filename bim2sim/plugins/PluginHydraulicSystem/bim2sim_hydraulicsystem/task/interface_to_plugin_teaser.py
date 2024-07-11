from bim2sim.tasks.base import ITask

from ebcpy import TimeSeriesData
import json

class InterfaceToPluginTeaser(ITask):
    """Loads heat demand data which has been generated by bim2sim plugin teaser"""

    reads = ()
    touches = ('heat_demand_dict',)

    def run(self):
        self.logger.info("Load heat demand data")

        thermal_zone_dict = self.read_thermal_zone_mapping_json()
        plugin_teaser_dict = self.read_heat_demand_mat_file()
        heat_demand_dict = self.merge_dicts(plugin_teaser_dict=plugin_teaser_dict, thermal_zone_dict=thermal_zone_dict)

        return heat_demand_dict,


    def read_thermal_zone_mapping_json(self):
        filepath = self.playground.sim_settings.thermal_zone_mapping_file_path
        with open(filepath, "r") as file:
            json_data = json.load(file)

        space_dict = {}
        i = 1
        for key, value in json_data.items():
            usage_dict = {}
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

    def read_heat_demand_mat_file(self):
        filepath = self.playground.sim_settings.heat_demand_mat_file_path
        tsd = TimeSeriesData(filepath)

        time_column = tsd.index
        plugin_teaser_names = tsd.get_variable_names()
        plugin_teaser_dict = {}
        plugin_teaser_thermal_zone_dict = {}
        for plugin_teaser_name in plugin_teaser_names:  
            plugin_teaser = plugin_teaser_name.split(".")[1]
            # thermal_zonenplugin_teasern
            if plugin_teaser.find("[") > -1:
                var = plugin_teaser[:plugin_teaser.find("[")]
                thermal_zone = plugin_teaser[plugin_teaser.find("[") + 1:plugin_teaser.rfind("]")]
                if thermal_zone.find(",") > -1:
                    split = thermal_zone.split(",")
                    thermal_zone = split[0]
                    var = f'{var.lstrip()}_{split[1].lstrip()}'
                if thermal_zone not in plugin_teaser_thermal_zone_dict:
                    plugin_teaser_thermal_zone_dict[thermal_zone] = {}
                if var not in plugin_teaser_thermal_zone_dict[thermal_zone]:
                    plugin_teaser_thermal_zone_dict[thermal_zone][var] = {}
                value_list = (tsd[plugin_teaser_name].values.tolist())
                result_dict = {time_column[i]: value_list[i][0] * 10 ** (-3) for i in range(len(time_column))}
                plugin_teaser_thermal_zone_dict[thermal_zone][var] = result_dict
            # Nicht thermal_zonenplugin_teasern
            else:

                if plugin_teaser not in plugin_teaser_dict:
                    plugin_teaser_dict[plugin_teaser] = {}
                value_list = (tsd[plugin_teaser_name].values.tolist())
                result_dict = {time_column[i]: value_list[i][0] * 10 ** (-3) for i in range(len(time_column))}
                plugin_teaser_dict[plugin_teaser] = result_dict
        return plugin_teaser_thermal_zone_dict

    def merge_dicts(self, plugin_teaser_dict, thermal_zone_dict):

        for key in plugin_teaser_dict:

            max_P_Heater = max(plugin_teaser_dict[key]["PHeater"].values())

            thermal_zone_dict[int(key)]["PHeater"] = max_P_Heater
        return thermal_zone_dict