"""Module contains the different classes for all HVAC elements"""
import inspect
import itertools
import logging
import math
import re
import sys
from typing import Set, List, Tuple, Generator, Union, Type

import numpy as np
import ifcopenshell.geom

from bim2sim.kernel.decision import ListDecision, DecisionBunch
from bim2sim.elements.mapping import condition, attribute
from bim2sim.elements.base_elements import Port, ProductBased, IFCBased
from bim2sim.elements.mapping.ifc2python import get_ports as ifc2py_get_ports
from bim2sim.elements.mapping.ifc2python import get_predefined_type
from bim2sim.elements.mapping.units import ureg
from bim2sim.utilities.types import FlowDirection, FlowSide


logger = logging.getLogger(__name__)
quality_logger = logging.getLogger('bim2sim.QualityReport')


def diameter_post_processing(value):
    if isinstance(value, (list, set)):
        return sum(value) / len(value)
    return value


def length_post_processing(value):
    if isinstance(value, (list, set)):
        return max(value)
    return value


class HVACPort(Port):
    """Port of HVACProduct.

    Definitions:
    flow_direction: is the direction of the port which can be sink, source,
     sink_and_source or unknown depending on the IFC data.
    groups: based on IFC assignment this might be "vorlauf" or something else.
    flow_side: defines if the port is part of the supply or return network.
    E.g. the radiator is a splitter where one port is part of the supply and
    the other port is part of the return network

    """
    vl_pattern = re.compile('.*(vorlauf|supply|feed|forward).*', re.IGNORECASE)
    rl_pattern = re.compile('.*(rücklauf|return|recirculation|back).*',
                            re.IGNORECASE)

    # TODO #733 Clean port flow side setup
    def __init__(
            self, *args, groups: Set = None,
            flow_direction: FlowDirection = FlowDirection.unknown, **kwargs):
        super().__init__(*args, **kwargs)

        self._flow_master = False
        # self._flow_direction = None

        self._flow_side = None
        # groups and flow_direction coming from ifc2args kwargs
        self.groups = groups or set()
        self.flow_direction = flow_direction

    @classmethod
    def ifc2args(cls, ifc) -> Tuple[tuple, dict]:
        args, kwargs = super().ifc2args(ifc)
        groups = {assg.RelatingGroup.ObjectType
                  for assg in ifc.HasAssignments}
        if ifc.FlowDirection == 'SOURCE':
            flow_direction = FlowDirection.source
        elif ifc.FlowDirection == 'SINK':
            flow_direction = FlowDirection.sink
        elif ifc.FlowDirection in ['SINKANDSOURCE', 'SOURCEANDSINK']:
            flow_direction = FlowDirection.sink_and_source
        elif ifc.FlowDirection == 'NOTDEFINED':
            flow_direction = FlowDirection.unknown
        else:
            flow_direction = FlowDirection.unknown

        kwargs['groups'] = groups
        kwargs['flow_direction'] = flow_direction
        return args, kwargs

    def _calc_position(self, name) -> np.array:
        """returns absolute position as np.array"""
        try:
            relative_placement = \
                self.parent.ifc.ObjectPlacement.RelativePlacement
            x_direction = np.array(
                relative_placement.RefDirection.DirectionRatios)
            z_direction = np.array(relative_placement.Axis.DirectionRatios)
        except AttributeError:
            x_direction = np.array([1, 0, 0])
            z_direction = np.array([0, 0, 1])
        y_direction = np.cross(z_direction, x_direction)
        directions = np.array((x_direction, y_direction, z_direction)).T
        port_coordinates_relative = \
            np.array(
                self.ifc.ObjectPlacement.RelativePlacement.Location.Coordinates)
        coordinates = self.parent.position + np.matmul(directions,
                                                       port_coordinates_relative)

        if all(coordinates == np.array([0, 0, 0])):
            quality_logger.info("Suspect position [0, 0, 0] for %s", self)
        return coordinates

    def validate_creation(self) -> bool:
        return True

    @property
    def flow_master(self):
        """Lock flow direction for port"""
        return self._flow_master

    @flow_master.setter
    def flow_master(self, value: bool):
        self._flow_master = value

    # @property
    # def flow_direction(self):
    #     """Flow direction of port
    #
    #     -1 = medium flows into port
    #     1 = medium flows out of port
    #     0 = medium flow undirected
    #     None = flow direction unknown"""
    #     return self._flow_direction

    # @flow_direction.setter
    # def flow_direction(self, value):
    #     if self._flow_master:
    #         raise AttributeError("Can't set flow direction for flow master.")
    #     if value not in (-1, 0, 1, None):
    #         raise AttributeError("Invalid value. Use one of (-1, 0, 1, None).")
    #     self._flow_direction = value

    # @property
    # def verbose_flow_direction(self):
    #     """Flow direction of port"""
    #     if self.flow_direction == -1:
    #         return 'SINK'
    #     if self.flow_direction == 0:
    #         return 'SINKANDSOURCE'
    #     if self.flow_direction == 1:
    #         return 'SOURCE'
    #     return 'UNKNOWN'

    @property
    def flow_side(self):
        """
        Flow side of port.

        1 = supply flow (Vorlauf)
        -1 = return flow (Rücklauf)
        0 = unknown
        """
        if self._flow_side is None:
            self._flow_side = self.determine_flow_side()
        return self._flow_side

    @flow_side.setter
    def flow_side(self, value):
        previous = self._flow_side
        self._flow_side = value
        if previous:
            if previous != value:
                logger.info(
                    f"Overwriting flow_side for {self} with {value.name}")
        else:
            logger.debug(f"Set flow_side for {self} to {value.name}")

    def determine_flow_side(self):
        """Check groups for hints of flow_side and returns flow_side if hints
        are definitely.

        First the flow_direction and the type of the element
        (generator/consumer) is checked for clear information. If no
        information can be obtained the pattern matches are evaluated based on
        the groups from IFC, that come from RelatingGroup assignment.
        If there are mismatching information from flow_direction and patterns
        the flow_side is set to unknown, otherwise it's set to supply_flow or
        supply_flow.
        """
        vl = None
        rl = None

        if self.parent.is_generator():
            if self.flow_direction.name == "source":
                vl = True
            elif self.flow_direction.name == "sink":
                rl = True
        elif self.parent.is_consumer():
            if self.flow_direction.name == "source":
                rl = True
            elif self.flow_direction.name == "sink":
                vl = True
        if not vl:
            vl = any(filter(self.vl_pattern.match, self.groups))
        if not rl:
            rl = any(filter(self.rl_pattern.match, self.groups))

        if vl and not rl:
            return FlowSide.supply_flow
        if rl and not vl:
            return FlowSide.return_flow
        return FlowSide.unknown


class HVACProduct(ProductBased):
    domain = 'HVAC'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.inner_connections: List[Tuple[HVACPort, HVACPort]] \
            = self.get_inner_connections()

    @property
    def expected_hvac_ports(self):
        raise NotImplementedError(f"Please define the expected number of ports "
                                  f"for the class {self.__class__.__name__} ")

    def get_ports(self) -> list:
        """Returns a list of ports of this product."""
        ports = ifc2py_get_ports(self.ifc)
        hvac_ports = []
        for port in ports:
            port_valid = True
            if port.is_a() != 'IfcDistributionPort':
                port_valid = False
            else:
                predefined_type = get_predefined_type(port)
                if predefined_type in [
                    'CABLE', 'CABLECARRIER', 'WIRELESS']:
                    port_valid = False
            if port_valid:
                hvac_ports.append(HVACPort.from_ifc(
                    ifc=port, parent=self))
            else:
                logger.warning(
                    "Not included %s as Port in %s with GUID %s",
                    port.is_a(),
                    self.__class__.__name__,
                    self.guid)
        return hvac_ports

    def get_inner_connections(self) -> List[Tuple[HVACPort, HVACPort]]:
        """Returns inner connections of Element.

        By default each port is connected to each other port.
        Overwrite for other connections."""

        connections = []
        for port0, port1 in itertools.combinations(self.ports, 2):
            connections.append((port0, port1))
        return connections

    def decide_inner_connections(self) -> Generator[DecisionBunch, None, None]:
        """Generator method yielding decisions to set inner connections."""

        if len(self.ports) < 2:
            # not possible to connect anything
            return

        # TODO: extend pattern
        vl_pattern = re.compile('.*vorlauf.*', re.IGNORECASE)
        rl_pattern = re.compile('.*rücklauf.*', re.IGNORECASE)

        # use score for ports to help user find best match_graph
        score_vl = {}
        score_rl = {}
        for port in self.ports:
            bonus_vl = 0
            bonus_rl = 0
            # connected to pipe
            if port.connection and type(port.connection.parent) \
                    in [Pipe, PipeFitting]:
                bonus_vl += 1
                bonus_rl += 1
            # string hints
            if any(filter(vl_pattern.match, port.groups)):
                bonus_vl += 1
            if any(filter(rl_pattern.match, port.groups)):
                bonus_rl += 1
            # flow direction
            if port.flow_direction == 1:
                bonus_vl += .5
            if port.flow_direction == -1:
                bonus_rl += .5
            score_vl[port] = bonus_vl
            score_rl[port] = bonus_rl

        # created sorted choices
        choices_vl = [port.guid for port, score in
                      sorted(score_vl.items(), key=lambda item: item[1],
                             reverse=True)]
        choices_rl = [port.guid for port, score in
                      sorted(score_rl.items(), key=lambda item: item[1],
                             reverse=True)]
        decision_vl = ListDecision(f"Please select VL Port for {self}.",
                                   choices=choices_vl,
                                   default=choices_vl[0],  # best guess
                                   key='VL',
                                   global_key='VL_port_of_' + self.guid)
        decision_rl = ListDecision(f"Please select RL Port for {self}.",
                                   choices=choices_rl,
                                   default=choices_rl[0],  # best guess
                                   key='RL',
                                   global_key='RL_port_of_' + self.guid)
        decisions = DecisionBunch((decision_vl, decision_rl))
        yield decisions

        port_dict = {port.guid: port for port in self.ports}
        vl = port_dict[decision_vl.value]
        rl = port_dict[decision_rl.value]
        # set flow correct side
        vl.flow_side = FlowSide.supply_flow
        rl.flow_side = FlowSide.return_flow
        self.inner_connections.append((vl, rl))

    def validate_ports(self):
        if isinstance(self.expected_hvac_ports, tuple):
            if self.expected_hvac_ports[0] <= len(self.ports) \
                    <= self.expected_hvac_ports[-1]:
                return True
        else:
            if len(self.ports) == self.expected_hvac_ports:
                return True
        return False

    def is_generator(self):
        return False

    def is_consumer(self):
        return False

    def calc_cost_group(self) -> [int]:
        """Default cost group for HVAC elements is 400"""
        return 400

    def __repr__(self):
        return "<%s (guid: %s, ports: %d)>" % (
            self.__class__.__name__, self.guid, len(self.ports))


class HeatPump(HVACProduct):
    """"HeatPump"""

    ifc_types = {
        'IfcUnitaryEquipment': ['*']
    }
    # IFC Schema does not support Heatpumps directly, but default of unitary
    # equipment is set to HeatPump now and expected ports to 4 to try to
    # identify heat pumps

    pattern_ifc_type = [
        re.compile('Heat.?pump', flags=re.IGNORECASE),
        re.compile('W(ä|ae)rme.?pumpe', flags=re.IGNORECASE),
    ]

    def is_generator(self):
        return True

    min_power = attribute.Attribute(
        description='Minimum power that heat pump operates at.',
        unit=ureg.kilowatt,
    )
    rated_power = attribute.Attribute(
        description='Rated power of heat pump.',
        unit=ureg.kilowatt,
    )
    efficiency = attribute.Attribute(
        description='Efficiency of heat pump provided as list with pairs of '
                    '[percentage_of_rated_power,efficiency]',
        unit=ureg.dimensionless
    )
    vdi_performance_data_table=attribute.Attribute(
        description="temp dummy to test vdi table export",
    )
    is_reversible = attribute.Attribute(
        description="Does the heat pump support cooling as well?",
        unit=ureg.dimensionless
    )
    rated_cooling_power = attribute.Attribute(
        description='Rated power of heat pump in cooling mode.',
        unit=ureg.kilowatt,
    )
    COP = attribute.Attribute(
        description="The COP of the heat pump, definition based on VDI 3805-22",
        unit=ureg.dimensionless
    )
    internal_pump = attribute.Attribute(
        description="The COP of the heat pump, definition based on VDI 3805-22",
    )

    @property
    def expected_hvac_ports(self):
        return 4


class Chiller(HVACProduct):
    """"Chiller"""

    ifc_types = {
        'IfcChiller': ['*', 'AIRCOOLED', 'WATERCOOLED', 'HEATRECOVERY']}

    pattern_ifc_type = [
        re.compile('Chiller', flags=re.IGNORECASE),
        re.compile('K(ä|ae)lte.?maschine', flags=re.IGNORECASE),
    ]

    rated_power = attribute.Attribute(
        description='Rated power of Chiller.',
        default_ps=('Pset_ChillerTypeCommon', 'NominalCapacity'),
        unit=ureg.kilowatt,
    )

    nominal_power_consumption = attribute.Attribute(
        description="nominal power consumption of chiller",
        default_ps=('Pset_ChillerTypeCommon', 'NominalPowerConsumption'),
        unit=ureg.kilowatt,
    )

    nominal_COP = attribute.Attribute(
        description="Chiller efficiency at nominal load",
        default_ps=('Pset_ChillerTypeCommon', 'NominalEfficiency'),
    )

    capacity_curve = attribute.Attribute(
        # (Capacity[W], CondensingTemperature[K], EvaporatingTemperature[K])
        description="Chiller's thermal power as function of fluid temperature",
        default_ps=('Pset_ChillerTypeCommon', 'CapacityCurve'),
    )

    COP = attribute.Attribute(
        # (COP, CondensingTemperature[K], EvaporatingTemperature[K])
        description="Chiller's COP as function of fluid temperature",
        default_ps=('Pset_ChillerTypeCommon', 'CoefficientOfPerformanceCurve'),
    )

    full_load_ratio = attribute.Attribute(
        # (FracFullLoadPower, PartLoadRatio)
        description="Chiller's thermal partial load power as function of fluid "
                    "temperature",
        default_ps=('Pset_ChillerTypeCommon', 'FullLoadRatioCurve'),
    )

    nominal_condensing_temperature = attribute.Attribute(
        description='Nominal condenser temperature',
        default_ps=('Pset_ChillerTypeCommon', 'NominalCondensingTemperature'),
        unit=ureg.celsius,
    )

    nominal_evaporating_temperature = attribute.Attribute(
        description='Nominal condenser temperature',
        default_ps=('Pset_ChillerTypeCommon', 'NominalEvaporatingTemperature'),
        unit=ureg.celsius,
    )

    min_power = attribute.Attribute(
        description='Minimum power at which Chiller operates at.',
        unit=ureg.kilowatt,
    )

    @property
    def expected_hvac_ports(self):
        return 4


class CoolingTower(HVACProduct):
    """"CoolingTower"""

    ifc_types = {
        'IfcCoolingTower':
            ['*', 'NATURALDRAFT', 'MECHANICALINDUCEDDRAFT',
             'MECHANICALFORCEDDRAFT']
    }

    pattern_ifc_type = [
        re.compile('Cooling.?Tower', flags=re.IGNORECASE),
        re.compile('Recooling.?Plant', flags=re.IGNORECASE),
        re.compile('K(ü|ue)hl.?turm', flags=re.IGNORECASE),
        re.compile('R(ü|ue)ck.?K(ü|ue)hl.?(werk|turm|er)', flags=re.IGNORECASE),
        re.compile('RKA', flags=re.IGNORECASE),
    ]

    def is_consumer(self):
        # TODO #733 check this
        return True

    min_power = attribute.Attribute(
        description='Minimum power that CoolingTower operates at.',
        unit=ureg.kilowatt,
    )
    rated_power = attribute.Attribute(
        description='Rated power of CoolingTower.',
        default_ps=('Pset_CoolingTowerTypeCommon', 'NominalCapacity'),
        unit=ureg.kilowatt,
    )
    efficiency = attribute.Attribute(
        description='Efficiency of CoolingTower provided as list with pairs of '
                    '[percentage_of_rated_power,efficiency]',
        unit=ureg.dimensionless,
    )

    @property
    def expected_hvac_ports(self):
        return 2


class HeatExchanger(HVACProduct):
    """"Heat exchanger"""

    ifc_types = {'IfcHeatExchanger': ['*', 'PLATE', 'SHELLANDTUBE']}

    pattern_ifc_type = [
        re.compile('Heat.?Exchanger', flags=re.IGNORECASE),
        re.compile('W(ä|ae)rme.?(ü|e)bertrager', flags=re.IGNORECASE),
        re.compile('W(ä|ae)rme.?tauscher', flags=re.IGNORECASE),
    ]

    min_power = attribute.Attribute(
        description='Minimum power that HeatExchange operates at.',
        unit=ureg.kilowatt,
    )
    rated_power = attribute.Attribute(
        description='Rated power of HeatExchange.',
        unit=ureg.kilowatt,
    )
    efficiency = attribute.Attribute(
        description='Efficiency of HeatExchange provided as list with pairs of '
                    '[percentage_of_rated_power,efficiency]',
        unit=ureg.dimensionless,
    )

    @property
    def expected_hvac_ports(self):
        return 4


class Boiler(HVACProduct):
    """Boiler"""
    ifc_types = {'IfcBoiler': ['*', 'WATER', 'STEAM']}

    pattern_ifc_type = [
        # re.compile('Heat.?pump', flags=re.IGNORECASE),
        re.compile('Kessel', flags=re.IGNORECASE),
        re.compile('Boiler', flags=re.IGNORECASE),
    ]

    @property
    def expected_hvac_ports(self):
        return 2

    def is_generator(self):
        """Boiler is a generator function."""
        return True

    def get_inner_connections(self):
        # TODO see #167
        if len(self.ports) > 2:
            return []
        else:
            connections = super().get_inner_connections()
            return connections

    water_volume = attribute.Attribute(
        description="Water volume of boiler",
        default_ps=('Pset_BoilerTypeCommon', 'WaterStorageCapacity'),
        unit=ureg.meter ** 3,
    )

    dry_mass = attribute.Attribute(
        description="Weight of the element, not including contained fluid.",
        default_ps=('Qto_BoilerBaseQuantities', 'GrossWeight'),
        unit=ureg.kg,
    )

    nominal_power_consumption = attribute.Attribute(
        description="nominal energy consumption of boiler",
        default_ps=('Pset_BoilerTypeCommon', 'NominalEnergyConsumption'),
        unit=ureg.kilowatt,
    )

    efficiency = attribute.Attribute(
        # (Efficiency, PartialLoadFactor)
        description="Efficiency of boiler provided as list with pairs of "
                    "percentage_of_rated_power and efficiency",
        default_ps=('Pset_BoilerTypeCommon', 'PartialLoadEfficiencyCurves'),
        unit=ureg.dimensionless,
    )

    energy_source = attribute.Attribute(
        description="Final energy source of boiler",
        default_ps=('Pset_BoilerTypeCommon', 'EnergySource'),
    )

    operating_mode = attribute.Attribute(
        # [fixed, twostep, modulating, other, unknown, unset]
        description="Boiler's operating mode",
        default_ps=('Pset_BoilerTypeCommon', 'OperatingMode'),
        unit=ureg.dimensionless,
    )

    part_load_ratio_range = attribute.Attribute(
        description="Allowable part load ratio range (Bounded value).",
        default_ps=('Pset_BoilerTypeCommon', 'NominalPartLoadRatio'),
    )

    def _get_minimal_part_load_ratio(self, name):
        """Calculates the minimal part load ratio based on the given range."""
        # TODO this is not tested yet but should work with the new BoundedValue
        #  in ifc2python
        if hasattr(self, "part_load_ratio_range"):
            return min(self.part_load_ratio_range)

    def _normalise_value_zero_to_one(self, value):
        if (max(self.part_load_ratio_range) == 100
                and min(self.part_load_ratio_range) == 0):
            return value * 0.01

    minimal_part_load_ratio = attribute.Attribute(
        description="Minimal part load ratio",
        functions=[_get_minimal_part_load_ratio],
        # TODO use ifc_post_processing to make sure that ranged value are between
        #  0 and 1
        ifc_postprocessing=[_normalise_value_zero_to_one]
    )


    def _calc_nominal_efficiency(self, name):
        """function to calculate the boiler nominal efficiency using the
        efficiency curve"""

        if isinstance(self.efficiency, list):
            efficiency_curve = {y: x for x, y in self.efficiency}
            nominal_eff = efficiency_curve.get(1, None)
            if nominal_eff:
                return nominal_eff
            else:
                # ToDo: linear regression
                raise NotImplementedError
        else:
            # WORKAROUND: input of lists is not yet implemented
            return self.efficiency

    nominal_efficiency = attribute.Attribute(
        description="""Boiler efficiency at nominal load""",
        functions=[_calc_nominal_efficiency],
        unit=ureg.dimensionless,
    )

    def _calc_rated_power(self, name) -> ureg.Quantity:
        """Function to calculate the rated power of the boiler using the nominal
        efficiency and the nominal power consumption"""
        return self.nominal_efficiency * self.nominal_power_consumption

    rated_power = attribute.Attribute(
        description="Rated power of boiler",
        unit=ureg.kilowatt,
        functions=[_calc_rated_power],
    )

    def _calc_partial_load_efficiency(self, name):
        """Function to calculate the boiler efficiency at partial load using the
        nominal partial ratio and the efficiency curve"""
        if isinstance(self.efficiency, list):
            efficiency_curve = {y: x for x, y in self.efficiency}
            partial_eff = efficiency_curve.get(max(self.part_load_ratio_range),
                                               None)
            if partial_eff:
                return partial_eff
            else:
                # ToDo: linear regression
                raise NotImplementedError
        else:
            # WORKAROUND: input of lists is not yet implemented
            return self.efficiency

    partial_load_efficiency = attribute.Attribute(
        description="Boiler efficiency at partial load",
        functions=[_calc_partial_load_efficiency],
        unit=ureg.dimensionless,
        default=0.15
    )

    def _calc_min_power(self, name) -> ureg.Quantity:
        """Function to calculate the minimum power that boiler operates at,
        using the partial load efficiency and the nominal power consumption"""
        if self.partial_load_efficiency and self.nominal_power_consumption:
            return self.partial_load_efficiency * self.nominal_power_consumption

    min_power = attribute.Attribute(
        description="Minimum power that boiler operates at",
        unit=ureg.kilowatt,
        functions=[_calc_min_power],
    )

    def _calc_min_PLR(self, name) -> ureg.Quantity:
        """Function to calculate the minimal PLR of the boiler using the minimal
        power and the rated power"""
        return self.min_power / self.rated_power

    min_PLR = attribute.Attribute(
        description="Minimum Part load ratio",
        unit=ureg.dimensionless,
        functions=[_calc_min_PLR],
    )
    return_temperature = attribute.Attribute(
        description="Nominal return temperature",
        default_ps=('Pset_BoilerTypeCommon', 'WaterInletTemperatureRange'),
        unit=ureg.celsius,
    )
    flow_temperature = attribute.Attribute(
        description="Nominal flow temperature",
        default_ps=('Pset_BoilerTypeCommon', 'OutletTemperatureRange'),
        unit=ureg.celsius,
    )

    def _calc_dT_water(self, name) -> ureg.Quantity:
        """Function to calculate the delta temperature of the boiler using the
        return and flow temperature"""
        return self.return_temperature - self.flow_temperature

    dT_water = attribute.Attribute(
        description="Nominal temperature difference",
        unit=ureg.kelvin,
        functions=[_calc_dT_water],
    )


class Pipe(HVACProduct):
    ifc_types = {
        "IfcPipeSegment":
            ['*', 'CULVERT', 'FLEXIBLESEGMENT', 'RIGIDSEGMENT', 'GUTTER',
             'SPOOL']
    }

    @property
    def expected_hvac_ports(self):
        return 2

    conditions = [
        condition.RangeCondition("diameter", 5.0 * ureg.millimeter,
                                 300.00 * ureg.millimeter)  # ToDo: unit?!
    ]

    def _calc_diameter_from_radius(self, name) -> ureg.Quantity:
        if self.radius:
            return self.radius*2
        else:
            return None

    diameter = attribute.Attribute(
        default_ps=('Pset_PipeSegmentTypeCommon', 'NominalDiameter'),
        unit=ureg.millimeter,
        patterns=[
            re.compile('.*Durchmesser.*', flags=re.IGNORECASE),
            re.compile('.*Diameter.*', flags=re.IGNORECASE),
        ],
        functions=[_calc_diameter_from_radius],
        ifc_postprocessing=diameter_post_processing,
    )
    # TODO #432 implement function to get diamter from shape

    radius = attribute.Attribute(
        patterns=[
            re.compile('.*Radius.*', flags=re.IGNORECASE)
        ],
        unit=ureg.millimeter
    )

    outer_diameter = attribute.Attribute(
        description="Outer diameter of pipe",
        default_ps=('Pset_PipeSegmentTypeCommon', 'OuterDiameter'),
        unit=ureg.millimeter,
    )

    inner_diameter = attribute.Attribute(
        description="Inner diameter of pipe",
        default_ps=('Pset_PipeSegmentTypeCommon', 'InnerDiameter'),
        unit=ureg.millimeter,
    )

    def _length_from_geometry(self, name):
        """
        Function to calculate the length of the pipe from the geometry
        """
        try:
            return Pipe.get_lenght_from_shape(self.ifc.Representation) \
                   * ureg.meter
        except AttributeError:
            return None

    length = attribute.Attribute(
        default_ps=('Qto_PipeSegmentBaseQuantities', 'Length'),
        unit=ureg.meter,
        patterns=[
            re.compile('.*Länge.*', flags=re.IGNORECASE),
            re.compile('.*Length.*', flags=re.IGNORECASE),
        ],
        ifc_postprocessing=length_post_processing,
        functions=[_length_from_geometry],
    )

    roughness_coefficient = attribute.Attribute(
        description="Interior roughness coefficient of pipe",
        default_ps=('Pset_PipeSegmentOccurrence',
                    'InteriorRoughnessCoefficient'),
        unit=ureg.millimeter,
    )

    @staticmethod
    def get_lenght_from_shape(ifc_representation):
        """Search for extruded depth in representations

        Warning: Found extrusion may net be the required length!
        :raises: AttributeError if not exactly one extrusion is found"""
        candidates = []
        try:
            for representation in ifc_representation.Representations:
                for item in representation.Items:
                    if item.is_a() == 'IfcExtrudedAreaSolid':
                        candidates.append(item.Depth)
        except:
            raise AttributeError("Failed to determine length.")
        if not candidates:
            raise AttributeError("No representation to determine length.")
        if len(candidates) > 1:
            raise AttributeError(
                "Too many representations to dertermine length %s." % candidates)

        return candidates[0]


class PipeFitting(HVACProduct):
    ifc_types = {
        "IfcPipeFitting":
            ['*', 'BEND', 'CONNECTOR', 'ENTRY', 'EXIT', 'JUNCTION',
             'OBSTRUCTION', 'TRANSITION']
    }
    pattern_ifc_type = [
        re.compile('Bogen', flags=re.IGNORECASE),
        re.compile('Bend', flags=re.IGNORECASE),
    ]

    @property
    def expected_hvac_ports(self):
        return (2, 3)

    conditions = [
        condition.RangeCondition("diameter", 5.0 * ureg.millimeter,
                                 300.00 * ureg.millimeter)
    ]

    diameter = attribute.Attribute(
        default_ps=('Pset_PipeFittingTypeCommon', 'NominalDiameter'),
        unit=ureg.millimeter,
        patterns=[
            re.compile('.*Durchmesser.*', flags=re.IGNORECASE),
            re.compile('.*Diameter.*', flags=re.IGNORECASE),
        ],
        ifc_postprocessing=diameter_post_processing,
    )
    # TODO #432 implement function to get diamter from shape

    length = attribute.Attribute(
        default_ps=("Qto_PipeFittingBaseQuantities", "Length"),
        unit=ureg.meter,
        patterns=[
            re.compile('.*Länge.*', flags=re.IGNORECASE),
            re.compile('.*Length.*', flags=re.IGNORECASE),
        ],
        default=0,
        ifc_postprocessing=length_post_processing
    )

    pressure_class = attribute.Attribute(
        unit=ureg.pascal,
        default_ps=('Pset_PipeFittingTypeCommon', 'PressureClass')
    )

    pressure_loss_coefficient = attribute.Attribute(
        description="Pressure loss coefficient of pipe fitting",
        default_ps=('Pset_PipeFittingTypeCommon', 'FittingLossFactor'),
        unit=ureg.pascal,
    )

    roughness_coefficient = attribute.Attribute(
        description="Roughness coefficient of pipe fitting",
        default_ps=('Pset_PipeFittingOccurrence',
                    'InteriorRoughnessCoefficient'),
        unit=ureg.millimeter,
    )

    @staticmethod
    def _diameter_post_processing(value):
        if isinstance(value, list):
            return np.average(value).item()
        return value

    def get_better_subclass(self) -> Union[None, Type['IFCBased']]:
        if len(self.ports) == 3:
            return Junction


class Junction(PipeFitting):
    ifc_types = {
        "IfcPipeFitting": ['JUNCTION']
    }

    pattern_ifc_type = [
        re.compile('T-St(ü|ue)ck', flags=re.IGNORECASE),
        re.compile('T-Piece', flags=re.IGNORECASE),
        re.compile('Kreuzst(ü|ue)ck', flags=re.IGNORECASE)
    ]

    @property
    def expected_hvac_ports(self):
        return 3

    volume = attribute.Attribute(
        description="Volume of the junction",
        unit=ureg.meter ** 3
    )


class SpaceHeater(HVACProduct):
    ifc_types = {'IfcSpaceHeater': ['*', 'CONVECTOR', 'RADIATOR']}

    pattern_ifc_type = [
        re.compile('Heizk(ö|oe)rper', flags=re.IGNORECASE),
        re.compile('Space.?heater', flags=re.IGNORECASE)
    ]

    @property
    def expected_hvac_ports(self):
        return 2

    def is_consumer(self):
        return True

    def _get_radiator_shape(self, name):
        """returns topods shape of the radiator"""
        settings = ifcopenshell.geom.main.settings()
        settings.set(settings.USE_PYTHON_OPENCASCADE, True)
        settings.set(settings.USE_WORLD_COORDS, True)
        settings.set(settings.EXCLUDE_SOLIDS_AND_SURFACES, False)
        settings.set(settings.INCLUDE_CURVES, True)
        return ifcopenshell.geom.create_shape(settings, self.ifc).geometry

    shape = attribute.Attribute(
        description="Returns topods shape of the radiator.",
        functions=[_get_radiator_shape]
    )

    number_of_panels = attribute.Attribute(
        description="Number of panels of heater",
        default_ps=('Pset_SpaceHeaterTypeCommon', 'NumberOfPanels'),
    )

    number_of_sections = attribute.Attribute(
        description="Number of sections of heater",
        default_ps=('Pset_SpaceHeaterTypeCommon', 'NumberOfSections'),
    )

    thermal_efficiency = attribute.Attribute(
        description="Thermal efficiency of heater",
        default_ps=('Pset_SpaceHeaterTypeCommon', 'ThermalEfficiency'),
        unit=ureg.dimensionless,
    )

    body_mass = attribute.Attribute(
        description="Body mass of heater",
        default_ps=('Pset_SpaceHeaterTypeCommon', 'BodyMass'),
        unit=ureg.kg,
    )

    length = attribute.Attribute(
        description="Lenght of heater",
        default_ps=('Qto_SpaceHeaterBaseQuantities', 'Length'),
        unit=ureg.meter,
    )

    height = attribute.Attribute(
        description="Height of heater",
        unit=ureg.meter
    )

    temperature_classification = attribute.Attribute(
        # [HighTemperature, LowTemperature, Other, NotKnown, Unset]
        description="Temperature classification of heater",
        default_ps=('Pset_SpaceHeaterTypeCommon', 'TemperatureClassification'),
    )

    rated_power = attribute.Attribute(
        description="Rated power of SpaceHeater",
        default_ps=('Pset_SpaceHeaterTypeCommon', 'OutputCapacity'),
        unit=ureg.kilowatt,
    )

    flow_temperature = attribute.Attribute(
        description="Flow temperature",
        unit=ureg.celsius,
    )

    return_temperature = attribute.Attribute(
        description="Return temperature",
        unit=ureg.celsius,
    )

    medium = attribute.Attribute(
        # [Steam, Water, Other, NotKnown, Unset]
        description="Medium of SpaceHeater",
        default_ps=('Pset_SpaceHeaterTypeCommon', 'HeatTransferMedium'),
    )

    heat_capacity = attribute.Attribute(
        description="Heat capacity of heater",
        default_ps=('Pset_SpaceHeaterTypeCommon', 'ThermalMassHeatCapacity'),
        unit=ureg.joule / ureg.kelvin,
    )

    def _calc_dT_water(self, name) -> ureg.Quantity:
        """Function to calculate the delta temperature of the boiler using the
        return and flow temperature"""
        return self.flow_temperature - self.return_temperature

    dT_water = attribute.Attribute(
        description="Nominal temperature difference",
        unit=ureg.kelvin,
        functions=[_calc_dT_water],
    )


class ExpansionTank(HVACProduct):
    ifc_types = {
        "IfcTank":
            ['BREAKPRESSURE', 'EXPANSION', 'FEEDANDEXPANSION']
    }
    pattern_ifc_type = [
        re.compile('Expansion.?Tank', flags=re.IGNORECASE),
        re.compile('Ausdehnungs.?gef(ä|ae)(ss|ß)', flags=re.IGNORECASE),
    ]

    @property
    def expected_hvac_ports(self):
        return 1


class Storage(HVACProduct):
    ifc_types = {
        "IfcTank":
            ['*', 'BASIN', 'STORAGE', 'VESSEL']
    }
    pattern_ifc_type = [
        re.compile('Speicher', flags=re.IGNORECASE),
        re.compile('Puffer.?speicher', flags=re.IGNORECASE),
        re.compile('Trinkwarmwasser.?speicher', flags=re.IGNORECASE),
        re.compile('Trinkwarmwasser.?speicher', flags=re.IGNORECASE),
        re.compile('storage', flags=re.IGNORECASE),
    ]

    conditions = [
        condition.RangeCondition('volume', 50 * ureg.liter,
                                 math.inf * ureg.liter)
    ]

    @property
    def expected_hvac_ports(self):
        return float('inf')

    def _calc_volume(self, name) -> ureg.Quantity:
        """
        Calculate volume of storage.
        """
        return self.height * self.diameter ** 2 / 4 * math.pi

    storage_type = attribute.Attribute(
        # [Ice, Water, RainWater, WasteWater, PotableWater, Fuel, Oil, Other,
        # NotKnown, Unset]
        description="Tanks's storage type (fluid type)",
        default_ps=('Pset_TankTypeCommon', 'StorageType'),
    )

    height = attribute.Attribute(
        description="Height of the tank",
        default_ps=('Pset_TankTypeCommon', 'NominalDepth'),
        unit=ureg.meter
    )

    diameter = attribute.Attribute(
        description="Diameter of the tank",
        default_ps=('Pset_TankTypeCommon', 'NominalLengthOrDiameter'),
        unit=ureg.meter,
    )

    volume = attribute.Attribute(
        description="Volume of the tank",
        default_ps=('Pset_TankTypeCommon', 'NominalCapacity'),
        unit=ureg.meter ** 3,
        functions=[_calc_volume]
    )

    number_of_sections = attribute.Attribute(
        description="Number of sections of the tank",
        default_ps=('Pset_TankTypeCommon', 'NumberOfSections'),
        unit=ureg.dimensionless,
    )


class Distributor(HVACProduct):
    ifc_types = {
        "IfcDistributionChamberElement":
            ['*', 'FORMEDDUCT', 'INSPECTIONCHAMBER', 'INSPECTIONPIT',
             'MANHOLE', 'METERCHAMBER', 'SUMP', 'TRENCH', 'VALVECHAMBER'],
        "IfcPipeFitting":
            ['NOTDEFINED', 'USERDEFINED']
    }
    # TODO why is pipefitting for DH found as Pipefitting and not distributor

    @property
    def expected_hvac_ports(self):
        return (2, float('inf'))

    pattern_ifc_type = [
        re.compile('Distribution.?chamber', flags=re.IGNORECASE),
        re.compile('Distributor', flags=re.IGNORECASE),
        re.compile('Verteiler', flags=re.IGNORECASE)
    ]

    # volume = attribute.Attribute(
    #     description="Volume of the Distributor",
    #     unit=ureg.meter ** 3
    # )

    nominal_power = attribute.Attribute(
        description="Nominal power of Distributor",
        unit=ureg.kilowatt
    )
    rated_mass_flow = attribute.Attribute(
        description="Rated mass flow of Distributor",
        unit=ureg.kg / ureg.s,
    )


class Pump(HVACProduct):
    ifc_types = {
        "IfcPump":
            ['*', 'CIRCULATOR', 'ENDSUCTION', 'SPLITCASE',
             'SUBMERSIBLEPUMP', 'SUMPPUMP', 'VERTICALINLINE',
             'VERTICALTURBINE']
    }

    @property
    def expected_hvac_ports(self):
        return 2

    pattern_ifc_type = [
        re.compile('Pumpe', flags=re.IGNORECASE),
        re.compile('Pump', flags=re.IGNORECASE)
    ]

    rated_current = attribute.Attribute(
        description="Rated current of pump",
        default_ps=('Pset_ElectricalDeviceCommon', 'RatedCurrent'),
        unit=ureg.ampere,
    )
    rated_voltage = attribute.Attribute(
        description="Rated current of pump",
        default_ps=('Pset_ElectricalDeviceCommon', 'RatedVoltage'),
        unit=ureg.volt,
    )

    def _calc_rated_power(self, name) -> ureg.Quantity:
        """Function to calculate the pump rated power using the rated current
        and rated voltage"""
        if self.rated_current and self.rated_voltage:
            return self.rated_current * self.rated_voltage
        else:
            return None

    rated_power = attribute.Attribute(
        description="Rated power of pump",
        unit=ureg.kilowatt,
        functions=[_calc_rated_power],
    )

    # Even if this is a bounded value, currently only the set point is used
    rated_mass_flow = attribute.Attribute(
        description="Rated mass flow of pump",
        default_ps=('Pset_PumpTypeCommon', 'FlowRateRange'),
        unit=ureg.kg / ureg.s,
    )

    rated_volume_flow = attribute.Attribute(
        description="Rated volume flow of pump",
        unit=ureg.m ** 3 / ureg.hour,
    )

    # Even if this is a bounded value, currently only the set point is used
    rated_pressure_difference = attribute.Attribute(
        description="Rated height or rated pressure difference of pump",
        default_ps=('Pset_PumpTypeCommon', 'FlowResistanceRange'),
        unit=ureg.newton / (ureg.m ** 2),
    )

    rated_height = attribute.Attribute(
        description="Rated height or rated pressure difference of pump",
        unit=ureg.meter,
    )

    nominal_rotation_speed = attribute.Attribute(
        description="nominal rotation speed of pump",
        default_ps=('Pset_PumpTypeCommon', 'NominalRotationSpeed'),
        unit=1 / ureg.s,
    )

    diameter = attribute.Attribute(
        unit=ureg.meter,
    )


class Valve(HVACProduct):
    ifc_types = {
        "IfcValve":
             ['*', 'AIRRELEASE', 'ANTIVACUUM', 'CHANGEOVER', 'CHECK',
             'COMMISSIONING', 'DIVERTING', 'DRAWOFFCOCK', 'DOUBLECHECK',
             'DOUBLEREGULATING', 'FAUCET', 'FLUSHING', 'GASCOCK',
             'GASTAP', 'ISOLATING', 'MIXING', 'PRESSUREREDUCING',
             'PRESSURERELIEF', 'REGULATING', 'SAFETYCUTOFF', 'STEAMTRAP',
             'STOPCOCK']
    }

    @property
    def expected_hvac_ports(self):
        return 2

    # expected_hvac_ports = 2

    pattern_ifc_type = [
        re.compile('Valve', flags=re.IGNORECASE),
        re.compile('Drossel', flags=re.IGNORECASE),
        re.compile('Ventil', flags=re.IGNORECASE)
    ]

    conditions = [
        condition.RangeCondition("diameter", 5.0 * ureg.millimeter,
                                 500.00 * ureg.millimeter)
    ]

    nominal_pressure_difference = attribute.Attribute(
        description="Nominal pressure difference of valve",
        default_ps=('Pset_ValveTypeCommon', 'CloseOffRating'),
        unit=ureg.pascal,
    )

    kv_value = attribute.Attribute(
        description="kv_value of valve",
        default_ps=('Pset_ValveTypeCommon', 'FlowCoefficient'),
    )

    valve_pattern = attribute.Attribute(
        # [SinglePort, Angled2Port, Straight2Port, Straight3Port,
        # Crossover2Port, Other, NotKnown, Unset]
        description="Nominal pressure difference of valve",
        default_ps=('Pset_ValveTypeCommon', 'ValvePattern'),
    )

    diameter = attribute.Attribute(
        description='Valve diameter',
        default_ps=('Pset_ValveTypeCommon', 'Size'),
        unit=ureg.millimeter,
        patterns=[
            re.compile('.*Durchmesser.*', flags=re.IGNORECASE),
            re.compile('.*Diameter.*', flags=re.IGNORECASE),
            re.compile('.*DN.*', flags=re.IGNORECASE),
        ],
    )

    length = attribute.Attribute(
        description='Length of Valve',
        unit=ureg.meter,
    )

    nominal_mass_flow_rate = attribute.Attribute(
        description='Nominal mass flow rate of the valve',
        unit=ureg.kg / ureg.s,
    )


class ThreeWayValve(Valve):
    ifc_types = {
        "IfcValve":
            ['MIXING']
    }

    pattern_ifc_type = [
        re.compile('3-Wege.*?ventil', flags=re.IGNORECASE)
    ]

    @property
    def expected_hvac_ports(self):
        return 3


class Duct(HVACProduct):
    ifc_types = {"IfcDuctSegment": ['*', 'RIGIDSEGMENT', 'FLEXIBLESEGMENT']}

    pattern_ifc_type = [
        re.compile('Duct.?segment', flags=re.IGNORECASE)
    ]

    diameter = attribute.Attribute(
        description='Duct diameter',
        unit=ureg.millimeter,
    )
    length = attribute.Attribute(
        description='Length of Duct',
        unit=ureg.meter,
    )


class DuctFitting(HVACProduct):
    ifc_types = {
        "IfcDuctFitting":
            ['*', 'BEND', 'CONNECTOR', 'ENTRY', 'EXIT', 'JUNCTION',
             'OBSTRUCTION', 'TRANSITION']
    }

    pattern_ifc_type = [
        re.compile('Duct.?fitting', flags=re.IGNORECASE)
    ]

    diameter = attribute.Attribute(
        description='Duct diameter',
        unit=ureg.millimeter,
    )
    length = attribute.Attribute(
        description='Length of Duct',
        unit=ureg.meter,
    )


class AirTerminal(HVACProduct):
    ifc_types = {
        "IfcAirTerminal":
            ['*', 'DIFFUSER', 'GRILLE', 'LOUVRE', 'REGISTER']
    }

    pattern_ifc_type = [
        re.compile('Air.?terminal', flags=re.IGNORECASE)
    ]

    diameter = attribute.Attribute(
        description='Terminal diameter',
        unit=ureg.millimeter,
    )

    def is_consumer(self):
        return True


class Medium(HVACProduct):
    # is deprecated?
    ifc_types = {"IfcDistributionSystem": ['*']}
    pattern_ifc_type = [
        re.compile('Medium', flags=re.IGNORECASE)
    ]

    @property
    def expected_hvac_ports(self):
        return 0


class CHP(HVACProduct):
    ifc_types = {'IfcElectricGenerator': ['CHP']}

    @property
    def expected_hvac_ports(self):
        return 2

    def is_generator(self):
        return True

    rated_power = attribute.Attribute(
        default_ps=('Pset_ElectricGeneratorTypeCommon', 'MaximumPowerOutput'),
        description="Rated power of CHP",
        patterns=[
            re.compile('.*Nennleistung', flags=re.IGNORECASE),
            re.compile('.*capacity', flags=re.IGNORECASE),
        ],
        unit=ureg.kilowatt,
    )

    efficiency = attribute.Attribute(
        default_ps=(
            'Pset_ElectricGeneratorTypeCommon', 'ElectricGeneratorEfficiency'),
        description="Electric efficiency of CHP",
        patterns=[
            re.compile('.*electric.*efficiency', flags=re.IGNORECASE),
            re.compile('.*el.*efficiency', flags=re.IGNORECASE),
        ],
        unit=ureg.dimensionless,
    )

    # water_volume = attribute.Attribute(
    #     description="Water volume CHP chp",
    #     unit=ureg.meter ** 3,
    # )


# collect all domain classes
items: Set[HVACProduct] = set()
for name, cls in inspect.getmembers(
        sys.modules[__name__],
        lambda member: inspect.isclass(member)  # class at all
                       and issubclass(member, HVACProduct)  # domain subclass
                       and member is not HVACProduct  # but not base class
                       and member.__module__ == __name__):  # declared here
    items.add(cls)
