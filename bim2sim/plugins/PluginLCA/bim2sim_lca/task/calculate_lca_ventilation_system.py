import pandas as pd
import json
import math
from pathlib import Path
from bim2sim.tasks.base import ITask
from bim2sim.elements.mapping.units import ureg

class CalculateEmissionVentilationSystem(ITask):

    reads = ('material_emission_dict', 'material_cost_dict')
    touches = ('total_gwp_ventilation_duct', 'total_gwp_ventilation_component',
               'total_cost_ventilation_duct', 'total_cost_ventilation_component')

    def run(self, material_emission_dict, material_cost_dict):
        total_gwp_ventilation_duct = 0
        total_gwp_ventilation_component = 0
        total_cost_ventilation_duct = 0
        total_cost_ventilation_component = 0

        self.lock = self.playground.sim_settings.lock

        if self.playground.sim_settings.calculate_lca_ventilation_system:
            with self.lock:
                supply_dict = self.load_pipe_data(self.playground.sim_settings.ventilation_supply_system_material_xlsx)
                exhaust_dict = self.load_pipe_data(self.playground.sim_settings.ventilation_exhaust_system_material_xlsx)

            (supply_dict, total_gwp_supply, total_cost_supply,
             total_pipe_mass_supply, total_isolation_mass_supply) = self.calulcate_pipe(
                                                                        duct_dict=supply_dict,
                                                                        material_emission_dict=material_emission_dict,
                                                                        material_cost_dict=material_cost_dict)

            (exhaust_dict, total_gwp_exhaust, total_cost_exhaust,
             total_pipe_mass_exhaust, total_isolation_mass_exhaust) = self.calulcate_pipe(
                                                                        duct_dict=exhaust_dict,
                                                                        material_emission_dict=material_emission_dict,
                                                                        material_cost_dict=material_cost_dict)

            self.write_xlsx(supply_dict=supply_dict,
                            exhaust_dict=exhaust_dict,
                            total_pipe_mass_supply=total_pipe_mass_supply,
                            total_pipe_mass_exhaust=total_pipe_mass_exhaust,
                            total_isolation_mass_supply=total_isolation_mass_supply,
                            total_isolation_mass_exhaust=total_isolation_mass_exhaust,
                            total_gwp_supply=total_gwp_supply,
                            total_gwp_exhaust=total_gwp_exhaust,
                            total_cost_supply=total_cost_supply,
                            total_cost_exhaust=total_cost_exhaust)

            total_gwp_ventilation_duct = total_gwp_supply + total_gwp_exhaust
            total_cost_ventilation_duct = total_cost_supply + total_cost_exhaust

            # Add maintenance costs
            total_gwp_ventilation_duct += total_gwp_ventilation_duct * 40 * material_cost_dict["VentilationSystem"]
            total_cost_ventilation_duct += total_cost_ventilation_duct * 40 * material_cost_dict["VentilationSystem"]

        return (total_gwp_ventilation_duct, total_gwp_ventilation_component,
                total_cost_ventilation_duct, total_cost_ventilation_component)

    def load_pipe_data(self, data_path):
        with open(data_path, "rb") as excel_file:
            df = pd.read_excel(excel_file, engine="openpyxl")
        pipe_dict = {}
        for index, row in df.iterrows():

            pipe_dict[index] = {"Duct weight [kg]": row["Sheet weight"],
                                "Isolation Volume [m³]": row["Isolation volume"],
                                "Surface Area [m²]": row["Surface area"]}
        pipe_dict.pop(len(pipe_dict) - 1)

        return pipe_dict


    def calulcate_pipe(self,
                       duct_dict:dict,
                       material_emission_dict:dict,
                       material_cost_dict:dict):

        total_pipe_mass = 0
        total_isolation_mass = 0
        total_gwp = 0
        total_cost = 0

        emission_pipe = material_emission_dict["Lueftungskanal"]
        emission_isolation = material_emission_dict["Mineralwolle-Daemmstoff"]
        cost_pipe = material_cost_dict["Lueftungskanal_m2"]

        copy_duct_dict = duct_dict.copy()
        for pipe in copy_duct_dict:
            mass_pipe = copy_duct_dict[pipe]["Duct weight [kg]"]
            mass_isolation = copy_duct_dict[pipe]["Isolation Volume [m³]"]
            surface_area = ureg(copy_duct_dict[pipe]["Surface Area [m²]"]).magnitude

            emission = round(mass_pipe * emission_pipe + mass_isolation * emission_isolation, 2)
            cost = round(surface_area * cost_pipe, 2)
            copy_duct_dict[pipe]["GWP [kg CO2-eq]"] = emission
            copy_duct_dict[pipe]["Cost [€]"] = cost

            total_pipe_mass += mass_pipe
            total_isolation_mass += mass_isolation
            total_gwp += emission
            total_cost += cost


        return copy_duct_dict, total_gwp, total_cost, total_pipe_mass, total_isolation_mass


    def write_xlsx(self,
                   supply_dict,
                   exhaust_dict,
                   total_pipe_mass_supply,
                   total_pipe_mass_exhaust,
                   total_isolation_mass_supply,
                   total_isolation_mass_exhaust,
                   total_gwp_supply,
                   total_gwp_exhaust,
                   total_cost_supply,
                   total_cost_exhaust):


        data = {}
        # data["Pump"] = pump_component
        # data["Component"] = component_material_emission
        # data["Component"]["Total"] = total_gwp_component
        data["Supply Duct"] = supply_dict
        data["Supply Duct"]["Total"] = {"Mass Duct [kg]": total_pipe_mass_supply,
                                        "Mass Isolation [kg]": total_isolation_mass_supply,
                                        "GWP [kg CO2-eq]": total_gwp_supply,
                                         "Cost [€]": total_cost_supply}
        data["Exhaust Duct"] = exhaust_dict
        data["Exhaust Duct"]["Total"] = {"Mass Duct [kg]": total_pipe_mass_exhaust,
                                         "Mass Isolation [kg]": total_isolation_mass_exhaust,
                                         "GWP [kg CO2-eq]": total_gwp_exhaust,
                                         "Cost [€]": total_cost_exhaust}
        data["Totals"] = {}
        data["Totals"]["GWP [kg CO2-eq]"] = {}
        data["Totals"]["GWP [kg CO2-eq]"]["Supply"] = total_gwp_supply
        data["Totals"]["GWP [kg CO2-eq]"]["Exhaust"] = total_gwp_exhaust
        data["Totals"]["GWP [kg CO2-eq]"]["Total"] = total_gwp_supply + total_gwp_exhaust
        data["Totals"]["Cost [€]"] = {}
        data["Totals"]["Cost [€]"]["Supply"] = total_cost_supply
        data["Totals"]["Cost [€]"]["Exhaust"] = total_cost_exhaust
        data["Totals"]["Cost [€]"]["Total"] = total_cost_supply + total_cost_exhaust

        with pd.ExcelWriter(self.paths.export / "lca_lcc_ventilation_system.xlsx") as writer:
            for key, values in data.items():
                df = pd.DataFrame.from_dict(data[key], orient="columns")
                if key != "Totals":
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