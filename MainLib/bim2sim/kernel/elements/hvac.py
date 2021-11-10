﻿"""Module contains the different classes for all HVAC elements"""
import inspect
import itertools
import sys
from functools import lru_cache
import logging
import math
import re
from typing import Set, List, Tuple, Generator

import numpy as np

from bim2sim.kernel import condition, attribute
from bim2sim.decision import BoolDecision, ListDecision, DecisionBunch
from bim2sim.kernel.element import Port, ProductBased
from bim2sim.kernel.units import ureg


logger = logging.getLogger(__name__)


def diameter_post_processing(value):
    if isinstance(value, (list, set)):
        return sum(value) / len(value)
    return value


def length_post_processing(value):
    if isinstance(value, (list, set)):
        return max(value)
    return value


class HVACPort(Port):
    """Port of HVACProduct."""
    vl_pattern = re.compile('.*vorlauf.*', re.IGNORECASE)  # TODO: extend pattern
    rl_pattern = re.compile('.*rücklauf.*', re.IGNORECASE)

    def __init__(
            self, *args, groups: Set = None,
            flow_direction: int = 0, **kwargs):
        super().__init__(*args, **kwargs)

        self._flow_master = False
        self._flow_direction = None
        self._flow_side = None

        self.groups = groups or set()
        self.flow_direction = flow_direction

    @classmethod
    def ifc2args(cls, ifc) -> Tuple[tuple, dict]:
        args, kwargs = super().ifc2args(ifc)
        groups = {assg.RelatingGroup.ObjectType
                  for assg in ifc.HasAssignments}
        flow_direction = None
        if ifc.FlowDirection == 'SOURCE':
            flow_direction = 1
        elif ifc.FlowDirection == 'SINK':
            flow_direction = -1
        elif ifc.FlowDirection == 'SINKANDSOURCE':
            flow_direction = 0

        kwargs['groups'] = groups
        kwargs['flow_direction'] = flow_direction
        return args, kwargs

    def calc_position(self):
        """returns absolute position as np.array"""
        try:
            relative_placement = \
                self.parent.ifc.ObjectPlacement.RelativePlacement
            x_direction = np.array(relative_placement.RefDirection.DirectionRatios)
            z_direction = np.array(relative_placement.Axis.DirectionRatios)
        except AttributeError:
            x_direction = np.array([1, 0, 0])
            z_direction = np.array([0, 0, 1])
        y_direction = np.cross(z_direction, x_direction)
        directions = np.array((x_direction, y_direction, z_direction)).T
        port_coordinates_relative = \
            np.array(self.ifc.ObjectPlacement.RelativePlacement.Location.Coordinates)
        coordinates = self.parent.position + np.matmul(directions, port_coordinates_relative)

        if all(coordinates == np.array([0, 0, 0])):
            logger = logging.getLogger('IFCQualityReport')
            logger.info("Suspect position [0, 0, 0] for %s", self)
        return coordinates

    @classmethod
    def pre_validate(cls, ifc) -> bool:
        return True

    def validate(self) -> bool:
        return True

    @property
    def flow_master(self):
        """Lock flow direction for port"""
        return self._flow_master

    @flow_master.setter
    def flow_master(self, value: bool):
        self._flow_master = value

    @property
    def flow_direction(self):
        """Flow direction of port

        -1 = medium flows into port
        1 = medium flows out of port
        0 = medium flow undirected
        None = flow direction unknown"""
        return self._flow_direction

    @flow_direction.setter
    def flow_direction(self, value):
        if self._flow_master:
            raise AttributeError("Can't set flow direction for flow master.")
        if value not in (-1, 0, 1, None):
            raise AttributeError("Invalid value. Use one of (-1, 0, 1, None).")
        self._flow_direction = value

    @property
    def verbose_flow_direction(self):
        """Flow direction of port"""
        if self.flow_direction == -1:
            return 'SINK'
        if self.flow_direction == 0:
            return 'SINKANDSOURCE'
        if self.flow_direction == 1:
            return 'SOURCE'
        return 'UNKNOWN'

    @property
    def flow_side(self):
        """VL(1), RL(-1), UNKNOWN(0)"""
        if self._flow_side is None:
            self._flow_side = self.determine_flow_side()
        return self._flow_side

    @flow_side.setter
    def flow_side(self, value):
        if value not in (-1, 0, 1):
            raise ValueError("allowed values for flow_side are 1, 0, -1")
        previous = self._flow_side
        self._flow_side = value
        if previous:
            if previous != value:
                logger.info("Overwriting flow_side for %r with %s" % (self, self.verbose_flow_side))
        else:
            logger.debug("Set flow_side for %r to %s" % (self, self.verbose_flow_side))

    @property
    def verbose_flow_side(self):
        if self.flow_side == 1:
            return "VL"
        if self.flow_side == -1:
            return "RL"
        return "UNKNOWN"

    def determine_flow_side(self):
        """Check groups for hints of flow_side and returns flow_side if hints are definitely"""
        vl = None
        rl = None
        if self.parent.is_generator():
            if self.flow_direction == 1:
                vl = True
            elif self.flow_direction == -1:
                rl = True
        elif self.parent.is_consumer():
            if self.flow_direction == 1:
                rl = True
            elif self.flow_direction == -1:
                vl = True
        if not vl:
            vl = any(filter(self.vl_pattern.match, self.groups))
        if not rl:
            rl = any(filter(self.rl_pattern.match, self.groups))

        if vl and not rl:
            return 1
        if rl and not vl:
            return -1
        return 0


class HVACProduct(ProductBased):
    domain = 'HVAC'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.inner_connections: List[Tuple[HVACPort, HVACPort]] \
            = self.get_inner_connections()

    def get_ports(self):
        ports = []
        try:
            for nested in self.ifc.IsNestedBy:
                # valid for IFC for Revit v19.2.0.0
                for element_port_connection in nested.RelatedObjects:
                    if element_port_connection.is_a() == 'IfcDistributionPort':
                        ports.append(HVACPort.from_ifc(
                            ifc=element_port_connection, parent=self))
                    else:
                        logger.warning(
                            "Not included %s as Port in %s",
                            element_port_connection.is_a(), self)
        except AttributeError as ae:
            logger.warning("Failed to create Port")
            pass
        # valid for IFC for Revit v19.1.0.0
        element_port_connections = getattr(self.ifc, 'HasPorts', [])
        for element_port_connection in element_port_connections:
            ports.append(HVACPort.from_ifc(
                ifc=element_port_connection.RelatingPort, parent=self))
        return ports

    def get_inner_connections(self) -> List[Tuple[HVACPort, HVACPort]]:
        """Returns inner connections of Element

        by default each port is connected to each other port.
        Overwrite for other connections"""

        connections = []
        for port0, port1 in itertools.combinations(self.ports, 2):
            connections.append((port0, port1))
        return connections

    def decide_inner_connections(self) -> Generator[DecisionBunch, None, None]:
        """Generator method yielding decisions to set inner connections."""
        if len(self.ports) < 2:
            # no chance to connect anything
            return

        # TODO: extend pattern
        vl_pattern = re.compile('.*vorlauf.*', re.IGNORECASE)
        rl_pattern = re.compile('.*rücklauf.*', re.IGNORECASE)

        # use score for ports to help user find best match
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
        vl.flow_side = 1
        rl.flow_side = -1
        self.inner_connections.append((vl, rl))


class HeatPump(HVACProduct):
    """"HeatPump"""

    ifc_types = {}  # IFC Schema does not support Heatpumps

    pattern_ifc_type = [
        re.compile('Heat.?pump', flags=re.IGNORECASE),
        re.compile('W(ä|ae)rme.?pumpe', flags=re.IGNORECASE),
    ]

    min_power = attribute.Attribute(
        description='Minimum power that HeatPump operates at.',
        unit=ureg.kilowatt,
    )
    rated_power = attribute.Attribute(
        description='Rated power of HeatPump.',
        unit=ureg.kilowatt,
    )
    efficiency = attribute.Attribute(
        description='Efficiency of HeatPump provided as list with pairs of [percentage_of_rated_power,efficiency]',
        unit=ureg.dimensionless,
    )


class Chiller(HVACProduct):
    """"Chiller"""

    ifc_types = {'IfcChiller': ['*', 'AIRCOOLED', 'WATERCOOLED', 'HEATRECOVERY']}

    pattern_ifc_type = [
        re.compile('Chiller', flags=re.IGNORECASE),
        re.compile('K(ä|ae)lte.?maschine', flags=re.IGNORECASE),
    ]

    min_power = attribute.Attribute(
        description='Minimum power that Chiller operates at.',
        unit=ureg.kilowatt,
    )
    rated_power = attribute.Attribute(
        description='Rated power of Chiller.',
        unit=ureg.kilowatt,
    )
    efficiency = attribute.Attribute(
        description='Efficiency of Chiller provided as list with pairs of [percentage_of_rated_power,efficiency]',
        unit=ureg.dimensionless,
    )


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

    min_power = attribute.Attribute(
        description='Minimum power that CoolingTower operates at.',
        unit=ureg.kilowatt,
    )
    rated_power = attribute.Attribute(
        description='Rated power of CoolingTower.',
        unit=ureg.kilowatt,
    )
    efficiency = attribute.Attribute(
        description='Efficiency of CoolingTower provided as list with pairs of [percentage_of_rated_power,efficiency]',
        unit=ureg.dimensionless,
    )


class HeatExchanger(HVACProduct):
    """"Heatexchanger"""

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
        description='Efficiency of HeatExchange provided as list with pairs of [percentage_of_rated_power,efficiency]',
        unit=ureg.dimensionless,
    )


class Boiler(HVACProduct):
    """Boiler"""
    ifc_types = {'IfcBoiler': ['*', 'WATER', 'STEAM']}

    pattern_ifc_type = [
        # re.compile('Heat.?pump', flags=re.IGNORECASE),
        re.compile('Kessel', flags=re.IGNORECASE),
        re.compile('Boiler', flags=re.IGNORECASE),
    ]

    # def _add_ports(self):
    #    super()._add_ports()
    #    for port in self.ports:
    #        if port.flow_direction == 1:
    #            port.flow_master = True
    #        elif port.flow_direction == -1:
    #            port.flow_master = True

    def is_generator(self):
        """boiler is generator function"""
        return True

    # @lru_cache()
    def get_inner_connections(self):
        return []  #
        # connections = []
        # vl_pattern = re.compile('.*vorlauf.*', re.IGNORECASE)  # TODO: extend pattern
        # rl_pattern = re.compile('.*rücklauf.*', re.IGNORECASE)
        # VL = []
        # RL = []
        # for port in self.ports:
        #     if any(filter(vl_pattern.match, port.groups)):
        #         if port.flow_direction == 1:
        #             VL.append(port)
        #         else:
        #             logger.warning("Flow direction (%s) of %s does not match %s",
        #                                 port.verbose_flow_direction, port, port.groups)
        #             decision = BoolDecision(
        #                 "Use %s as VL?" % (port),
        #                 global_key=port.guid)
        #             use = decision.decide()
        #             if use:
        #                 VL.append(port)
        #     elif any(filter(rl_pattern.match, port.groups)):
        #         if port.flow_direction == -1:
        #             RL.append(port)
        #         else:
        #             logger.warning("Flow direction (%s) of %s does not match %s",
        #                                 port.verbose_flow_direction, port, port.groups)
        #             decision = BoolDecision(
        #                 "Use %s as RL?" % (port),
        #                 global_key=port.guid)
        #             use = decision.decide()
        #             if use:
        #                 RL.append(port)
        # if len(VL) == 1 and len(RL) == 1:
        #     VL[0].flow_side = 1
        #     RL[0].flow_side = -1
        #     connections.append((RL[0], VL[0]))
        # else:
        #     logger.warning("Unable to solve inner connections for %s", self)
        # return connections

    water_volume = attribute.Attribute(
        description="Water volume of boiler",
        unit=ureg.meter ** 3,
    )

    min_power = attribute.Attribute(
        description="Minimum power that boiler operates at",
        unit=ureg.kilowatt,
    )

    rated_power = attribute.Attribute(
        description="Rated power of boiler",
        unit=ureg.kilowatt,
    )

    efficiency = attribute.Attribute(
        description="Efficiency of boiler provided as list with pairs of [percentage_of_rated_power,efficiency]",
        unit=ureg.dimensionless,
    )


class Pipe(HVACProduct):
    ifc_types = {
        "IfcPipeSegment":
            ['*', 'CULVERT', 'FLEXIBLESEGMENT', 'RIGIDSEGMENT', 'GUTTER',
             'SPOOL']
    }

    conditions = [
        condition.RangeCondition("diameter", 5.0 * ureg.millimeter, 300.00 * ureg.millimeter)  # ToDo: unit?!
    ]

    diameter = attribute.Attribute(
        default_ps=('Pset_PipeSegmentTypeCommon', 'NominalDiameter'),
        unit=ureg.millimeter,
        patterns=[
            re.compile('.*Durchmesser.*', flags=re.IGNORECASE),
            re.compile('.*Diameter.*', flags=re.IGNORECASE),
        ],
        ifc_postprocessing=diameter_post_processing,
    )

    @staticmethod
    def _length_from_geometry(bind, name):
        try:
            return Pipe.get_lenght_from_shape(bind.ifc.Representation)
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

    @staticmethod
    def get_lenght_from_shape(ifc_representation):
        """Serach for extruded depth in representations

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
            raise AttributeError("Too many representations to dertermine length %s." % candidates)

        return candidates[0]


class PipeFitting(HVACProduct):
    ifc_types = {
        "IfcPipeFitting":
            ['*', 'BEND', 'CONNECTOR', 'ENTRY', 'EXIT', 'JUNCTION', 'OBSTRUCTION',
             'TRANSITION']
    }

    conditions = [
        condition.RangeCondition("diameter", 5.0 * ureg.millimeter, 300.00 * ureg.millimeter)
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

    length = attribute.Attribute(
        default_ps=("Qto_PipeSegmentBaseQuantities", "Length"),
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

    @staticmethod
    def _diameter_post_processing(value):
        if isinstance(value, list):
            return np.average(value).item()
        return value


class SpaceHeater(HVACProduct):
    ifc_types = {'IfcSpaceHeater': ['*', 'CONVECTOR', 'RADIATOR']}

    pattern_ifc_type = [
        re.compile('Space.?heater', flags=re.IGNORECASE)
    ]

    def is_consumer(self):
        return True

    rated_power = attribute.Attribute(
        description="Rated power of SpaceHeater",
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


# class ExpansionTank(HVACProduct):
#     ifc_type = "IfcTank"   #ToDo: IfcTank, IfcTankType=Expansion
#     predefined_types = ['BASIN', 'BREAKPRESSURE', 'EXPANSION', 'FEEDANDEXPANSION', 'STORAGE', 'VESSEL']
#     pattern_ifc_type = [
#         re.compile('Expansion.?Tank', flags=re.IGNORECASE),
#         re.compile('Ausdehnungs.?gef(ä|ae)(ss|ß)', flags=re.IGNORECASE),
#     ]


# class StorageDevice(HVACProduct):
#     """IFC4 CHANGE  This entity has been deprecated for instantiation and will become ABSTRACT in a future release;
#     new subtypes should now be used instead."""
#     ifc_type = "IfcStorageDevice"
#     pattern_ifc_type = [
#         re.compile('Storage.?device', flags=re.IGNORECASE)
#     ]


class Storage(HVACProduct):
    ifc_types = {
        "IfcTank":
            ['BASIN', 'STORAGE', 'VESSEL']
        # 'BREAKPRESSURE', 'EXPANSION', 'FEEDANDEXPANSION',
    }

    conditions = [
        condition.RangeCondition('volume', 50 * ureg.liter, math.inf * ureg.liter)
    ]

    pattern_ifc_type = [
        re.compile('Tank', flags=re.IGNORECASE),
        re.compile('Speicher', flags=re.IGNORECASE),
        # re.compile('Expansion.?Tank', flags=re.IGNORECASE),
        re.compile('Ausdehnungs.?gef(ä|ae)(ss|ß)', flags=re.IGNORECASE),
    ]

    @property
    def storage_type(self):
        return None

    height = attribute.Attribute(
        unit=ureg.meter,
    )

    diameter = attribute.Attribute(
        unit=ureg.millimeter,
    )

    @property
    def port_positions(self):
        return (0, 0.5, 1)

    def _calc_volume(self):
        return self.height * self.diameter ** 2 / 4 * math.pi

    volume = attribute.Attribute(
        unit=ureg.meter ** 3,
    )


class Distributor(HVACProduct):
    ifc_types = {
        "IfcDistributionChamberElement":
            ['FORMEDDUCT', 'INSPECTIONCHAMBER', 'INSPECTIONPIT',
             'MANHOLE', 'METERCHAMBER', 'SUMP', 'TRENCH', 'VALVECHAMBER']
    }

    pattern_ifc_type = [
        re.compile('Distribution.?chamber', flags=re.IGNORECASE),
        re.compile('Distributor', flags=re.IGNORECASE),
        re.compile('Verteiler', flags=re.IGNORECASE)
    ]

    volume = attribute.Attribute(
        description="Volume of the Distributor",
        unit=ureg.meter ** 3
    )

    nominal_power = attribute.Attribute(
        description="Nominal power of Distributor",
        unit=ureg.kilowatt
    )


class Pump(HVACProduct):
    ifc_types = {
        "IfcPump":
            ['*', 'CIRCULATOR', 'ENDSUCTION', 'SPLITCASE',
             'SUBMERSIBLEPUMP', 'SUMPPUMP', 'VERTICALINLINE',
             'VERTICALTURBINE']
    }

    pattern_ifc_type = [
        re.compile('Pumpe', flags=re.IGNORECASE),
        re.compile('Pump', flags=re.IGNORECASE)
    ]

    rated_power = attribute.Attribute(
        unit=ureg.kilowatt,
    )

    rated_height = attribute.Attribute(
        unit=ureg.meter,
    )

    rated_volume_flow = attribute.Attribute(
        unit=ureg.meter ** 3 / ureg.hour,
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

    pattern_ifc_type = [
        re.compile('Valve', flags=re.IGNORECASE),
        re.compile('Drossel', flags=re.IGNORECASE),
        re.compile('Ventil', flags=re.IGNORECASE)
    ]

    conditions = [
        condition.RangeCondition("diameter", 5.0 * ureg.millimeter, 500.00 * ureg.millimeter)  # ToDo: unit?!
    ]

    diameter = attribute.Attribute(
        description='Valve diameter',
        unit=ureg.millimeter,
        patterns=[
            re.compile('.*Durchmesser.*', flags=re.IGNORECASE),
            re.compile('.*Diameter.*', flags=re.IGNORECASE),
            re.compile('.*DN.*', flags=re.IGNORECASE),
        ],
    )
    # @cached_property
    # def diameter(self):
    #     result = self.find('diameter')
    #
    #     if isinstance(result, list):
    #         return np.average(result).item()
    #     return result

    length = attribute.Attribute(
        description='Length of Valve',
        unit=ureg.meter,
    )


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


class Medium(HVACProduct):
    # is deprecated?
    ifc_types = {"IfcDistributionSystems": ['*']}
    pattern_ifc_type = [
        re.compile('Medium', flags=re.IGNORECASE)
    ]


class CHP(HVACProduct):
    ifc_types = {'IfcElectricGenerator': ['CHP']}

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
        default_ps=('Pset_ElectricGeneratorTypeCommon', 'ElectricGeneratorEfficiency'),
        description="Electric efficiency of CHP",
        patterns=[
            re.compile('.*electric.*efficiency', flags=re.IGNORECASE),
            re.compile('.*el.*efficiency', flags=re.IGNORECASE),
        ],
        unit=ureg.dimensionless,
    )

    water_volume = attribute.Attribute(
        description="Water volume CHP chp",
        unit=ureg.meter ** 3,
    )


# collect all domain classes
items: Set[HVACProduct] = set()
for name, cls in inspect.getmembers(
        sys.modules[__name__],
        lambda member: inspect.isclass(member)  # class at all
                       and issubclass(member, HVACProduct)  # domain subclass
                       and member is not HVACProduct  # but not base class
                       and member.__module__ == __name__):  # declared here
    items.add(cls)
