from bim2sim.tasks.base import ITask
import sys
import os
from butterfly.butterfly import decomposeParDict as dcpP


class InitializeOpenFOAMProject(ITask):
    """This ITask runs the OpenFOAM meshing on linux systems.
    """

    reads = ()
    touches = ()

    def __init__(self, playground):
        super().__init__(playground)
        self.base_path = self.paths + '/OpenFOAM'

    def run(self):
        if not sys.platform == 'linux':
            print('Execution on non-Linux systems is not recommended.')
            return
        self.run_meshing(self.base_path)
        self.run_simulation(self.base_path)

    def run_meshing(self, of_path):
        run = input(
            "This will take several minutes. Proceed anyways? [Y/n] \n")
        if run == 'Y':
            procs = os.cpu_count()
            procs = round(procs / 4) * 2
            distrib = self.split_into_three_factors(procs)
            dPpath = of_path + 'system/decomposeParDict'
            decomposeParDict = dcpP.DecomposeParDict()
            decomposeParDict = decomposeParDict.from_file(dPpath)
            decomposeParDict.set_value_by_parameter('numberOfSubdomains',
                                                    str(procs))
            hc1 = decomposeParDict.get_value_by_parameter('hierarchicalCoeffs')
            distrib = '(' + str(distrib[0]) + ' ' + str(
                distrib[1]) + ' ' + str(
                distrib[2]) + ')'
            hc1['n'] = distrib
            decomposeParDict.set_value_by_parameter('hierarchicalCoeffs', hc1)
            decomposeParDict.save(project_folder=of_path)

            # execution
            cwd = os.getcwd()
            print('current working directory: ' + cwd)
            os.chdir(of_path)
            os.system('pwd')
            os.system('blockMesh')
            os.system('decomposePar -force')
            print('Writing snappyHexMesh output to file \'logMeshing\'.')
            os.system('mpiexec -np ' + str(procs) + ' snappyHexMesh -parallel '
                                                    '-overwrite > logMeshing')
            print('Done meshing.')
            os.system('reconstructParMesh -mergeTol 1e-10 -constant')
            os.system('decomposePar -cellDist -dry-run')
            os.chdir(cwd)
            os.system('pwd')

    @staticmethod
    def run_simulation(of_path):
        run = input(
            "Warning: Meshing must be done in advance. \n This will take "
            "a while. Proceed anyways? [Y/n] \n")
        if run == 'Y':
            procs = os.cpu_count()
            procs = round(procs / 4) * 2
            cwd = os.getcwd()
            print('current working directory: ' + cwd)
            os.chdir(of_path)
            os.system('pwd')
            os.system('topoSet')
            os.system('setsToZones')
            os.system('decomposePar -force')
            print(
                'Writing buoyantSimpleFoam output to file \'logSimulation\'.')
            os.system('mpiexec -np ' + str(procs) + ' buoyantSimpleFoam '
                                                    '-parallel > logSimulation')
            print('Done simulating.')
            os.system('reconstructPar -latestTime')
            os.chdir(cwd)
            os.system('pwd')

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
        if len(groups) < 3:
            groups.append(1)
        return groups


if __name__ == "__main__":
    # run_meshing('/home/anna/Downloads/BA/OpenFOAM_114/')
    # run_simulation('/home/anna/Downloads/BA/OpenFOAM_114/')
    pass
