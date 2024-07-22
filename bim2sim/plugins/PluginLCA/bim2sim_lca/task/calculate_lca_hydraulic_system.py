import pandas as pd
import json
import math
from pathlib import Path
from bim2sim.tasks.base import ITask

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

            pipe_dict[index] = {"Materialmenge": row["Materialmenge [kg]"],
                                "Material": row["material"],
                                "dammung": row["Material dammung [kg]"]}
        return pipe_dict

    def load_component_data(self):
        df = pd.read_excel(self.playground.sim_settings.hydraulic_system_material_xlsx, sheet_name="Komponenten")
        pipe_dict = {}
        for  index, row in df.iterrows():
            pipe_dict[index] = {"type": row["type"],
                                "material": row["material"],
                                "material_mass": row["material_mass"],
                                "Power": row["Power"]}
        return pipe_dict

    def calulcate_emission_pipe(self,
                                pipe_dict:dict,
                                material_emission_dict:dict):


        emission_pipe = material_emission_dict[self.playground.sim_settings.pipe_type]
        emission_dammung = material_emission_dict["Rohrisolierung"]

        copy_pipe_dict = pipe_dict.copy()
        for pipe in copy_pipe_dict:

            material = copy_pipe_dict[pipe]["Materialmenge"]
            if isinstance(material, float):
                continue
            material = float(material.split(" ")[0])

            material_dammung = copy_pipe_dict[pipe]["dammung"]
            if isinstance(material_dammung, float):
                continue
            material_dammung = float(material_dammung.split(" ")[0])
            #material_float = float(re.findall(r'\d+\.\d+', material)[0])
            #emissions = float(material_float)*emission_pipe
            #emission_dammung = float(material_dammung)
            #emissions_pipe = float(material) * emission_pipe
            emissions = float(material) * emission_pipe + float(material_dammung) * emission_dammung
            emission_dict = {"emission": emissions}
            material_dict = {"material": material}
            pipe_dict[pipe].update(emission_dict)
            pipe_dict[pipe].update(material_dict)
        #print(pipe_dict)
        #total_gwp = max(item['emission'] for item in pipe_dict.values())
        total_gwp = max(item.get('emission', 0) for item in pipe_dict.values())
        total_material_mass = max(item.get('material', 0) for item in pipe_dict.values())

        #total_material_mass = max(float(item.get('Materialmenge', 0)) for item in pipe_dict.values())
        #total_material_mass = (max(item['Materialmenge'] for item in pipe_dict.values()))

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
            corresponding_material = material_value["type"]
            for key in mapping_keys_list:
                if key in corresponding_material:
                    if "material_mass" in material_value:
                        if isinstance(material_value["material_mass"], str):
                            material_mass = round(float(material_value["material_mass"].split()[0]),3)
                        else:
                            material_mass = float(material_value["material_mass"])
                        gwp = material_emission_dict[mapping[key]]
                        if gwp != 0 and material_mass!= 0:
                            if not math.isinf(material_mass):
                                emissions = round(material_mass * gwp,4)
                                total_gwp_component += float(emissions)
                                material_value["emissions"] = emissions
                        if key not in component_material_emission:
                            component_material_emission[comp_material] = {}
                        component_material_emission[comp_material]["type"] = mapping[key]
                        component_material_emission[comp_material]["emissions"] = emissions
                else:
                    if "Pumpe" in corresponding_material:
                        if comp_material not in pump_component:
                            pump_component[comp_material] = {}
                        pump_component[comp_material]["Power"] = material_value["Power"]
        return component_material_emission, pump_component, total_gwp_component

    def write_xlsx(self,
                   pipe_dict,
                   total_gwp_pipe,
                   component_material_emission,
                   total_material_mass,
                   total_gwp_component,
                   pump_component
                   ):

        total_gwp = total_gwp_pipe + total_gwp_component

        data = {}
        data["pump"] = pump_component
        data["component"] = component_material_emission
        data["component"]["total_gwp_component"] = total_gwp_component
        data["pipe"] = pipe_dict
        data["pipe"]["total_gwp_pipe"] = total_gwp_pipe
        data["pipe"]["total_material_mass"] = total_material_mass
        data["total_gwp"] = total_gwp

        with pd.ExcelWriter(self.paths.export / "lca_hydraulic_system.xlsx") as writer:
            for key, values in data.items():
                if key == "total_gwp":
                    df = pd.DataFrame({"total_gwp": [data["total_gwp"]]})
                    df.to_excel(writer, sheet_name=key, index_label=key, index=True)
                else:
                    df = pd.DataFrame.from_dict(data[key], orient="columns")
                    df_transposed = df.transpose()
                    df_transposed.to_excel(writer, sheet_name=key, index_label=key, index=True)


