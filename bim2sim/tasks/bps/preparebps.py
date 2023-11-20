from bim2sim.kernel.decision import BoolDecision, DecisionBunch
from bim2sim.elements.bps_elements import Slab, GroundFloor, Floor, Roof
from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_elements


class Prepare(ITask):
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
            self.prepare_instance_class(inst, elements)

    def prepare_instance_class(self, instance, elements):
        """prepare elements based on different functions:
        * slabs class recheck
        * recognize decomposed roofs"""

        if type(instance).__bases__[0] is Slab or type(instance) is Slab:
            self.recognize_decomposed_roofs(instance, elements)
            self.better_slab_class(instance)

    @staticmethod
    def better_slab_class(instance):
        """do a recheck of selected classes if necessary, and changes it to a
        new class
        based on criteria and information of the space boundaries"""
        if len(instance.space_boundaries) > 0:
            # TODO Is Floor the most correct here? We might create a new class
            #  for such elements
            new_class = Floor
            if instance.is_external is True:
                new_class = Roof
                if instance.top_bottom:
                    if len(instance.top_bottom) == 1:
                        if instance.top_bottom[0] == 'BOTTOM':
                            new_class = GroundFloor
            if new_class != type(instance):
                instance.__class__ = new_class
                # ToDo: More clean way to do this?
                # ToDo: Maybe remove ald element and add new element

    def recognize_decomposed_roofs(self, instance, elements):
        """recognize the roofs that are decomposed on another slabs, and after
        that:
        * set decompositions on decomposed instance
        * set decomposition properties on decomposed instance"""
        if instance.ifc.IsDecomposedBy:
            for decomp in instance.ifc.IsDecomposedBy:
                for inst_ifc in decomp.RelatedObjects:
                    inst = elements.get(inst_ifc.GlobalId, None)
                    if inst:
                        self.set_decompositions(instance, inst)
                        self.set_decomposition_properties(instance, inst)
                        del self.elements[inst.guid]

    @staticmethod
    def set_decompositions(instance, d_instance):
        """set decompositions of a decomposed slab and vice versa as list in the
        instance"""
        if not hasattr(instance, 'decomposed_by'):
            instance.decomposed_by = []
        instance.decomposed_by.append(d_instance)
        if not hasattr(d_instance, 'decomposes'):
            d_instance.decomposes = []
        d_instance.decomposes.append(instance)

    @staticmethod
    def set_decomposition_properties(instance, d_instance):
        """set attributes of decomposes instance, if attribute of decomposed
        instance not available or invalid"""
        # when decomposed,decomposes instance has attributes of the decomposed
        # instance
        if len(d_instance.space_boundaries):
            for sb in d_instance.space_boundaries:
                if sb not in instance.space_boundaries:
                    instance.space_boundaries.append(sb)

        for tz in d_instance.thermal_zones:
            if tz not in instance.thermal_zones:
                instance.thermal_zones.append(tz)
            if instance not in tz.bound_elements:
                tz.bound_elements.append(instance)
            d_instance_index = tz.bound_elements.index(d_instance)
            del tz.bound_elements[d_instance_index]

        for attr, (value, available) in instance.attributes.items():
            if not value and hasattr(d_instance, attr):
                if getattr(d_instance, attr):
                    setattr(instance, attr, getattr(d_instance, attr))
        if hasattr(instance, 'layerset') and hasattr(d_instance, 'layerset'):
            if instance.layerset and d_instance.layerset:
                instance.layerset = d_instance.layerset
                instance.layerset.parents.append(instance)
