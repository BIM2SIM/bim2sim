from diss.examples.d_02_cfd.cfd_DH_IFC_HVAC_ovf_fvDOM_30_bm05 import run_example_18 as bm05
from diss.examples.d_02_cfd.cfd_DH_IFC_HVAC_ovf_fvDOM_30_bm07 import run_example_18 as bm07
from diss.examples.d_02_cfd.cfd_DH_IFC_HVAC_ovf_fvDOM_30_bm08 import run_example_18 as bm08
from diss.examples.d_02_cfd.cfd_DH_IFC_HVAC_ovf_fvDOM_30_bm10 import run_example_18 as bm10
from diss.examples.d_02_cfd.cfd_DH_IFC_HVAC_ovf_fvDOM_30_bm12 import run_example_18 as bm12
from diss.examples.d_02_cfd.cfd_DH_IFC_HVAC_ovf_fvDOM_30_bm14 import run_example_18 as bm14
from diss.examples.d_02_cfd.cfd_DH_IFC_HVAC_ovf_fvDOM_30_bm15 import run_example_18 as bm15
from diss.examples.d_02_cfd.cfd_DH_IFC_HVAC_ovf_fvDOM_30_bm20 import run_example_18 as bm20
from diss.examples.d_02_cfd.cfd_DH_IFC_HVAC_ovf_fvDOM_30_bm25 import run_example_18 as bm25
from diss.examples.d_02_cfd.cfd_DH_IFC_HVAC_ovf_P1_30_bm30 import run_example_18 as bm30


def run_bm_tests():
    bm05()
    bm07()
    bm08()
    bm10()
    bm12()
    bm14()
    bm15()
    bm20()
    bm25()

if __name__ == '__main__':
    run_bm_tests()
