from diss.examples.d_02_cfd.cfd_DH_VR_down_fvDOM_30_bm12 import run_example_18 as vr_down_8o
from diss.examples.d_02_cfd.cfd_DH_VR_side_fvDOM_30_bm12 import run_example_18 as vr_side_8o
from diss.examples.d_02_cfd.cfd_DH_VR_8o8p_side_fv30_bm12 import run_example_18 as vr_side_8o8p


def run_VR_tests():
    vr_down_8o()
    vr_side_8o()
    vr_side_8o8p()

if __name__ == '__main__':
    run_VR_tests()
