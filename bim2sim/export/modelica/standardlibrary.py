"""Modul containing model representations from the Modelica Standard Library"""
import bim2sim.elements.aggregation.hvac_aggregations
from bim2sim.export import modelica
from bim2sim.elements import hvac_elements as hvac
from bim2sim.elements.mapping.units import ureg


class StandardLibrary(modelica.Instance):
    """Base class for Modelica Standard Library"""
    library = "Modelica Standard Library"


class StaticPipe(StandardLibrary):
    path = "Modelica.Fluid.Pipes.StaticPipe"
    represents = [hvac.Pipe, hvac.PipeFitting,
                  bim2sim.elements.aggregation.hvac_aggregations.PipeStrand]

    def __init__(self, element):
        super().__init__(element)

    def define_parameters(self):
        self.export_parameters["redeclare package Medium"] \
            = 'Modelica.Media.Water.ConstantPropertyLiquidWater'
        self.parameter(name='length',
                       unit=ureg.meter,
                       required=True,
                       attributes=['length'])
        self.parameter(name='diameter',
                       unit=ureg.meter,
                       required=True,
                       attributes=['diameter'])

    def get_port_name(self, port):
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
        super().__init__(element)

    def define_parameters(self):
        self.export_parameters["redeclare package Medium"] \
            = 'Modelica.Media.Water.ConstantPropertyLiquidWater'
        self.parameter(name='dp_nominal',
                       unit=ureg.bar,
                       required=True,
                       attributes=['nominal_pressure_difference'])
        self.parameter(name='m_flow_nominal',
                       unit=ureg.kg/ureg.s,
                       required=True,
                       attributes=['nominal_mass_flow_rate'])

    def get_port_name(self, port):
        if port.verbose_flow_direction == 'SINK':
            return 'port_a'
        if port.verbose_flow_direction == 'SOURCE':
            return 'port_b'
        else:
            return super().get_port_name(port)


class ClosedVolume(StandardLibrary):
    path = "Modelica.Fluid.Vessels.ClosedVolume"
    represents = [hvac.Storage]

    def __init__(self, element):
        super().__init__(element)

    def define_parameters(self):
        self.export_parameters["redeclare package Medium"] \
            = 'Modelica.Media.Water.ConstantPropertyLiquidWater'
        self.parameter(name='V',
                       unit=ureg.meter ** 3,
                       required=True,
                       attributes=['volume'])

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
        super().__init__(element)

    def define_parameters(self):
        self.export_parameters["redeclare package Medium"] \
            = 'Modelica.Media.Water.ConstantPropertyLiquidWater'
        self.parameter(name='V',
                       unit=ureg.meter ** 3,
                       required=True,
                       attributes=['volume'])

    def get_port_name(self, port):
        try:
            index = self.element.ports.index(port)
        except ValueError:
            return super().get_port_name(port)
        else:
            return "port_%d" % (index + 1)
            # TODO: name ports by flow direction?
