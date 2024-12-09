from diss.examples.d_02_cfd.cfd_FZK_fv_0 import run_example_1 as fv0
from diss.examples.d_02_cfd.cfd_FZK_fv_30 import run_example_1 as fv30
from diss.examples.d_02_cfd.cfd_FZK_fv_100 import run_example_1 as fv100
from diss.examples.d_02_cfd.cfd_FZK_noR_0 import run_example_1 as nr0
from diss.examples.d_02_cfd.cfd_FZK_noR_30 import run_example_1 as nr30
from diss.examples.d_02_cfd.cfd_FZK_noR_100 import run_example_1 as nr100
from diss.examples.d_02_cfd.cfd_FZK_P1_0 import run_example_1 as p0
from diss.examples.d_02_cfd.cfd_FZK_P1_30 import run_example_1 as p30
from diss.examples.d_02_cfd.cfd_FZK_P1_100 import run_example_1 as p100


def run_radiator_tests():
    fv0()
    fv30()
    fv100()
    nr0()
    nr30()
    nr100()
    p0()
    p30()
    p100()

if __name__ == '__main__':
    run_radiator_tests()
