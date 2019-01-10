from MainLib import bim2sim
from ast import literal_eval
import re

class AixLib(bim2sim.SimulationBase):

    def __init__(self):
        super().__init__()
        
        # do stuff
        return

    def prepare(self, model):
        
        self.logger.info('preparing stuff')

        return

    def run(self):

        self.logger.info('doing stuff')

        return
    def create_modelica_table_from_list(self,curve):
        """

        :param curve:
        :return:
        """
        curve = literal_eval(curve)
        for key, value in curve.iteritems():
            # add first and last value to make sure there is a constant
            # behaviour before and after the given heating curve
            value = [value[0] - 5, value[1]] + value + [value[-2] + 5,
                                                        value[-1]]
            # transform to string and replace every second comma with a
            # semicolon to match modelica syntax
            value = str(value)
            value = re.sub('(,[^,]*),', r'\1;', value)
            setattr(self, key, value)
