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
                room_supply_dict = self.load_room_data(self.playground.sim_settings.ventilation_rooms_supply_xlsx)
                room_exhaust_dict = self.load_room_data(self.playground.sim_settings.ventilation_rooms_exhaust_xlsx)
                fire_damper_dict = self.load_fire_damper_data(self.playground.sim_settings.ventilation_fire_damper_xlsx)

            (total_gwp_fire_damper, total_cost_fire_damper,
             total_gwp_silencer, total_cost_silencer, total_gwp_vav,
             total_cost_vav) = self.calculate_components(room_supply_dict,
                                                         room_exhaust_dict,
                                                         fire_damper_dict,
                                                         material_emission_dict,
                                                         material_cost_dict)

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
                            total_cost_exhaust=total_cost_exhaust,
                            total_gwp_fire_damper=total_gwp_fire_damper,
                            total_cost_fire_damper=total_cost_fire_damper,
                            total_gwp_silencer=total_gwp_silencer,
                            total_cost_silencer=total_cost_silencer,
                            total_gwp_vav=total_gwp_vav,
                            total_cost_vav=total_cost_vav)

            total_gwp_ventilation_duct = total_gwp_supply + total_gwp_exhaust
            total_cost_ventilation_duct = total_cost_supply + total_cost_exhaust
            total_gwp_ventilation_component = total_gwp_fire_damper + total_gwp_silencer + total_gwp_vav
            total_cost_ventilation_component = total_cost_fire_damper + total_cost_silencer + total_cost_vav


            # Add maintenance costs
            total_gwp_ventilation_duct += total_gwp_ventilation_duct * 40 * material_cost_dict["VentilationSystem"]
            total_cost_ventilation_duct += total_cost_ventilation_duct * 40 * material_cost_dict["VentilationSystem"]
            total_gwp_ventilation_component += total_gwp_ventilation_component * 40 * material_cost_dict["VentilationSystem"]
            total_gwp_ventilation_component += total_gwp_ventilation_component * 40 * material_cost_dict["VentilationSystem"]

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
            # we need to recalculate this *100 because rho=100kg/m3
            mass_isolation = copy_duct_dict[pipe]["Isolation Volume [m³]"] * 100
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

    def calculate_components(
            self, room_supply_dict: dict, room_exhaust_dict: dict,
            fire_damper_dict: dict, material_emission_dict: dict,
            material_cost_dict: dict):

        total_gwp_silencer = 0
        total_gwp_vav = 0
        total_gwp_fire_damper = 0
        total_cost_silencer = 0
        total_cost_vav = 0
        total_cost_fire_damper = 0

        emission_fire_damper_spec = material_emission_dict[
            "Brandschutzklappe"]  # per kg
        emission_isolation_spec = material_emission_dict[
            "Mineralwolle-Daemmstoff"]  # per kg
        emission_duct_sheet_spec = material_emission_dict[
            "Lueftungskanal"]  # per kg
        emission_vav_spec = material_emission_dict[
            "Volumenstromregler_VRE"]  # per kg
        cost_fire_damper_spec = material_cost_dict[
            "Brandschutzklappe"]  # per piece
        cost_vav_spec = material_cost_dict["Volumenstromregler"]  # per piece
        cost_silencer_spec = material_cost_dict["Schalldaempfer"]  # per piece

        # Handle room supply calculations
        room_supply_dict_cp = room_supply_dict.copy()
        for room in room_supply_dict_cp:
            # Safely extract values with default of 0 for NaN or missing values
            mass_vav = self._safe_get_value(room_supply_dict_cp[room],
                                            "VAV Weight [kg]", 0)
            insulation_volume = self._safe_get_value(room_supply_dict_cp[room],
                                                     "Isolation volume Silencer [m³]",
                                                     0)
            mass_sheet_silencer = self._safe_get_value(
                room_supply_dict_cp[room], "Gewicht Blech Silencer [kg]", 0)

            # Only calculate if we have valid data
            if mass_vav > 0:
                emission_vav = mass_vav * emission_vav_spec
                total_gwp_vav += emission_vav
                total_cost_vav += cost_vav_spec

            # Calculate silencer emissions only if we have valid silencer data
            if insulation_volume > 0 or mass_sheet_silencer > 0:
                # We need to recalculate this *100 because rho=100kg/m3
                mass_insulation_silencer = insulation_volume * 100
                emission_silencer = mass_insulation_silencer * emission_isolation_spec + mass_sheet_silencer * emission_duct_sheet_spec
                total_gwp_silencer += emission_silencer
                total_cost_silencer += cost_silencer_spec

        # Handle room exhaust calculations
        room_exhaust_dict_cp = room_exhaust_dict.copy()
        for room in room_exhaust_dict_cp:
            # Safely extract values with default of 0 for NaN or missing values
            mass_vav = self._safe_get_value(room_exhaust_dict_cp[room],
                                            "VAV Weight [kg]", 0)
            insulation_volume = self._safe_get_value(
                room_exhaust_dict_cp[room], "Isolation volume Silencer [m³]",
                0)
            mass_sheet_silencer = self._safe_get_value(
                room_exhaust_dict_cp[room], "Gewicht Blech Silencer [kg]", 0)

            # Only calculate if we have valid data
            if mass_vav > 0:
                emission_vav = mass_vav * emission_vav_spec
                total_gwp_vav += emission_vav
                total_cost_vav += cost_vav_spec

            # Calculate silencer emissions only if we have valid silencer data
            if insulation_volume > 0 or mass_sheet_silencer > 0:
                # We need to recalculate this *100 because rho=100kg/m3
                mass_insulation_silencer = insulation_volume * 100
                emission_silencer = mass_insulation_silencer * emission_isolation_spec + mass_sheet_silencer * emission_duct_sheet_spec
                total_gwp_silencer += emission_silencer
                total_cost_silencer += cost_silencer_spec

        # Handle fire damper calculations
        if isinstance(fire_damper_dict, list):
            # If fire_damper_dict is a list of dictionaries
            for fire_damper in fire_damper_dict:
                mass_fire_damper = self._safe_get_value(fire_damper,
                                                        "Gewicht Brandschutzklappe[kg]",
                                                        0)
                if mass_fire_damper > 0:
                    total_gwp_fire_damper += mass_fire_damper * emission_fire_damper_spec
                    total_cost_fire_damper += cost_fire_damper_spec
        else:
            # If fire_damper_dict is a dictionary with indices as keys
            fire_damper_dict_cp = fire_damper_dict.copy()
            for idx in fire_damper_dict_cp:
                mass_fire_damper = self._safe_get_value(
                    fire_damper_dict_cp[idx], "Gewicht Brandschutzklappe[kg]",
                    0)
                if mass_fire_damper > 0:
                    total_gwp_fire_damper += mass_fire_damper * emission_fire_damper_spec
                    total_cost_fire_damper += cost_fire_damper_spec

        return (total_gwp_fire_damper, total_cost_fire_damper,
                total_gwp_silencer, total_cost_silencer, total_gwp_vav,
                total_cost_vav)

    def _safe_get_value(self, dictionary, key, default_value=0):
        """
        Safely get a value from a dictionary, handling NaN values.

        Args:
            dictionary: The dictionary to extract from
            key: The key to look up
            default_value: The default value to return if key is missing or value is NaN

        Returns:
            The value or default_value if value is NaN or key is missing
        """
        import math
        import numpy as np

        if key not in dictionary:
            return default_value

        value = dictionary[key]

        # Check for various forms of NaN or None
        if value is None or (isinstance(value, (int, float)) and (
        math.isnan(value) if hasattr(math, 'isnan') else np.isnan(value))):
            return default_value

        # Handle string 'nan' values
        if isinstance(value, str) and value.lower() == 'nan':
            return default_value

        # Try to convert string to float if possible
        if isinstance(value, str):
            try:
                value = float(value)
            except (ValueError, TypeError):
                return default_value

        return value

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
                   total_cost_exhaust,
                   total_gwp_fire_damper,
                   total_cost_fire_damper,
                   total_gwp_silencer,
                   total_cost_silencer,
                   total_gwp_vav,
                   total_cost_vav
                   ):


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
        data["Totals"]["GWP [kg CO2-eq]"]["Fire Dampers"] = total_gwp_fire_damper
        data["Totals"]["GWP [kg CO2-eq]"]["VAVs"] = total_gwp_vav
        data["Totals"]["GWP [kg CO2-eq]"]["Silencer"] = total_gwp_silencer
        data["Totals"]["GWP [kg CO2-eq]"]["Total"] = total_gwp_supply + total_gwp_exhaust + total_gwp_fire_damper + total_gwp_vav + total_gwp_silencer

        data["Totals"]["Cost [€]"] = {}
        data["Totals"]["Cost [€]"]["Supply"] = total_cost_supply
        data["Totals"]["Cost [€]"]["Exhaust"] = total_cost_exhaust
        data["Totals"]["Cost [€]"]["Fire Dampers"] = total_cost_fire_damper
        data["Totals"]["Cost [€]"]["VAVs"] = total_cost_vav
        data["Totals"]["Cost [€]"]["Silencer"] = total_cost_silencer

        data["Totals"]["Cost [€]"]["Total"] = total_cost_supply + total_cost_exhaust + total_cost_fire_damper + total_cost_vav + total_cost_silencer

        with pd.ExcelWriter(self.paths.export / "lca_lcc_ventilation_system.xlsx") as writer:
            for key, values in data.items():
                df = pd.DataFrame.from_dict(data[key], orient="columns")
                if key != "Totals":
                    df = df.transpose()
                df.to_excel(writer, sheet_name=key, index_label=key, index=True)

    def load_room_data(self, data_path):
        with open(data_path, "rb") as excel_file:
            df = pd.read_excel(excel_file, engine="openpyxl")
        room_dict = {}
        for index, row in df.iterrows():

            room_dict[index] = {"VAV Weight [kg]": row["Gewicht Volume_flow_controller"],
                                "Isolation volume Silencer [m³]": row["Isolation volume silencer"],
                                "Gewicht Blech Silencer [kg]": row["Gewicht Blech silencer"]}
        room_dict.pop(len(room_dict) - 1)

        return room_dict

    def load_fire_damper_data(self, data_path):
        fire_damper_dict = {}
        counter = 0

        # Load supply data
        with open(data_path, "rb") as excel_file:
            df_supply = pd.read_excel(excel_file, engine="openpyxl",
                                      sheet_name="Brandschutzklappen Zuluft")

        for _, row in df_supply.iterrows():
            fire_damper_dict[counter] = {"Gewicht Brandschutzklappe[kg]": row[
                "Gewicht Brandschutzklappe ges"]}
            counter += 1

        # Load exhaust data
        with open(data_path, "rb") as excel_file:
            df_exhaust = pd.read_excel(excel_file, engine="openpyxl",
                                       sheet_name="Brandschutzklappen Abluft")

        for _, row in df_exhaust.iterrows():
            fire_damper_dict[counter] = {"Gewicht Brandschutzklappe[kg]": row[
                "Gewicht Brandschutzklappe ges"]}
            counter += 1

        return fire_damper_dict



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