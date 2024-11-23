from diss.examples.d_02_cfd.cfd_DH_IFC_HVAC_ovf_P1_30_bm05 import run_example_18 as bm05
from diss.examples.d_02_cfd.cfd_DH_IFC_HVAC_ovf_P1_30_bm10 import run_example_18 as bm10
from diss.examples.d_02_cfd.cfd_DH_IFC_HVAC_ovf_P1_30_bm15 import run_example_18 as bm15
from diss.examples.d_02_cfd.cfd_DH_IFC_HVAC_ovf_P1_30_bm20 import run_example_18 as bm20
from diss.examples.d_02_cfd.cfd_DH_IFC_HVAC_ovf_P1_30_bm25 import run_example_18 as bm25
from diss.examples.d_02_cfd.cfd_DH_IFC_HVAC_ovf_P1_30_bm30 import run_example_18 as bm30


def run_bm_tests():
    bm05()
    bm10()
    bm15()
    bm20()
    bm25()
    bm30()

if __name__ == '__main__':
    run_bm_tests()
