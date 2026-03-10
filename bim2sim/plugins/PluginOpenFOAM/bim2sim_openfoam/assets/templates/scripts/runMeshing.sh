#!/usr/bin/zsh
#SBATCH --job-name=JOBNAME

### Request the time you need for execution.
#SBATCH --time=MTIME

#### Request the memory you need for your job.
##SBATCH --mem-per-cpu=2600M

### Request & nodes
COMP_ACCOUNT
#SBATCH --nodes=NNODES
#SBATCH --ntasks=NPROCS

### Load the required module files
module load GCC/11.3.0
module load OpenMPI/4.1.4
module load OpenFOAM/v2206

### start the OpenFOAM binary in parallel, cf.
blockMesh
decomposePar -force
$MPIEXEC $FLAGS_MPI_BATCH snappyHexMesh -parallel -overwrite >logMeshing.compress

reconstructParMesh -mergeTol 1e-10 -constant
topoSet
setsToZones
checkMesh > logCheckMesh.compress