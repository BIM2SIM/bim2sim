import pickle

from bim2sim.tasks.base import ITask
from bim2sim.elements.aggregation import AggregationMixin


class SerializedElement:
    def __init__(self, element):
        self.guid = element.guid
        self.element_type = element.__class__.__name__
        self.attributes = {}
        for attr_name, attr_val in element.attributes.items():
            self.attributes[attr_name] = attr_val
        if hasattr(element, "storeys"):
            self.storeys = [storey.guid for storey in element.storeys]
        if issubclass(element.__class__, AggregationMixin):
            self.elements = [ele.guid for ele in element.elements]

    def __repr__(self):
        return "<serialized %s (guid: '%s')>" % (
            self.element_type, self.guid)


class SerializeElements(ITask):
    """Serialize element structure, run() method holds detailed information."""

    reads = ('elements', 'space_boundaries', 'tz_elements')
    touches = ('serialized_elements',)
    single_use = True

    def run(self, elements, space_boundaries, tz_elements):
        """Make the element structure serializable.

        As due to swigPy objects coming from IfcOpenShell we can't
        directly serialize a whole bim2sim project or even the elements
        structure with serializers like pickle. To still keep the element
        structure information after a project run, we just copy the relevant
        information like the attributes from the AttributeManager, guid and
        type of the element to a simple SerializedElement instance and store it
        with pickle.

        Args:
            elements: dict[guid: element] of bim2sim element structure
            space_boundaries: dict[guid: SpaceBoundary] of bim2sim
                SpaceBoundaries
            tz_elements: dict[guid: tz] of bim2sim ThermalZones

        Returns:
            serialized_elements: dict[guid: serializedElement] of serialized
                elements
        """
        all_elements = {**elements, **space_boundaries, **tz_elements}
        serialized_elements = {}
        for ele in all_elements.values():
            se = SerializedElement(ele)
            serialized_elements[se.guid] = se
        pickle_path = self.paths.export / "serialized_elements.pickle"
        with open(pickle_path, "wb") as outfile:
            pickle.dump(serialized_elements, outfile)

        return serialized_elements,
