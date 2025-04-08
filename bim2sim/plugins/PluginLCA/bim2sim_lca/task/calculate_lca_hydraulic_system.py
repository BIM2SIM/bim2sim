import pandas as pd
from bim2sim.tasks.base import ITask
from bim2sim.elements.mapping.units import ureg


class CalculateEmissionHydraulicSystem(ITask):

    reads = ('material_emission_dict', 'material_cost_dict')
    touches = ('total_gwp_hydraulic_pipe', 'total_gwp_hydraulic_component',
               'total_cost_hydraulic_pipe', 'total_cost_hydraulic_component')

    def run(self, material_emission_dict, material_cost_dict):

        if self.playground.sim_settings.calculate_lca_hydraulic_system:
            self.lock = self.playground.sim_settings.lock


            # TODO if this fails, recheck if hydraulic_components_data_file_radiator_sheet as ChoiceSetting is the reason
            with self.lock:
                pipe_dict = self.load_pipe_data()
                component_dict = self.load_component_data()
                radiator_dict = self.read_radiator_material_excel(
                    filename=self.playground.sim_settings.hydraulic_components_data_file_path,
                    sheet_name=self.playground.sim_settings.hydraulic_components_data_file_radiator_sheet)

            (component_material_emission_cost, pump_component, 
             total_gwp_hydraulic_component, total_cost_hydraulic_component) = self.calulcate_components(
                                                                                    component_dict=component_dict,
                                                                                    material_emission_dict=material_emission_dict,
                                                                                    radiator_dict=radiator_dict,
                                                                                    material_cost_dict=material_cost_dict)

            (pipe_dict, total_gwp_hydraulic_pipe, total_cost_hydraulic_pipe,
             total_pipe_mass, total_isolation_mass) = self.calulcate_pipe(pipe_dict=pipe_dict,
                                                                          material_emission_dict=material_emission_dict,
                                                                          material_cost_dict=material_cost_dict)

            # Add maintenance costs
            total_cost_hydraulic_pipe += total_cost_hydraulic_pipe * 40 * material_cost_dict["HydraulicSystem"]
            total_cost_hydraulic_component += total_cost_hydraulic_component * 40 * material_cost_dict["HydraulicSystem"]

            self.write_xlsx(pipe_dict=pipe_dict,
                            component_material_emission_cost=
                            component_material_emission_cost,
                            pump_component=pump_component,
                            total_pipe_mass=total_pipe_mass,
                            total_isolation_mass=total_isolation_mass,
                            total_gwp_pipe=total_gwp_hydraulic_pipe,
                            total_gwp_component=total_gwp_hydraulic_component,
                            total_cost_pipe=total_cost_hydraulic_pipe,
                            total_cost_component=total_cost_hydraulic_component
                            )

            return (total_gwp_hydraulic_pipe, total_gwp_hydraulic_component,
                    total_cost_hydraulic_pipe, total_cost_hydraulic_component)
        else:
            self.logger.warning(
                f"Skipping task {self.name} as sim_setting "
                f"'calculate_lca_hydraulic_system' "
                f"is set to "
                f"{self.playground.sim_settings.calculate_lca_hydraulic_system}"
                f"and no LCA calculation of hydraulic system should be"
                f" performed.")
            return None, None, None, None

    def load_pipe_data(self):
        with open(self.playground.sim_settings.hydraulic_system_material_xlsx, "rb") as excel_file:
            df = pd.read_excel(excel_file, engine="openpyxl", sheet_name="Pipes")

        pipe_dict = {}
        for index, row in df.iterrows():
            pipe_dict[index] = {"Material": row["Material"],
                                "Mass Pipe [kg]": row["Mass Pipe [kg]"],
                                "Mass Isolation [kg]": row["Mass Isolation [kg]"],
                                "Pipe Length [m]": row["Pipe Length [m]"]}
        pipe_dict.pop(len(pipe_dict) - 1)

        return pipe_dict

    def load_component_data(self):
        with open(self.playground.sim_settings.hydraulic_system_material_xlsx, "rb") as excel_file:
            df = pd.read_excel(excel_file, engine="openpyxl", sheet_name="Components")

        component_dict = {}
        for index, row in df.iterrows():
            if self.playground.sim_settings.heat_delivery_type == "Radiator":
                if "radiator_forward" in row["Type"] and not "ground" in row["Type"]:
                    component_dict[index] = {"Type": row["Type"],
                                             "Material": row["Material"],
                                             "Mass [kg]": row["Mass [kg]"],
                                             "Length [m]": row["Length [m]"],
                                             "Power [kW]": row["Power [kW]"],
                                             "Model": row["Model"]}
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
                                             "Length [m]": row["Length [m]"],
                                             "Power [kW]": row["Power [kW]"],
                                             "Model": row["Model"]}
                elif "Pumpe" in row["Type"]:
                    component_dict[index] = {"Type": row["Type"],
                                             "Power [kW]": row["Power [kW]"]}
        return component_dict

    def read_radiator_material_excel(self,
                                     filename,
                                     sheet_name,
                                     ):
        """

        Args:
            filename ():
            sheet_name ():

        Returns:

        """
        with open(filename, "rb") as excel_file:
            data = pd.read_excel(excel_file, engine="openpyxl", sheet_name=sheet_name)

        # Daten aus der Tabelle auslesen und verarbeiten
        model_dict = {}
        for index, row in data.iterrows():
            data_dict = {}
            if not pd.isnull(row['Typ']):
                data_dict["typ"] = row['Typ']
            if not pd.isnull(row['Normwärmeleistung ((75/65/20 °C) in W/m']):
                data_dict["Normwärmeleistung"] = row['Normwärmeleistung ((75/65/20 °C) in W/m'] * (
                            ureg.watt / ureg.meter)
            if not pd.isnull(row['Trendlinie a']):
                data_dict["Trendlinie a"] = row['Trendlinie a']
            if not pd.isnull(row['Trendlinie e']):
                data_dict["Trendlinie e"] = row['Trendlinie e']
            # Weiterverarbeitung der Daten (hier nur Ausgabe als Beispiel)
            model_dict[index] = data_dict
        return model_dict

    def calulcate_pipe(self,
                       pipe_dict:dict,
                       material_emission_dict:dict,
                       material_cost_dict:dict):

        total_pipe_mass = 0
        total_isolation_mass = 0
        total_pipe_length = 0
        total_gwp = 0
        total_cost = 0
        emission_pipe = material_emission_dict[self.playground.sim_settings.pipe_type]
        emission_isolation = material_emission_dict["Rohrisolierung"]
        cost_pipe = material_cost_dict[self.playground.sim_settings.pipe_type]["Pipe"]
        cost_isolation = material_cost_dict[self.playground.sim_settings.pipe_type]["Isolation"]
        cost_installation = material_cost_dict[self.playground.sim_settings.pipe_type]["Installation"]

        copy_pipe_dict = pipe_dict.copy()
        for pipe in copy_pipe_dict:
            pipe_dict[pipe] = {}
            mass_pipe = copy_pipe_dict[pipe]["Mass Pipe [kg]"]
            mass_isolation = copy_pipe_dict[pipe]["Mass Isolation [kg]"]
            pipe_length = copy_pipe_dict[pipe]["Pipe Length [m]"]

            emissions = round(mass_pipe * emission_pipe + mass_isolation * emission_isolation, 2)
            cost = round((mass_pipe * cost_pipe + mass_isolation * cost_isolation +
                          pipe_length * cost_installation),2)

            pipe_dict[pipe]["GWP [kg CO2-eq]"] = emissions
            pipe_dict[pipe]["Cost [€]"] = cost
            pipe_dict[pipe]["Mass Pipe [kg]"] = mass_pipe
            pipe_dict[pipe]["Mass Isolation [kg]"] = mass_isolation
            pipe_dict[pipe]["Pipe Length [m]"] = pipe_length

            total_pipe_mass += mass_pipe
            total_isolation_mass += mass_isolation
            total_pipe_length += pipe_length
            total_gwp += emissions
            total_cost += cost

        return pipe_dict, total_gwp, total_cost, total_pipe_mass, total_isolation_mass

    def calulcate_components(self,
                             component_dict: dict,
                             material_emission_dict: dict,
                             material_cost_dict: dict,
                             radiator_dict: dict):

        if self.playground.sim_settings.heat_delivery_type == "Radiator":
            mapping = {"radiator_forward": "Heizkoerper",}
        elif self.playground.sim_settings.heat_delivery_type == "UFH":
            ufh_pipe_type = self.playground.sim_settings.ufh_pipe_type
            mapping = {'radiator_forward': '', "radiator_forward_extra": "Heizkoerper"}

        component_material_emission_cost = {}
        pump_component = {}
        total_gwp_component = 0
        total_cost_component = 0

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
                                cost = material_amount * material_cost_dict[mapping[key]]
                            else:
                                mapping[key] = "Heizkoerper"
                                material_amount = material_value["Mass [kg]"]
                                length = material_value["Length [m]"]
                                radiator = radiator_dict[int(material_value["Model"])]
                                cost = length * radiator["Trendlinie a"] * ((length * 1000) ** radiator["Trendlinie e"])
                        elif self.playground.sim_settings.heat_delivery_type == "Radiator":
                            material_amount = material_value["Mass [kg]"]
                            length = material_value["Length [m]"]
                            radiator = radiator_dict[int(material_value["Model"])]
                            cost = length * radiator["Trendlinie a"] * ((length * 1000) ** radiator["Trendlinie e"])
                        gwp = material_emission_dict[mapping[key]]
                        emissions = round(material_amount * gwp,2)
                        total_gwp_component += emissions
                        cost = round(cost, 2)
                        total_cost_component += cost
                        material_value["GWP [kg CO2-eq]"] = emissions
                        material_value["Cost [€]"] = cost

                        if key not in component_material_emission_cost:
                            component_material_emission_cost[comp_material] = {}
                        component_material_emission_cost[comp_material]["Type"] = mapping[key]
                        component_material_emission_cost[comp_material]["GWP [kg CO2-eq]"] = emissions
                        component_material_emission_cost[comp_material]["Cost [€]"] = cost
                else:
                    if "Pumpe" in corresponding_material:
                        if comp_material not in pump_component:
                            pump_component[comp_material] = {}
                        pump_component[comp_material]["Power [kW]"] = material_value["Power [kW]"]
        return component_material_emission_cost, pump_component, total_gwp_component, total_cost_component

    def write_xlsx(self,
                   pipe_dict,
                   component_material_emission_cost,
                   pump_component,
                   total_pipe_mass,
                   total_isolation_mass,
                   total_gwp_pipe,
                   total_gwp_component,
                   total_cost_pipe,
                   total_cost_component):


        data = {}
        data["Pump"] = pump_component
        data["Component"] = component_material_emission_cost
        data["Component"]["Total"] = {"Type": "",
                                      "GWP [kg CO2-eq]": total_gwp_component,
                                      "Cost [€]": total_cost_component}
        data["Pipe"] = pipe_dict
        data["Pipe"]["Total"] = {"Material": "",
                                 "Mass Pipe [kg]": total_pipe_mass,
                                 "Mass Isolation [kg]": total_isolation_mass,
                                 "GWP [kg CO2-eq]": total_gwp_pipe,
                                 "Cost [€]": total_cost_pipe}
        data["Totals"] = {}
        data["Totals"]["GWP [kg CO2-eq]"] = {}
        data["Totals"]["GWP [kg CO2-eq]"]["Pipe"] = total_gwp_pipe
        data["Totals"]["GWP [kg CO2-eq]"]["Component"] = total_gwp_component
        data["Totals"]["GWP [kg CO2-eq]"]["Total"] = total_gwp_pipe + total_gwp_component
        data["Totals"]["Cost [€]"] = {}
        data["Totals"]["Cost [€]"]["Pipe"] = total_cost_pipe
        data["Totals"]["Cost [€]"]["Component"] = total_cost_component
        data["Totals"]["Cost [€]"]["Total"] = total_cost_pipe + total_cost_component

        with pd.ExcelWriter(self.paths.export / "lca_lcc_hydraulic_system.xlsx") as writer:
            for key, values in data.items():
                df = pd.DataFrame.from_dict(data[key], orient="columns")
                if key != "Total":
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