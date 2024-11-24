import os
from pathlib import Path


def run_checkMesh(of_path):
    cwd = os.getcwd()
    os.chdir(of_path / 'export'/'OpenFOAM')
    os.system('pwd')
    # os.system('conda deactivate')
    os.system('checkMesh > logCheckMesh')
    os.chdir(cwd)


if __name__ == '__main__':
    temp_dir = Path('/mnt/sim/SimData/CFD-temp')
    for diss_dir in temp_dir.glob('diss_DH_ovf_P3_b*_*'):
        try:
            run_checkMesh(diss_dir)
        except:
            print(f'failed for {diss_dir}')
