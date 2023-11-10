import os
from pathlib import Path

import pandas as pd

import openpyxl


class ComfortUtils:
    @staticmethod
    def convert_use_conditions_to_xls(json_file, result_path=""):
        """ convert a given UseConditions.json file to .xls.
        """
        df_json = pd.read_json(json_file)
        df_json = df_json.transpose()
        df_json.to_excel(result_path + 'UseConditions_EXTENDED.xlsx')

    @staticmethod
    def new_empty_json_keeping_first_keys(json_file):
        df_json = pd.read_json(json_file)
        json_keys = df_json.keys()
        new_json = pd.DataFrame(index=json_keys, columns=['clo', 'met'])
        new_json.to_excel('EmptyUseConditions.xlsx')

    @staticmethod
    def convert_xlsx_to_json(xls_name, json_name):
        file = pd.read_excel(xls_name)
        json_file = file.to_json(json_name)

    @staticmethod
    def convert_csv_to_json(csv_name, json_name, sep=';'):
        file = pd.read_csv(filepath_or_buffer=csv_name, sep=sep,
                           index_col=0).transpose()
        json_file = file.to_json(json_name, indent=4)

    @staticmethod
    def extend_use_conditions(json_name, use_conditions):
        file = pd.read_json(use_conditions).transpose()
        new_parameters_json = pd.read_json(json_name).transpose()

        # replace TEASER Template Values with new derived values from
        # ISO7730 and ASHRAE
        file['activity_degree_persons'] = \
            new_parameters_json['ISO7730_ASHRAE_Combined_met']
        file['fixed_heat_flow_rate_persons'] = \
            new_parameters_json['ISO7730_ASHRAE_Combined_WperPerson']
        # Set new clothing params (clo values) derived from ISO7730 and ASHRAE
        file['clothing_persons'] = \
            new_parameters_json['ISO7730_ASHRAE_Combined_clo']
        file['surround_clo_persons'] = \
            new_parameters_json['surround_insulation_combined_clo']

        # write new comfort use conditions to the asset directory.
        comfort_use_conditions = str(os.path.splitext(use_conditions)[0]) + \
                                 'Comfort.json'
        file.transpose().to_json(comfort_use_conditions, indent=4)



if __name__ == '__main__':
    # use_conditions_path = Path(__file__).parent.parent.parent.parent.parent \
    #                       / "assets/enrichment/usage/UseConditions.json"
    # ComfortUtils.convert_use_conditions_to_xls(
    #     use_conditions_path)
    # ComfortUtils.new_empty_json_keeping_first_keys(use_conditions_path)
    usage_path = Path(__file__).parent.parent.parent.parent.parent / \
                 'assets' / 'enrichment' / 'usage'
    new_json_name = 'activity_clothing_ISO7730_ASHRAE_V002.json'

    ComfortUtils.convert_csv_to_json(
        r'C:\Users\richter\sciebo\03-Paperdrafts'
        r'\MDPI_SpecialIssue_Comfort_Climate'
        r'\activity_clothing_ISO7730_ASHRAE_V002.csv', new_json_name)
    ComfortUtils.extend_use_conditions(new_json_name, usage_path /
                                       'UseConditions.json')

