from bim2sim.tasks.base import ITask
import sys
import os
from butterfly.butterfly import decomposeParDict as decPD
import pathlib


class AddOpenFOAMComfort(ITask):
    """This ITask adds the openfoam comfort settings.
    """

    reads = ('openfoam_case',)
    touches = ()

    def __init__(self, playground):
        super().__init__(playground)

    def run(self, openfoam_case):
        if not self.playground.sim_settings.add_comfort:
            return
        openfoam_case.comfortDict = {
            'comfort1': {
                'type': 'comfort',
                'libs': '( "libfieldFunctionObjects.dll" )',
                'clothing': openfoam_case.current_zone.clothing_persons
                            + openfoam_case.current_zone.surround_clo_persons,
                'metabolicRate':
                    openfoam_case.current_zone.activity_degree_persons,
                'writeControl': 'writeTime',
                'writeInterval': '1'}}
        openfoam_case.controlDict.values['functions'].update(
            openfoam_case.comfortDict)

        openfoam_case.controlDict.save(openfoam_case.openfoam_dir)
