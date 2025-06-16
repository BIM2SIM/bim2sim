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
             total_pipe_weight_supply, total_insulation_weight_supply) = self.calulcate_pipe(
                                                                        duct_dict=supply_dict,
                                                                        material_emission_dict=material_emission_dict,
                                                                        material_cost_dict=material_cost_dict)

            (exhaust_dict, total_gwp_exhaust, total_cost_exhaust,
             total_pipe_weight_exhaust, total_insulation_weight_exhaust) = self.calulcate_pipe(
                                                                        duct_dict=exhaust_dict,
                                                                        material_emission_dict=material_emission_dict,
                                                                        material_cost_dict=material_cost_dict)

            self.write_xlsx(supply_dict=supply_dict,
                            exhaust_dict=exhaust_dict,
                            total_pipe_weight_supply=total_pipe_weight_supply,
                            total_pipe_weight_exhaust=total_pipe_weight_exhaust,
                            total_insulation_weight_supply=total_insulation_weight_supply,
                            total_insulation_weight_exhaust=total_insulation_weight_exhaust,
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

            rbf = (1.0-(1.0+0.03)**(-40.0))/0.03
            # Add maintenance costs
            # total_gwp_ventilation_duct += total_gwp_ventilation_duct * 40 * material_cost_dict["VentilationSystem"]
            total_cost_ventilation_duct += total_cost_ventilation_duct * rbf * material_cost_dict["VentilationSystem"]
            # total_gwp_ventilation_component += total_gwp_ventilation_component * 40 * material_cost_dict["VentilationSystem"]
            total_gwp_ventilation_component += total_gwp_ventilation_component * rbf * material_cost_dict["VentilationSystem"]

        return (total_gwp_ventilation_duct, total_gwp_ventilation_component,
                total_cost_ventilation_duct, total_cost_ventilation_component)

    def load_pipe_data(self, data_path):
        with open(data_path, "rb") as excel_file:
            df = pd.read_excel(excel_file, engine="openpyxl")
        pipe_dict = {}
        for index, row in df.iterrows():

            pipe_dict[index] = {"Duct weight in kg": row["sheet_weight"],
                                "Insulation Volume in m³": row["insulation_volume"],
                                "Surface Area in m²": row["surface_area"]}
        pipe_dict.pop(len(pipe_dict) - 1)

        return pipe_dict


    def calulcate_pipe(self,
                       duct_dict:dict,
                       material_emission_dict:dict,
                       material_cost_dict:dict):

        total_pipe_weight = 0
        total_insulation_weight = 0
        total_gwp = 0
        total_cost = 0

        emission_pipe = material_emission_dict["Lueftungskanal"]
        emission_insulation = material_emission_dict["Mineralwolle-Daemmstoff"]
        cost_pipe = material_cost_dict["Lueftungskanal_m2"]

        copy_duct_dict = duct_dict.copy()
        for pipe in copy_duct_dict:
            weight_pipe = copy_duct_dict[pipe]["Duct weight in kg"]
            # we need to recalculate this *100 because rho=100kg/m3
            weight_insulation = copy_duct_dict[pipe]["Insulation Volume in m³"] * 100
            surface_area = ureg(copy_duct_dict[pipe]["Surface Area in m²"]).magnitude

            emission = round(weight_pipe * emission_pipe + weight_insulation * emission_insulation, 2)
            cost = round(surface_area * cost_pipe, 2)
            copy_duct_dict[pipe]["GWP in kg CO2-eq"] = emission
            copy_duct_dict[pipe]["Cost in €"] = cost

            total_pipe_weight += weight_pipe
            total_insulation_weight += weight_insulation
            total_gwp += emission
            total_cost += cost


        return copy_duct_dict, total_gwp, total_cost, total_pipe_weight, total_insulation_weight

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
        emission_insulation_spec = material_emission_dict[
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
            weight_vav = self._safe_get_value(room_supply_dict_cp[room],
                                            "weight_volume_flow_controller", 0)
            insulation_volume = self._safe_get_value(room_supply_dict_cp[room],
                                                     "insulation_volume_silencer",
                                                     0)
            weight_sheet_silencer = self._safe_get_value(
                room_supply_dict_cp[room], "weight_insulation_silencer", 0)

            # Only calculate if we have valid data
            if weight_vav > 0:
                emission_vav = weight_vav * emission_vav_spec
                total_gwp_vav += emission_vav
                total_cost_vav += cost_vav_spec

            # Calculate silencer emissions only if we have valid silencer data
            if insulation_volume > 0 or weight_sheet_silencer > 0:
                # We need to recalculate this *100 because rho=100kg/m3
                weight_insulation_silencer = insulation_volume * 100
                emission_silencer = weight_insulation_silencer * emission_insulation_spec + weight_sheet_silencer * emission_duct_sheet_spec
                total_gwp_silencer += emission_silencer
                total_cost_silencer += cost_silencer_spec

        # VAV and silcener only in supply
        # Handle room exhaust calculations
        # room_exhaust_dict_cp = room_exhaust_dict.copy()
        # for room in room_exhaust_dict_cp:
        #     # Safely extract values with default of 0 for NaN or missing values
        #     weight_vav = self._safe_get_value(room_exhaust_dict_cp[room],
        #                                     "VAV Weight in kg", 0)
        #     insulation_volume = self._safe_get_value(
        #         room_exhaust_dict_cp[room], "Insulation volume Silencer in m³",
        #         0)
        #     weight_sheet_silencer = self._safe_get_value(
        #         room_exhaust_dict_cp[room], "Gewicht Blech Silencer in kg", 0)
        #
        #     # Only calculate if we have valid data
        #     if weight_vav > 0:
        #         emission_vav = weight_vav * emission_vav_spec
        #         total_gwp_vav += emission_vav
        #         total_cost_vav += cost_vav_spec
        #
        #     # Calculate silencer emissions only if we have valid silencer data
        #     if insulation_volume > 0 or weight_sheet_silencer > 0:
        #         # We need to recalculate this *100 because rho=100kg/m3
        #         weight_insulation_silencer = insulation_volume * 100
        #         emission_silencer = weight_insulation_silencer * emission_insulation_spec + weight_sheet_silencer * emission_duct_sheet_spec
        #         total_gwp_silencer += emission_silencer
        #         total_cost_silencer += cost_silencer_spec


        fire_damper_dict_cp = fire_damper_dict.copy()
        for idx in fire_damper_dict_cp:
            weight_fire_damper = self._safe_get_value(
                fire_damper_dict_cp[idx], "weight_fire_damper",
                0)
            if weight_fire_damper > 0:
                total_gwp_fire_damper += weight_fire_damper * emission_fire_damper_spec
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
                value = ureg(value).m
            except (ValueError, TypeError):
                return default_value

        return value

    def write_xlsx(self,
                   supply_dict,
                   exhaust_dict,
                   total_pipe_weight_supply,
                   total_pipe_weight_exhaust,
                   total_insulation_weight_supply,
                   total_insulation_weight_exhaust,
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
        data["Supply Duct"]["Total"] = {"Duct weight in kg": total_pipe_weight_supply,
                                        "Insulation weight in kg": total_insulation_weight_supply,
                                        "GWP in kg CO2-eq": total_gwp_supply,
                                        "Cost in €": total_cost_supply}
        data["Exhaust Duct"] = exhaust_dict
        data["Exhaust Duct"]["Total"] = {"Duct weight in kg": total_pipe_weight_exhaust,
                                         "Insulation weight in kg": total_insulation_weight_exhaust,
                                         "GWP in kg CO2-eq": total_gwp_exhaust,
                                         "Cost in €": total_cost_exhaust}
        data["Totals"] = {}
        data["Totals"]["GWP in kg CO2-eq"] = {}
        data["Totals"]["GWP in kg CO2-eq"]["Supply"] = total_gwp_supply
        data["Totals"]["GWP in kg CO2-eq"]["Exhaust"] = total_gwp_exhaust
        data["Totals"]["GWP in kg CO2-eq"]["Fire Dampers"] = total_gwp_fire_damper
        data["Totals"]["GWP in kg CO2-eq"]["Volume Flow Controller"] = total_gwp_vav
        data["Totals"]["GWP in kg CO2-eq"]["Silencer"] = total_gwp_silencer
        data["Totals"]["GWP in kg CO2-eq"]["Total"] = total_gwp_supply + total_gwp_exhaust + total_gwp_fire_damper + total_gwp_vav + total_gwp_silencer

        data["Totals"]["Cost in €"] = {}
        data["Totals"]["Cost in €"]["Supply"] = total_cost_supply
        data["Totals"]["Cost in €"]["Exhaust"] = total_cost_exhaust
        data["Totals"]["Cost in €"]["Fire Damper"] = total_cost_fire_damper
        data["Totals"]["Cost in €"]["Volume Flow Controller"] = total_cost_vav
        data["Totals"]["Cost in €"]["Silencer"] = total_cost_silencer

        data["Totals"]["Cost in €"]["Total"] = total_cost_supply + total_cost_exhaust + total_cost_fire_damper + total_cost_vav + total_cost_silencer

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

            room_dict[index] = {"Weight of Volume Flow Controller in kg": row["weight_volume_flow_controller"],
                                "insulation volume of Silencer in m³": row["insulation_volume_silencer"],
                                "Sheet weight of Silencer in kg": row["weight_metal_silencer"]}
        room_dict.pop(len(room_dict) - 1)

        return room_dict

    def load_fire_damper_data(self, data_path):
        fire_damper_dict = {}
        counter = 0

        # Load supply data
        with open(data_path, "rb") as excel_file:
            df_supply = pd.read_excel(excel_file, engine="openpyxl",
                                      sheet_name="fire dampers supply air")

        for _, row in df_supply.iterrows():
            fire_damper_dict[counter] = {"Fire damper weight in kg": row[
                "sum_weight_fire_damper"]}
            counter += 1

        # Load exhaust data
        with open(data_path, "rb") as excel_file:
            df_exhaust = pd.read_excel(excel_file, engine="openpyxl",
                                       sheet_name="fire dampers exhaust air")

        for _, row in df_exhaust.iterrows():
            fire_damper_dict[counter] = {"Fire damper weight in kg": row[
                "sum_weight_fire_damper"]}
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