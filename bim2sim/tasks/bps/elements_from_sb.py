from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_elements


class CreateElementsFromSB(ITask):

    reads = ('elements',)

    def run(self, elements):
        if not self.playground.sim_settings.create_elements_from_sb:
            self.logger.warning("Skipping task CreateElementsFromSB as "
                                "sim_setting 'create_elements_from_sb' is set "
                                "to False.")
            return
        sbs = filter_elements(elements, 'space_boundaries')
        sbs_without_element = {}
        for guid, sb_ele in sbs.items():
            if sb_ele.bound_element == None:
                sbs_without_element[guid] = sb_ele

        for guid, sb_ele in sbs_without_element.items():
            top_bottom = sb_ele.top_bottom


