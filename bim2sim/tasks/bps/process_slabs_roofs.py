from bim2sim.kernel.decision import BoolDecision, DecisionBunch
from bim2sim.elements.bps_elements import Slab, GroundFloor, Floor, Roof
from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_elements


class ProcessSlabsRoofs(ITask):
    """Handles decomposed roofs and wrong slab elements."""

    reads = ('elements',)
    touches = ('elements',)

    def run(self, elements: dict):
        for element in elements.copy().values():
            if type(element).__bases__[0] is Slab or type(element) is Slab:
                elements = self.recognize_decomposed_roofs(element, elements)
                self.better_slab_class(element)
        return elements,

    @staticmethod
    def better_slab_class(element):
        """do a recheck of selected classes if necessary, and changes it to a
        new class
        based on criteria and information of the space boundaries"""
        if len(element.space_boundaries) > 0:
            # TODO Is Floor the most correct here? We might create a new class
            #  for such elements
            new_class = Floor
            if element.is_external is True:
                new_class = Roof
                if element.top_bottom:
                    if len(element.top_bottom) == 1:
                        if element.top_bottom[0] == 'BOTTOM':
                            new_class = GroundFloor
            if new_class != type(element):
                element.__class__ = new_class
                # ToDo: More clean way to do this?
                # ToDo: Maybe remove ald element and add new element

    def recognize_decomposed_roofs(self, element, elements):
        """recognize the roofs that are decomposed on another slabs, and after
        that:
        * set decompositions on decomposed element
        * set decomposition properties on decomposed element"""
        if element.ifc.IsDecomposedBy:
            for decomp in element.ifc.IsDecomposedBy:
                for inst_ifc in decomp.RelatedObjects:
                    inst = elements.get(inst_ifc.GlobalId, None)
                    if inst:
                        self.set_decompositions(element, inst)
                        self.set_decomposition_properties(element, inst)
                        del elements[inst.guid]
        return elements

    @staticmethod
    def set_decompositions(element, d_element):
        """set decompositions of a decomposed slab and vice versa as list in the
        element"""
        if not hasattr(element, 'decomposed_by'):
            element.decomposed_by = []
        element.decomposed_by.append(d_element)
        if not hasattr(d_element, 'decomposes'):
            d_element.decomposes = []
        d_element.decomposes.append(element)

    @staticmethod
    def set_decomposition_properties(element, d_element):
        """set attributes of decomposes element, if attribute of decomposed
        element not available or invalid"""
        # when decomposed,decomposes element has attributes of the decomposed
        # element
        if len(d_element.space_boundaries):
            for sb in d_element.space_boundaries:
                if sb not in element.space_boundaries:
                    element.space_boundaries.append(sb)

        for tz in d_element.thermal_zones:
            if tz not in element.thermal_zones:
                element.thermal_zones.append(tz)
            if element not in tz.bound_elements:
                tz.bound_elements.append(element)
            d_element_index = tz.bound_elements.index(d_element)
            del tz.bound_elements[d_element_index]

        for attr, (value, available) in element.attributes.items():
            if not value and hasattr(d_element, attr):
                if getattr(d_element, attr):
                    setattr(element, attr, getattr(d_element, attr))
        if hasattr(element, 'layerset') and hasattr(d_element, 'layerset'):
            if element.layerset and d_element.layerset:
                element.layerset = d_element.layerset
                element.layerset.parents.append(element)
