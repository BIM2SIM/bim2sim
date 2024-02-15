import pickle

from bim2sim.tasks.base import ITask


class DeserializeElements(ITask):
    """Deserialize elements, run() method holds detailed information."""

    touches = ('deserialized_elements',)
    single_use = True

    def run(self):
        """Deserializes the elements from a previous run.

        Loads the serialized_elements from a previous run from the pickled
        object.

        Returns:
            serialized_elements: dict[guid: serializedElement] of serialized
                elements
        """
        pickle_path = self.paths.export / "serialized_elements.pickle"

        with open(pickle_path, 'rb') as file:
            serialized_elements = pickle.load(file)
        return serialized_elements,
