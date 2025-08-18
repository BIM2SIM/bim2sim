"""Modul containing model representations from the Modelica Standard Library"""
from dataclasses import dataclass
from typing import Union

import bim2sim.elements.aggregation.hvac_aggregations
from bim2sim.export import modelica
from bim2sim.elements import hvac_elements as hvac
from bim2sim.elements.mapping.units import ureg
from bim2sim.export.modelica import ModelicaParameter, check_numeric

MEDIUM_WATER = 'Modelica.Media.Water.ConstantPropertyLiquidWater'


@dataclass(frozen=True)
class Parameter:
    ifc_attribute_name: str
    modelica_name: str


class StandardLibrary(modelica.ModelicaElement):
    """Base class for Modelica Standard Library"""
    library = "Modelica Standard Library"


class StaticPipe(StandardLibrary):
    path = "Modelica.Fluid.Pipes.StaticPipe"
    represents = [hvac.Pipe, hvac.PipeFitting,
                  bim2sim.elements.aggregation.hvac_aggregations.PipeStrand]

    ID_PARAMETER_LENGTH = 'length'

    mappser ={
        ID_PARAMETER_LENGTH: 'length'
    }

    def __init__(self, element: Union[hvac.Pipe]):
        super().__init__(element)
        self._set_parameter(name='redeclare package Medium',
                            unit=None,
                            required=False,
                            value=MEDIUM_WATER)
        self._set_parameter(name='length',
                            unit=ureg.meter,
                            required=True,
                            check=check_numeric(min_value=0 * ureg.meter),
                            attributes=['length'])
        self._set_parameter(name='diameter',
                            unit=ureg.meter,
                            required=True,
                            check=check_numeric(min_value=0 * ureg.meter),
                            attributes=['diameter'])

    def get_port_name(self, port):
        if port.flow_direction.name == 'sink':
            return 'port_a'
        if port.flow_direction.name == 'source':
            return 'port_b'
        # TODO #733 find port if sourceandsink or sinkdansource
        # if port.flow_direction == 0.  # SOURCEANDSINK and SINKANDSOURCE
        else:
            return super().get_port_name(port)


class Valve(StandardLibrary):
    path = "Modelica.Fluid.Valves.ValveIncompressible"
    represents = [hvac.Valve]

    def __init__(self, element):
        super().__init__(element)
        self._set_parameter(name='redeclare package Medium',
                            unit=None,
                            required=False,
                            value=MEDIUM_WATER)
        self._set_parameter(name='dp_nominal',
                            unit=ureg.bar,
                            required=True,
                            check=check_numeric(min_value=0 * ureg.bar),
                            attributes=['nominal_pressure_difference'],)
        self._set_parameter(name='m_flow_nominal',
                            unit=ureg.kg / ureg.s,
                            required=True,
                            check=check_numeric(min_value=0 * ureg.kg / ureg.s),
                            attributes=['nominal_mass_flow_rate'])

    def get_port_name(self, port):
        if port.flow_direction.name == 'sink':
            return 'port_a'
        if port.flow_direction.name == 'source':
            return 'port_b'
        else:
            return super().get_port_name(port)


class ClosedVolume(StandardLibrary):
    path = "Modelica.Fluid.Vessels.ClosedVolume"
    represents = [hvac.Storage]

    def __init__(self, element):
        super().__init__(element)
        self._set_parameter(name='redeclare package Medium',
                            unit=None,
                            required=False,
                            value=MEDIUM_WATER)
        self._set_parameter(name='V',
                            unit=ureg.meter ** 3,
                            required=True,
                            check=check_numeric(min_value=0 * ureg.meter ** 3),
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
        self._set_parameter(name='redeclare package Medium',
                            unit=None,
                            required=False,
                            value=MEDIUM_WATER)
        self._set_parameter(name='V',
                            unit=ureg.meter ** 3,
                            required=True,
                            check=check_numeric(min_value=0 * ureg.meter ** 3),
                            attributes=['volume'])

    def get_port_name(self, port):
        try:
            index = self.element.ports.index(port)
        except ValueError:
            return super().get_port_name(port)
        else:
            return "port_%d" % (index + 1)
            # TODO: name ports by flow direction?
