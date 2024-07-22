import requests
from pathlib import Path
import json

class Load_Technology_Parameter:


    reads = ()
    touches = ('emission_parameter_dict',)


    def run(self):

        print("###### Load material emission data from Ökobaudat! ######")

        mapping = {
            "A1-A3": "Herstellung",
            "A1": "Rohstoffbereitstellung",
            "A2": "Transport",
            "A3": "Herstellung",
            "A4-A5": "Errichtung",
            "A4": "Transport",
            "A5": "Einbau",
            "B1": "Nutzung",
            "B2": "Instandhaltung",
            "B3": "Reparatur",
            "B4": "Ersatz",
            "B5": "Umbau/Erneuerung",
            "B6": "Energieeinsatz",
            "B7": "Wassereinsatz",
            "C1": "Abbruch",
            "C2": "Transport",
            "C3": "Abfallbehandlung",
            "C4": "Beseitigung",
            "D": "Recyclingpotential"
        }


        #### Distribution emission data ####

        with open(Path(ModelParameter.root_doc_path, "emission", "emission_distribution_uuid.json"),
                  'r') as json_file:
            distribution_uuid = json.load(json_file)

        emission_data_distribution_system = {}
        gwp_data = {}

        for technology, uuid in distribution_uuid.items():
            print(technology)
            emission_data_distribution_system[technology] = {}
            gwp_data = Load_Technology_Parameter.load_gwp_from_oekobaudat(uuid)
            for key, value in gwp_data.items():
                mapped_key = mapping[key]
                emission_data_distribution_system[technology][mapped_key] = float(value)

        json_file = Path(ModelParameter.root_doc_path, "emission", 'emission_distribution_system.json')
        with open(json_file, 'w') as outfile:
            json.dump(emission_data_distribution_system, outfile, indent=3)

        #### Building material emission data ####

        with open(Path(ModelParameter.root_doc_path, "emission", "building_material_uuid.json"),
                  'r') as json_file:
            material_uuid_data_set = json.load(json_file)

        emission_data_building = {}
        gwp_data = {}

        for material, material_uuid_data in material_uuid_data_set.items():
            emission_data_building[material] = {}
            gwp_data = Load_Technology_Parameter.load_gwp_from_oekobaudat(material_uuid_data["uuid"])
            print(material)
            for key, value in gwp_data.items():
                mapped_key = mapping[key]
                emission_data_building[material][mapped_key] = float(value) * material_uuid_data["calculation_factor"]

        json_file = Path(ModelParameter.root_doc_path, "emission", 'building_material_emission.json')
        with open(json_file, 'w') as outfile:
            json.dump(emission_data_building, outfile, indent=3)

        print("###### Loading material emission data from Ökobaudat finished! ######")

        return emission_parameter_dict




    def load_gwp_from_oekobaudat(uuid: str):
        """
        Gibt das globale Erwärmungspotential nach Ökobaudat in Kategorien zurück
        :param uuid: UUID nach Ökobaudat
        :return: Globales Erwärmungspotential nach ÖKOBAUDAT, ReferenceUnit: Einheit für Berechnung z.B. kg oder m³
        """
        OKOBAU_URL = "https://oekobaudat.de/OEKOBAU.DAT/resource/datastocks/c391de0f-2cfd-47ea-8883-c661d294e2ba"

        """Fetches the data of a specific EPD given its UUID"""
        response = requests.get(f"{OKOBAU_URL}/processes/{uuid}?format=json&view=extended")

        response.raise_for_status()
        data = response.json()

        for entry in data['LCIAResults']['LCIAResult']:
            if entry['referenceToLCIAMethodDataSet']['shortDescription'][0]['value'] == "Global Warming Potential - total (GWP-total)" or \
                entry['referenceToLCIAMethodDataSet']['shortDescription'][0]['value'] == "Globales Erwärmungspotenzial - total (GWP-total)" or \
                entry['referenceToLCIAMethodDataSet']['shortDescription'][0]['value'] == "Globales Erwärmungspotenzial total (GWP-total)" or \
                entry['referenceToLCIAMethodDataSet']['shortDescription'][0]['value'] == "Global Warming Potential total (GWP-total)":

                results = {}
                for sub_entry in entry['other']['anies']:
                    if 'module' in sub_entry and 'value' in sub_entry:
                        results[sub_entry['module']] = sub_entry['value']
                break

        return results






