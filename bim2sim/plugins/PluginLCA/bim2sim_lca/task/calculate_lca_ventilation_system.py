import pandas as pd
import json
import math
from pathlib import Path
from bim2sim.tasks.base import ITask
from bim2sim.elements.mapping.units import ureg

class CalculateEmissionVentilationSystem(ITask):

    reads = ('material_emission_dict',)
    touches = ('total_gwp_ventilation_duct', 'total_gwp_ventilation_component')

    def run(self, material_emission_dict):
        total_gwp_ventilation_duct = 0
        total_gwp_ventilation_component = 0

        self.lock = self.playground.sim_settings.lock

        if self.playground.sim_settings.calculate_lca_ventilation_system:
            supply_dict = self.load_pipe_data(self.playground.sim_settings.ventilation_supply_system_material_xlsx)
            exhaust_dict = self.load_pipe_data(self.playground.sim_settings.ventilation_exhaust_system_material_xlsx)

            #component_dict = self.load_component_data()
            # component_material_emission, pump_component, total_gwp_hydraulic_component = self.calulcate_emission_components(
            #         component_dict=component_dict, material_emission_dict=material_emission_dict)

            supply_dict, total_gwp_supply, total_pipe_mass_supply, total_isolation_mass_supply = self.calulcate_emission_pipe(
                                                                        duct_dict=supply_dict,
                                                                        material_emission_dict=material_emission_dict)

            exhaust_dict, total_gwp_exhaust, total_pipe_mass_exhaust, total_isolation_mass_exhaust = self.calulcate_emission_pipe(
                                                                        duct_dict=exhaust_dict,
                                                                        material_emission_dict=material_emission_dict)

            self.write_xlsx(supply_dict=supply_dict,
                            exhaust_dict=exhaust_dict,
                            total_pipe_mass_supply=total_pipe_mass_supply,
                            total_pipe_mass_exhaust=total_pipe_mass_exhaust,
                            total_isolation_mass_supply=total_isolation_mass_supply,
                            total_isolation_mass_exhaust=total_isolation_mass_exhaust,
                            total_gwp_supply=total_gwp_supply,
                            total_gwp_exhaust=total_gwp_exhaust)

            total_gwp_ventilation_duct = total_gwp_supply + total_gwp_exhaust

        return total_gwp_ventilation_duct, total_gwp_ventilation_component

    def load_pipe_data(self, data_path):
        with self.lock:
            with open(data_path, "rb") as excel_file:
                df = pd.read_excel(excel_file, engine="openpyxl")
        pipe_dict = {}
        for index, row in df.iterrows():

            pipe_dict[index] = {"Duct weight [kg]": row["Sheet weight"],
                                "Isolation Volume [m³]": row["Isolation volume"]}
        pipe_dict.pop(len(pipe_dict) - 1)

        return pipe_dict

    def load_component_data(self):
        with self.lock:
            with open(self.playground.sim_settings.hydraulic_system_material_xlsx, "rb") as excel_file:
                df = pd.read_excel(excel_file, engine="openpyxl", sheet_name="Components")
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
                                duct_dict:dict,
                                material_emission_dict:dict):

        total_pipe_mass = 0
        total_isolation_mass = 0
        total_gwp = 0
        emission_pipe = material_emission_dict["Lueftungskanal"]
        emission_isolation = material_emission_dict["Mineralwolle-Daemmstoff"]

        copy_duct_dict = duct_dict.copy()
        for pipe in copy_duct_dict:
            mass_pipe = copy_duct_dict[pipe]["Duct weight [kg]"]
            mass_isolation = copy_duct_dict[pipe]["Isolation Volume [m³]"]

            emissions = round(mass_pipe * emission_pipe + mass_isolation * emission_isolation, 4)
            emission_dict = {"GWP [kg CO2-eq]": emissions}
            copy_duct_dict[pipe].update(emission_dict)

            copy_duct_dict[pipe]["Duct weight [kg]"] = mass_pipe
            copy_duct_dict[pipe]["Isolation Volume [m³]"] = mass_isolation

            total_pipe_mass += mass_pipe
            total_isolation_mass += mass_isolation
            total_gwp += emissions


        return copy_duct_dict, total_gwp, total_pipe_mass, total_isolation_mass

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
                   supply_dict,
                   exhaust_dict,
                   total_pipe_mass_supply,
                   total_pipe_mass_exhaust,
                   total_isolation_mass_supply,
                   total_isolation_mass_exhaust,
                   total_gwp_supply,
                   total_gwp_exhaust):


        data = {}
        # data["Pump"] = pump_component
        # data["Component"] = component_material_emission
        # data["Component"]["Total"] = total_gwp_component
        data["Supply Duct"] = supply_dict
        data["Supply Duct"]["Total"] = {"Mass Duct [kg]": total_pipe_mass_supply,
                                        "Mass Isolation [kg]": total_isolation_mass_supply,
                                        "GWP [kg CO2-eq]": total_gwp_supply}
        data["Exhaust Duct"] = exhaust_dict
        data["Exhaust Duct"]["Total"] = {"Mass Duct [kg]": total_pipe_mass_exhaust,
                                         "Mass Isolation [kg]": total_isolation_mass_exhaust,
                                         "GWP [kg CO2-eq]": total_gwp_exhaust}
        data["Total GWP"] = {}
        data["Total GWP"]["GWP [kg CO2-eq]"] = {}
        data["Total GWP"]["GWP [kg CO2-eq]"]["Pipe"] = total_gwp_supply + total_gwp_exhaust
        #data["Total GWP"]["GWP [kg CO2-eq]"]["Component"] =
        data["Total GWP"]["GWP [kg CO2-eq]"]["Total"] = total_gwp_supply + total_gwp_exhaust

        with pd.ExcelWriter(self.paths.export / "lca_ventilation_system.xlsx") as writer:
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