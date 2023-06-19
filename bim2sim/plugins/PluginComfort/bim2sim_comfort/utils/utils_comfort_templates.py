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
        file = pd.read_csv(csv_name, sep, index_col=0).transpose()
        json_file = file.to_json(json_name, indent=4)


if __name__ == '__main__':
    # use_conditions_path = Path(__file__).parent.parent.parent.parent.parent \
    #                       / "assets/enrichment/usage/UseConditions.json"
    # ComfortUtils.convert_use_conditions_to_xls(
    #     use_conditions_path)
    # ComfortUtils.new_empty_json_keeping_first_keys(use_conditions_path)
    ComfortUtils.convert_csv_to_json(
        r'C:\Users\Richter_lokal\sciebo\03-Paperdrafts'
        r'\MDPI_SpecialIssue_Comfort_Climate\activity_ISO7730_ASHRAE_V001.csv',
                                      'activity_ISO7730_ASHRAE_V001.json')

