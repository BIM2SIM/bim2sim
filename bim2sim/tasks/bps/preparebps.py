from bim2sim.kernel.decision import BoolDecision, DecisionBunch
from bim2sim.elements.bps_elements import Slab, GroundFloor, Floor, Roof
from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_elements


class PrepareBPS(ITask):
    """Sets common settings for heating and cooling for thermal zones and
    handles decomposed roofs."""

    reads = ('elements', 'space_boundaries',)
    touches = ('tz_elements', 'elements',)

    def __init__(self, playground):
        super().__init__(playground)
        self.tz_elements = {}
        self.elements = {}

    def run(self, elements: dict, space_boundaries: dict):
        self.elements = elements
        yield from self.prepare_thermal_zones(elements,
                                              self.playground.sim_settings)
        self.prepare_elements(elements)
        self.tz_elements = dict(sorted(self.tz_elements.items()))
        self.elements = dict(sorted(self.elements.items()))

        return self.tz_elements, self.elements

    def prepare_thermal_zones(self, elements, sim_settings):
        """prepare the thermal zones by setting space properties, with
        cooling and heating"""

        thermal_zones = filter_elements(elements, 'ThermalZone')
        self.tz_elements = {inst.guid: inst for inst in thermal_zones}

        if len(self.tz_elements) == 0:
            # ToDo: Geometric Method before SB creation
            self.logger.warning("Found no spaces by semantic detection")
            decision = BoolDecision("Try to detect zones by geometrical?")
            yield DecisionBunch([decision])
            use = decision.value
            if use:
                self.recognize_zone_geometrical()
            else:
                raise NotImplementedError("No Spaces found in IFC. No "
                                          "Simulation model can be generated.")

        self.set_space_properties(sim_settings)

        self.logger.info("Found %d thermal zone entities",
                         len(self.tz_elements))

    def set_space_properties(self, sim_settings):
        """set cooling and heating values based on simulation settings"""

        for tz in self.tz_elements.values():
            tz.with_cooling = sim_settings.cooling
            tz.with_heating = sim_settings.heating
            if sim_settings.deactivate_ahu:
                tz.with_ahu = False

    def recognize_zone_geometrical(self):
        """Recognizes zones/spaces by geometric detection"""
        raise NotImplementedError

    def prepare_elements(self, elements):
        """prepare elements based on recheck, can change classes"""
        for inst in elements.copy().values():
            self.prepare_element_class(inst, elements)

    def prepare_element_class(self, element, elements):
        """prepare elements based on different functions:
        * slabs class recheck
        * recognize decomposed roofs"""

        if type(element).__bases__[0] is Slab or type(element) is Slab:
            self.recognize_decomposed_roofs(element, elements)
            self.better_slab_class(element)

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
                        del self.elements[inst.guid]

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
