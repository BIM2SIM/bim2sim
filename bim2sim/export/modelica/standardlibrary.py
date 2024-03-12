"""Modul containing model representations from the Modelica Standard Library"""
import bim2sim.elements.aggregation.hvac_aggregations
from bim2sim.export import modelica
from bim2sim.elements import hvac_elements as hvac
from bim2sim.elements import aggregation
from bim2sim.elements.mapping.units import ureg


class StandardLibrary(modelica.Instance):
    """Base class for Modelica Standard Library"""
    library = "Modelica Standard Library"


class StaticPipe(StandardLibrary):
    path = "Modelica.Fluid.Pipes.StaticPipe"
    represents = [hvac.Pipe, hvac.PipeFitting,
                  bim2sim.elements.aggregation.hvac_aggregations.PipeStrand]

    def __init__(self, element):
        self.check_length = self.check_numeric(min_value=0 * ureg.meter)
        self.check_diameter = self.check_numeric(min_value=0 * ureg.meter)
        super().__init__(element)

    def request_params(self):
        self.request_param("length", self.check_length)
        # self.request_param("diameter", self.check_diameter, export=False)
        self.request_param('diameter', self.check_diameter)

    def get_port_name(self, port):
        # try:
        #     index = self.element.ports.index(port)
        # except ValueError:
        #     # unknown port
        #     index = -1
        # if index == 0:
        #     return "port_a"
        # elif index == 1:
        #     return "port_b"
        if port.verbose_flow_direction == 'SINK':
            return 'port_a'
        if port.verbose_flow_direction == 'SOURCE':
            return 'port_b'
        else:
            return super().get_port_name(port)


class Valve(StandardLibrary):
    path = "Modelica.Fluid.Valves.ValveIncompressible"
    represents = [hvac.Valve]

    def __init__(self, element):
        self.check_length = self.check_numeric(min_value=0 * ureg.meter)
        self.check_diameter = self.check_numeric(min_value=0 * ureg.meter)
        super().__init__(element)

    def request_params(self):
        self.request_param("length", self.check_length)
        self.request_param("diameter", self.check_diameter)

    def get_port_name(self, port):
        try:
            index = self.element.ports.index(port)
        except ValueError:
            # unknown port
            index = -1
        if index == 0:
            return "port_a"
        elif index == 1:
            return "port_b"
        else:
            return super().get_port_name(port)


class ClosedVolume(StandardLibrary):
    path = "Modelica.Fluid.Vessels.ClosedVolume"
    represents = [hvac.Storage]

    def __init__(self, element):
        self.check_volume = self.check_numeric(min_value=0 * ureg.meter ** 3)
        super().__init__(element)

    def volume(self):
        self.request_param("volume", self.check_volume)

    def get_port_name(self, port):
        try:
            index = self.element.ports.index(port)
        except ValueError:
            return super().get_port_name(port)
        else:
            return "ports[%d]" % index


class TeeJunctionVolume(StandardLibrary):
    path = "Modelica.Fluid.Fittings.TeeJunctionVolume"
    represents = [hvac.Junction]

    def __init__(self, element):
        self.check_volume = self.check_numeric(min_value=0 * ureg.meter ** 3)
        super().__init__(element)

    def volume(self):
        self.request_param("volume", self.check_volume)

    def get_port_name(self, port):
        try:
            index = self.element.ports.index(port)
        except ValueError:
            return super().get_port_name(port)
        else:
            return "port_%d" % (index + 1)  # TODO: name ports by flow direction?

