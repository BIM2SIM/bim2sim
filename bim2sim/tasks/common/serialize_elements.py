import pickle
from typing import Tuple, Dict

from bim2sim.elements.base_elements import SerializedElement
from bim2sim.tasks.base import ITask


class SerializeElements(ITask):
    """Serialize element structure, run() method holds detailed information."""

    reads = ('elements',)
    touches = ('serialized_elements',)
    single_use = True

    def run(self, elements: dict) -> Tuple[Dict]:
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

        Returns:
            serialized_elements: dict[guid: serializedElement] of serialized
                elements
        """
        all_elements = {**elements,}
        serialized_elements = {}
        for ele in all_elements.values():
            se = SerializedElement(ele)
            serialized_elements[se.guid] = se
        pickle_path = self.paths.export / "serialized_elements.pickle"
        with open(pickle_path, "wb") as outfile:
            pickle.dump(serialized_elements, outfile)

        return serialized_elements,
