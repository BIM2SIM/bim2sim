from ifcopenshell.entity_instance import entity_instance

from bim2sim.kernel.elements import hvac
from bim2sim.kernel.ifc2python import get_ports
from bim2sim.task.base import Playground
from bim2sim.task.common.common import CheckIfc


class CheckIfcHVAC(CheckIfc):
    """
    Check an IFC file for a number of conditions (missing information, incorrect information, etc) that could lead on
    future tasks to fatal errors.
    """

    def __init__(self, playground: Playground):
        super().__init__(playground)
        self.sub_inst_cls = 'IfcDistributionPort'
        self.plugin = hvac

    def validate_sub_inst(self, port: entity_instance) -> list:
        """
        Validation function for a port that compiles all validation functions.

        Args:
            port: IFC port entity

        Returns:
            error: list of errors found in the IFC port

        """
        error = []
        self.apply_validation_function(self._check_unique(port, self.id_list),
                                       'GlobalId - '
                                       'The space boundary GlobalID is not '
                                       'unique', error)
        self.apply_validation_function(self._check_flow_direction(port),
                                       'FlowDirection - '
                                       'The port flow direction is missing', error)
        self.apply_validation_function(self._check_assignments(port),
                                       'Assignments - '
                                       'The port assignments are missing', error)
        self.apply_validation_function(self._check_connection(port),
                                       'Connections - '
                                       'The port has no connections', error)
        self.apply_validation_function(self._check_contained_in(port),
                                       'ContainedIn - '
                                       'The port is not contained in', error)

        return error

    def validate_instances(self, inst: entity_instance) -> list:
        """
        Validation function for an instance that compiles all instance validation functions.

        Args:
            inst: IFC instance being checked

        Returns:
            error: list of instances error

        """
        error = []
        self.apply_validation_function(self._check_unique(inst, self.id_list),
                                       'GlobalId - '
                                       'The instance GlobalID is not unique', error)
        self.apply_validation_function(self._check_inst_ports(inst),
                                       'Ports - '
                                       'The instance ports are missing', error)
        self.apply_validation_function(self._check_contained_in_structure(inst),
                                       'ContainedInStructure - '
                                       'The instance is not contained in any '
                                       'structure', error)
        self.apply_validation_function(self._check_inst_properties(inst),
                                       'Missing Property_Sets - '
                                       'One or more instance\'s necessary '
                                       'property sets are missing', error)
        self.apply_validation_function(self._check_inst_representation(inst),
                                       'Representation - '
                                       'The instance has no geometric '
                                       'representation', error)
        self.apply_validation_function(self._check_assignments(inst),
                                       'Assignments - ' 
                                       'The instance assignments are missing', error)

        return error

    @staticmethod
    def _check_flow_direction(port: entity_instance) -> bool:
        """
        Check that the port has a defined flow direction.

        Args:
            port: port IFC entity

        Returns:
            True if check succeeds, False otherwise
        """
        return port.FlowDirection in ['SOURCE', 'SINK', 'SINKANDSOURCE',
                                      'SOURCEANDSINK']

    @staticmethod
    def _check_assignments(port: entity_instance) -> bool:
        """
        Check that the port has at least one assignment.

        Args:
            port: port ifc entity

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return any(assign.is_a('IfcRelAssignsToGroup') for assign in
                   port.HasAssignments)

    @staticmethod
    def _check_connection(port: entity_instance) -> bool:
        """
        Check that the port is: "connected_to" or "connected_from".

        Args:
            port: port ifc entity

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return len(port.ConnectedTo) > 0 or len(port.ConnectedFrom) > 0

    @staticmethod
    def _check_contained_in(port: entity_instance) -> bool:
        """
        Check that the port is "contained_in".

        Args:
            port: port ifc entity

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return len(port.ContainedIn) > 0

    # instances check
    @staticmethod
    def _check_inst_ports(inst: entity_instance) -> bool:
        """
        Check that an instance has associated ports.

        Args:
            inst: IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        ports = get_ports(inst)
        if ports:
            return True
        else:
            return False

    @staticmethod
    def _check_contained_in_structure(inst: entity_instance) -> bool:
        """
        Check that an instance is contained in an structure.

        Args:
            inst: IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        if hasattr(inst, 'ContainedInStructure'):
            return len(inst.ContainedInStructure) > 0
        else:
            return False
