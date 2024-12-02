import requests
from pathlib import Path
import json
import bim2sim
from bim2sim.tasks.base import ITask
import threading

class LoadMaterialEmissionParameter(ITask):

    reads = ()
    touches = ('material_emission_dict',)

    def run(self):

        self.lock = threading.Lock()

        self.logger.info("###### Load material emission data from Ökobaudat! ######")

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
        material_emissions_file_path = Path(
            Path(bim2sim.__file__).parent, r"assets/enrichment/material/MaterialEmissions.json")
        self.lock.acquire()
        with open(material_emissions_file_path,'r') as json_file:
            material_emission_parameter_dict = json.load(json_file)
        self.lock.release()

        if self.playground.sim_settings.update_emission_parameter_from_oekobdauat:
            self.logger.info("Update material emission parameter from Ökobaudat")
            gwp_data = {}
            for material, material_data in material_emission_parameter_dict.items():
                print(f"Update material {material}")
                oekobaudat_uuid = material_emission_parameter_dict[material]["oekobaudat_uuid"]
                oekobaudat_calculation_factor = material_emission_parameter_dict[material]["oekobaudat_calculation_factor"]
                gwp_data = self.load_gwp_from_oekobaudat(oekobaudat_uuid)
                material_emission_parameter_dict[material] = {}
                material_emission_parameter_dict[material]["oekobaudat_uuid"] = oekobaudat_uuid
                material_emission_parameter_dict[material]["oekobaudat_calculation_factor"] = oekobaudat_calculation_factor
                for key, value in gwp_data.items():
                    mapped_key = mapping[key]
                    material_emission_parameter_dict[material][mapped_key] = float(value)

            with open(material_emissions_file_path, 'w') as json_file:
                json.dump(material_emission_parameter_dict, json_file, indent=3)
            self.logger.info("Finished updating material emission parameter from Ökobaudat")

        material_emission_dict = {}
        for material in material_emission_parameter_dict.keys():
            emission_material = 0
            for key, value in material_emission_parameter_dict[material].items():
                if key != "oekobaudat_uuid" and key != "oekobaudat_calculation_factor":
                    emission_material += value
            material_emission_dict[material] = emission_material * material_emission_parameter_dict[material]["oekobaudat_calculation_factor"]

        return material_emission_dict,


    @staticmethod
    def load_gwp_from_oekobaudat(uuid: str):
        """
        Gibt das globale Erwärmungspotential nach Ökobaudat in Kategorien zurück
        :param uuid: UUID nach Ökobaudat
        :return: Globales Erwärmungspotential nach ÖKOBAUDAT, ReferenceUnit: Einheit für Berechnung z.B. kg oder m³
        """
        OKOBAU_URL = "https://oekobaudat.de/OEKOBAU.DAT/resource/datastocks/ca70a7e6-0ea4-4e90-a947-d44585783626"

        """Fetches the data of a specific EPD given its UUID"""
        response = requests.get(f"{OKOBAU_URL}/processes/{uuid}?format=json&view=extended", verify=False)

        response.raise_for_status()
        data = response.json()

        results = {}
        for entry in data['LCIAResults']['LCIAResult']:
            if entry['referenceToLCIAMethodDataSet']['shortDescription'][1]['value'] == (
            "Global Warming Potential - total (GWP-total)") or \
                    entry['referenceToLCIAMethodDataSet']['shortDescription'][1]['value'] == (
            "Globales Erwärmungspotenzial - total (GWP-total)") or \
                    entry['referenceToLCIAMethodDataSet']['shortDescription'][1]['value'] == (
            "Globales Erwärmungspotenzial total (GWP-total)") or \
                    entry['referenceToLCIAMethodDataSet']['shortDescription'][1]['value'] == (
            "Global Warming Potential total (GWP-total)"):

                # Initialisieren eines leeren Dictionaries für GWP-total
                results = {}
                # Loop durch alle 'other' Elemente
                for sub_entry in entry['other']['anies']:
                    # Prüfen, ob 'module' als Schlüssel in 'sub_entry' vorhanden ist
                    if 'module' in sub_entry and 'value' in sub_entry:
                        # Hinzufügen des Wertes zum Dictionary
                        results[sub_entry['module']] = sub_entry['value']
                break


        return results








