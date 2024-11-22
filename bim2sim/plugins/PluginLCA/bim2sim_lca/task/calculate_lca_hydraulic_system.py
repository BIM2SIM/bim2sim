import pandas as pd
import json
import math
from pathlib import Path
from bim2sim.tasks.base import ITask
from bim2sim.elements.mapping.units import ureg

class CalculateEmissionHydraulicSystem(ITask):

    reads = ('material_emission_dict',)
    touches = ('total_gwp_hydraulic_pipe', 'total_gwp_hydraulic_component')

    def run(self, material_emission_dict):
        if self.playground.sim_settings.calculate_lca_hydraulic_system:
            pipe_dict = self.load_pipe_data()

            component_dict = self.load_component_data()
            component_material_emission, pump_component, total_gwp_hydraulic_component = self.calulcate_emission_components(
                    component_dict=component_dict, material_emission_dict=material_emission_dict)

            pipe_dict, total_gwp_hydraulic_pipe, total_pipe_mass, total_isolation_mass = self.calulcate_emission_pipe(pipe_dict=pipe_dict, material_emission_dict=material_emission_dict)
            self.write_xlsx(pipe_dict=pipe_dict,
                            component_material_emission=component_material_emission,
                            pump_component=pump_component,
                            total_pipe_mass=total_pipe_mass,
                            total_isolation_mass=total_isolation_mass,
                            total_gwp_pipe=total_gwp_hydraulic_pipe,
                            total_gwp_component=total_gwp_hydraulic_component)

        return total_gwp_hydraulic_pipe, total_gwp_hydraulic_component

    def load_pipe_data(self):
        df = pd.read_excel(self.playground.sim_settings.hydraulic_system_material_xlsx, sheet_name="Pipes")
        pipe_dict = {}
        for  index, row in df.iterrows():

            pipe_dict[index] = {"Material": row["Material"],
                                "Mass Pipe [kg]": row["Mass Pipe [kg]"],
                                "Mass Isolation [kg]": row["Mass Isolation [kg]"]}
        pipe_dict.pop(len(pipe_dict) - 1)

        return pipe_dict

    def load_component_data(self):
        df = pd.read_excel(self.playground.sim_settings.hydraulic_system_material_xlsx, sheet_name="Components")
        component_dict = {}
        for index, row in df.iterrows():
            if self.playground.sim_settings.heat_delivery_type == "Radiator":
                if "radiator_forward" in row["Type"] and not "ground" in row["Type"]:
                    component_dict[index] = {"Type": row["Type"],
                                             "Material": row["Material"],
                                             "Mass [kg]": row["Mass [kg]"],
                                             "Power [kW]": row["Power [kW]"]}
                if "Pumpe" in row["Type"]:
                    component_dict[index] = {"Type": row["Type"],
                                             "Power [kW]": row["Power [kW]"]}
            elif self.playground.sim_settings.heat_delivery_type == "UFH":
                if "radiator_forward" in row["Type"] and not "extra" in row["Type"]:
                    component_dict[index] = {"Type": row["Type"],
                                             "UFH Area [m²]": row["UFH area [m²]"],
                                             "UFH Laying Distance [mm]": row["UFH Laying Distance [mm]"]}
                elif "radiator_forward_extra" in row["Type"] and not "ground" in row["Type"]:
                    component_dict[index] = {"Type": row["Type"],
                                             "Material": row["Material"],
                                             "Mass [kg]": row["Mass [kg]"],
                                             "Power [kW]": row["Power [kW]"]}
                elif "Pumpe" in row["Type"]:
                    component_dict[index] = {"Type": row["Type"],
                                             "Power [kW]": row["Power [kW]"]}
        return component_dict

    def calulcate_emission_pipe(self,
                                pipe_dict:dict,
                                material_emission_dict:dict):

        total_pipe_mass = 0
        total_isolation_mass = 0
        total_gwp = 0
        emission_pipe = material_emission_dict[self.playground.sim_settings.pipe_type]
        emission_isolation = material_emission_dict["Rohrisolierung"]

        copy_pipe_dict = pipe_dict.copy()
        for pipe in copy_pipe_dict:

            mass_pipe = copy_pipe_dict[pipe]["Mass Pipe [kg]"]
            mass_isolation = copy_pipe_dict[pipe]["Mass Isolation [kg]"]

            emissions = round(mass_pipe * emission_pipe + mass_isolation * emission_isolation, 4)
            emission_dict = {"GWP [kg CO2-eq]": emissions}
            pipe_dict[pipe].update(emission_dict)

            pipe_dict[pipe]["Mass Pipe [kg]"] = mass_pipe
            pipe_dict[pipe]["Mass Isolation [kg]"] = mass_isolation

            total_pipe_mass += mass_pipe
            total_isolation_mass += mass_isolation
            total_gwp += emissions

        return pipe_dict, total_gwp, total_pipe_mass, total_isolation_mass

    def calulcate_emission_components(self,
                                      component_dict: dict,
                                      material_emission_dict: dict):

        if self.playground.sim_settings.heat_delivery_type == "Radiator":
            mapping = {"radiator_forward": "Heizkoerper",}
        elif self.playground.sim_settings.heat_delivery_type == "UFH":
            ufh_pipe_type = self.playground.sim_settings.ufh_pipe_type
            mapping = {'radiator_forward': '', "radiator_forward_extra": "Heizkoerper"}

        component_material_emission = {}
        pump_component = {}
        total_gwp_component = 0

        mapping_keys_list = list(mapping.keys())
        for comp_material, material_value in component_dict.items():
            corresponding_material = material_value["Type"]
            for key in mapping_keys_list:
                if key in corresponding_material:
                    if "Mass [kg]" in material_value or "UFH Area [m²]" in material_value:
                        if self.playground.sim_settings.heat_delivery_type == "UFH":
                            if "extra" not in corresponding_material:
                                mapping[key] = (f"Fussbodenheizung_{ufh_pipe_type}_"
                                                f"{int(material_value['UFH Laying Distance [mm]'])}mm_m2")
                                material_amount = material_value["UFH Area [m²]"]
                            else:
                                mapping[key] = "Heizkoerper"
                                material_amount = material_value["Mass [kg]"]
                        elif self.playground.sim_settings.heat_delivery_type == "Radiator":
                            material_amount = material_value["Mass [kg]"]
                        gwp = material_emission_dict[mapping[key]]
                        emissions = round(material_amount * gwp,4)
                        total_gwp_component += emissions
                        material_value["GWP [kg CO2-eq]"] = emissions

                        if key not in component_material_emission:
                            component_material_emission[comp_material] = {}
                        component_material_emission[comp_material]["Type"] = mapping[key]
                        component_material_emission[comp_material]["GWP [kg CO2-eq]"] = emissions
                else:
                    if "Pumpe" in corresponding_material:
                        if comp_material not in pump_component:
                            pump_component[comp_material] = {}
                        pump_component[comp_material]["Power [kW]"] = material_value["Power [kW]"]
        return component_material_emission, pump_component, total_gwp_component


    def write_xlsx(self,
                   pipe_dict,
                   total_gwp_pipe,
                   component_material_emission,
                   total_pipe_mass,
                   total_isolation_mass,
                   total_gwp_component,
                   pump_component
                   ):


        data = {}
        data["Pump"] = pump_component
        data["Component"] = component_material_emission
        data["Component"]["Total"] = total_gwp_component
        data["Pipe"] = pipe_dict
        data["Pipe"]["Total"] = {"Material": "",
                                 "Mass Pipe [kg]": total_pipe_mass,
                                 "Mass Isolation [kg]": total_isolation_mass,
                                 "GWP [kg CO2-eq]": total_gwp_pipe}
        data["Total GWP"] = {}
        data["Total GWP"]["GWP [kg CO2-eq]"] = {}
        data["Total GWP"]["GWP [kg CO2-eq]"]["Pipe"] = total_gwp_pipe
        data["Total GWP"]["GWP [kg CO2-eq]"]["Component"] = total_gwp_component
        data["Total GWP"]["GWP [kg CO2-eq]"]["Total"] = total_gwp_pipe + total_gwp_component

        with pd.ExcelWriter(self.paths.export / "lca_hydraulic_system.xlsx") as writer:
            for key, values in data.items():
                df = pd.DataFrame.from_dict(data[key], orient="columns")
                if key != "Total GWP":
                    df = df.transpose()
                df.to_excel(writer, sheet_name=key, index_label=key, index=True)




    @staticmethod
    def ureg_to_str(value, unit, n_digits=3, ):
        """Transform pint unit to human readable value with given unit."""
        if value is not None and not isinstance(value, float):
            return round(value.to(unit).m, n_digits)
        elif value is None:
            return "-"
        else:
            return value

    @staticmethod
    def ureg_to_float(value, unit, n_digits=3, ):
        """Transform pint unit to human readable value with given unit."""
        if value is not None and not isinstance(value, str):
            return round(value.to(unit).m, n_digits)
        elif value is None:
            return "-"
        else:
            return value