from bim2sim.tasks.base import ITask
import sys
import os
import logging
from butterfly.butterfly import decomposeParDict as decPD
import pathlib

logger = logging.getLogger(__name__)


class RunOpenFOAMMeshing(ITask):
    """This ITask runs the openfoam meshing on linux systems.

    In case of error messages, please check the following hints, especially
    when working with Anaconda environments and PyCharm.
    - Check which version of OpenFOAM you have installed and if you can
    access it from the terminal (e.g. 'blockMesh'/'which blockMesh'). If the
    specified path is not the one you'd like to use, please add the OpenFOAM
    installation path to the PATH system variable.
    - Check which version of OpenMPI you have installed and if you can
    access it from the terminal (e.g. 'mpirun'/'which mpirun'). Make sure to
    not use the MPI included in Anaconda and adjust the path in the .bashrc
    accordingly or set a symbolic link.
    - For error messages like: 'error loading shared libraries', please make
    sure that PyCharm includes all system path variables, especially
    LD_LIBRARY_PATH by checking Run Configurations -> Environment Variables.
    If it is not included automatically, add it manually. The value must be
    the same as the output you get from 'echo $LD_LIBRARY_PATH'.
    """

    reads = ('openfoam_case', )
    touches = ()

    def __init__(self, playground):
        super().__init__(playground)

    def run(self, openfoam_case):
        if not self.playground.sim_settings.run_meshing:
            return 
        
        if not sys.platform == 'linux':
            logger.warning('Execution on non-Linux systems is not '
                           'recommended. Meshing aborted.')
            return

        of_path = openfoam_case.openfoam_dir
        logger.warning("Meshing in progress. This will take several minutes.")
        # Use half of the available processes
        procs = os.cpu_count()
        # procs = round(procs / 4) * 2
        distrib = self.split_into_three_factors(procs)

        # Write updated distribution to decomposeParDict
        dPpath = of_path / 'system' / 'decomposeParDict'
        decomposeParDict = decPD.DecomposeParDict()
        decomposeParDict = decomposeParDict.from_file(dPpath)
        decomposeParDict.set_value_by_parameter('numberOfSubdomains',
                                                str(procs))
        hc1 = decomposeParDict.get_value_by_parameter('hierarchicalCoeffs')
        distrib = '(' + str(distrib[0]) + ' ' + str(distrib[1]) + ' ' + \
                  str(distrib[2]) + ')'
        hc1['n'] = distrib
        decomposeParDict.set_value_by_parameter('hierarchicalCoeffs', hc1)
        decomposeParDict.save(project_folder=of_path)

        # execution
        cwd = os.getcwd()
        os.chdir(of_path)
        os.system('pwd')
        # os.system('conda deactivate')
        os.system('blockMesh')
        os.system('decomposePar -force')
        logger.info('Writing snappyHexMesh output to file \'logMeshing\'.')
        os.system('mpiexec --oversubscribe -np ' + str(procs) + ' snappyHexMesh -parallel '
                                                '-overwrite > logMeshing')
        os.system('reconstructParMesh -mergeTol 1e-10 -constant')
        os.system('topoSet')
        os.system('setsToZones')
        os.system('checkMesh')
        os.chdir(cwd)

    @staticmethod
    def prime_factors(n):
        factors = []
        divisor = 2
        while n > 1:
            while n % divisor == 0:
                factors.append(divisor)
                n //= divisor
            divisor += 1
        return factors

    def split_into_three_factors(self, n):
        factors = self.prime_factors(n)
        factors.sort()
        groups = []
        for i, factor in enumerate(factors):
            groups.append(factor)
        while len(groups) < 3:
            groups.append(1)
        res = len(groups) - 3
        for i in range(res):
            groups[i] = groups[i] * groups[-1]
            groups.pop()
        return groups
