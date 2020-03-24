"""Module for disaggregation"""

from bim2sim.kernel.element import BaseElement
from bim2sim.kernel import elements, attribute


class Disaggregation(BaseElement):
    """Base disaggregation of models"""

    def __init__(self, name, element, *args, **kwargs):
        if 'guid' not in kwargs:
            kwargs['guid'] = self.get_id("Disagg")
        super().__init__(*args, **kwargs)
        self.name = name
        self.parent = element
        self.ifc_type = element.ifc_type
        self.guid = None

    def calc_position(self):
        try:
            return self.thermal_zones[0].position
        except:
            return None

    def calc_orientation(self):
        try:
            return self.parent.orientation
        except:
            return None

    # @classmethod
    # def get_empty_mapping(cls, elements: list):
    #     """Get information to remove elements
    #     :returns tuple of
    #         mapping dict with original ports as values and None as keys
    #         connection list of outer connections"""
    #     ports = [port for element in elements for port in element.ports]
    #     mapping = {port: None for port in ports}
    #     # TODO: len > 1, optimize
    #     external_ports = []
    #     for port in ports:
    #         if port.connection and port.connection.parent not in elements:
    #             external_ports.append(port.connection)
    #
    #     mapping[external_ports[0].connection] = external_ports[1]
    #     mapping[external_ports[1].connection] = external_ports[0]
    #     connections = []  # (external_ports[0], external_ports[1])
    #
    #     return mapping, connections

    def __repr__(self):
        return "<%s '%s' (disaggregation of the element %d)>" % (
            self.__class__.__name__, self.name, len(self.parent))


class SubSlab(Disaggregation):
    disaggregatable_elements = ['IfcSlab']

    @attribute.multi_calc
    def _calc_avg(self):
        result = dict(
            area=self.parent.area,
            thickness=self.parent.thickness,
            thermal_transmittance=self.parent.thermal_transmittance,
            is_external=self.parent.is_external
        )
        return result

    area = attribute.Attribute(
        name='area',
        functions=[_calc_avg]
    )

    thickness = attribute.Attribute(
        name='thickness',
        functions=[_calc_avg]
    )

    thermal_transmittance = attribute.Attribute(
        name='thermal_transmittance',
        functions=[_calc_avg]
    )

    is_external = attribute.Attribute(
        name='is_external',
        functions=[_calc_avg]
    )

    @classmethod
    def create_on_match(cls, name, slab, thermalzone):
        instance = cls(name, slab)
        if instance.area > thermalzone.area:
            instance.area = float(thermalzone.area)
        if not hasattr(slab, "sub_slabs"):
            slab.sub_slabs = []
        slab.sub_slabs.append(instance)

        return instance


class SubRoof(Disaggregation):
    disaggregatable_elements = ['IfcRoof']
