from pathlib import Path

import bim2sim
from bim2sim.kernel.ifc_file import IfcFileClass
from bim2sim.utilities.svg_utils import convert_ifc_to_svg, \
    split_svg_by_storeys, combine_svgs_complete
from bim2sim.utilities.types import IFCDomain

# total_ifc_path = (Path(bim2sim.__file__).parent.parent /
#                   'test/resources/arch/ifc/FM_ARC_DigitalHub_with_SB89.ifc')
#
# ifc_file_cls = IfcFileClass(
#     ifc_path=total_ifc_path,
#     ifc_domain=IFCDomain.arch,
#     reset_guids=False)
#
# svg_path = convert_ifc_to_svg(ifc_file_cls, Path("D:/01_Kurzablage/fp_testing"))
# split_svg_by_storeys(svg_path)


svg_main = Path("D:/01_Kurzablage/compare_EP_TEASER_DH/bim2sim_project_teaser/export/TEASER/SimResults/FM_ARC_DigitalHub_with_SB89")
combine_svgs_complete(str(svg_main), ["1OVsTAdVr0zxMeLRn9FNmI"])
combine_svgs_complete(str(svg_main), ["1OVsTAdVr0zxMeLRn9FNo$"])
combine_svgs_complete(str(svg_main), ["1OVsTAdVr0zxMeLRn9FNzI"])