import pandas as pd
import json
import math
from pathlib import Path
from bim2sim.tasks.base import ITask
from bim2sim.elements.mapping.units import ureg

class CalculateEmissionHydraulicSystem(ITask):

    reads = ('material_emission_dict',)
    touches = ()

    def run(self, material_emission_dict):

        pipe_dict = self.load_pipe_data()
        component_dict = self.load_component_data()
        pipe_dict, total_gwp_pipe, total_material_mass = self.calulcate_emission_pipe(pipe_dict=pipe_dict, material_emission_dict=material_emission_dict)
        component_material_emission, pump_component, total_gwp_component = self.calulcate_emission_technology(component_dict=component_dict, material_emission_dict=material_emission_dict)
        self.write_xlsx(pipe_dict=pipe_dict,
                        component_material_emission=component_material_emission,
                        pump_component=pump_component,
                        total_material_mass=total_material_mass,
                        total_gwp_pipe=total_gwp_pipe,
                        total_gwp_component=total_gwp_component)

    def load_pipe_data(self):
        df = pd.read_excel(self.playground.sim_settings.hydraulic_system_material_xlsx, sheet_name="pipe")
        pipe_dict = {}
        for  index, row in df.iterrows():

            pipe_dict[index] = {"Material": row["material"],
                                "Mass Pipe [kg]": row["Materialmenge [kg]"],
                                "Mass Isolation [kg]": row["Material dammung [kg]"]}
        return pipe_dict

    def load_component_data(self):
        df = pd.read_excel(self.playground.sim_settings.hydraulic_system_material_xlsx, sheet_name="Komponenten")
        pipe_dict = {}
        for  index, row in df.iterrows():
            pipe_dict[index] = {"Type": row["type"],
                                "Material": row["material"],
                                "Mass [kg]": self.ureg_to_float(row["material_mass"], ureg.kg),
                                "Power [kW]": self.ureg_to_str(row["Power"], ureg.kilowatt)}
        return pipe_dict

    def calulcate_emission_pipe(self,
                                pipe_dict:dict,
                                material_emission_dict:dict):


        emission_pipe = material_emission_dict[self.playground.sim_settings.pipe_type]
        emission_isolation = material_emission_dict["Rohrisolierung"]

        copy_pipe_dict = pipe_dict.copy()
        for pipe in copy_pipe_dict:

            mass_pipe = copy_pipe_dict[pipe]["Mass Pipe [kg]"]
            if isinstance(mass_pipe, float):
                continue
            mass_pipe = float(mass_pipe.split(" ")[0])

            material_isolation = copy_pipe_dict[pipe]["Mass Isolation [kg]"]
            if isinstance(material_isolation, float):
                continue
            material_isolation = float(material_isolation.split(" ")[0])

            emissions = float(mass_pipe) * emission_pipe + float(material_isolation) * emission_isolation
            emission_dict = {"GWP [kg CO2-eq]": emissions}
            pipe_dict[pipe].update(emission_dict)

        total_gwp = max(item.get('GWP [kg CO2-eq]', 0) for item in pipe_dict.values())
        total_material_mass = max(item.get('Mass Pipe [kg]', 0) for item in pipe_dict.values())


        return pipe_dict, total_gwp, total_material_mass

    def calulcate_emission_technology(self,
                                    component_dict: dict,
                                    material_emission_dict: dict):

        mapping = {"radiator_forward": "Heizkoerper",
                   }
        component_material_emission = {}
        pump_component = {}
        total_gwp_component = 0

        mapping_keys_list = list(mapping.keys())
        for comp_material, material_value in component_dict.items():
            corresponding_material = material_value["Type"]
            for key in mapping_keys_list:
                if key in corresponding_material:
                    if "Mass [kg]" in material_value:
                        if isinstance(material_value["Mass [kg]"], str):
                            material_mass = round(float(material_value["Mass [kg]"].split()[0]),3)
                        else:
                            material_mass = float(material_value["Mass [kg]"])
                        gwp = material_emission_dict[mapping[key]]
                        if gwp != 0 and material_mass!= 0:
                            if not math.isinf(material_mass):
                                emissions = round(material_mass * gwp,4)
                                total_gwp_component += float(emissions)
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
                   total_material_mass,
                   total_gwp_component,
                   pump_component
                   ):


        data = {}
        data["Pump"] = pump_component
        data["Component"] = component_material_emission
        data["Component"]["Total GWP"] = total_gwp_component
        data["Pipe"] = pipe_dict
        data["Pipe"]["Total GWP"] = total_gwp_pipe
        data["Pipe"]["Total Mass"] = total_material_mass
        data["Total GWP"] = {}
        data["Total GWP"]["GWP [kg CO2-eq]"] = {}
        data["Total GWP"]["GWP [kg CO2-eq]"]["Pipe"] = total_gwp_pipe
        data["Total GWP"]["GWP [kg CO2-eq]"]["Component"] = total_gwp_component
        data["Total GWP"]["GWP [kg CO2-eq]"]["Total"] = total_gwp_pipe + total_gwp_component

        with pd.ExcelWriter(self.paths.export / "lca_hydraulic_system.xlsx") as writer:
            for key, values in data.items():
                df = pd.DataFrame.from_dict(data[key], orient="columns")
                df_transposed = df.transpose()
                df_transposed.to_excel(writer, sheet_name=key, index_label=key, index=True)




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