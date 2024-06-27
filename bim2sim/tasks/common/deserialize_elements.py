import pickle

from bim2sim.tasks.base import ITask


class DeserializeElements(ITask):
    """Deserialize elements, run() method holds detailed information."""

    touches = ('elements',)
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
        try:
            with open(pickle_path, 'rb') as file:
                elements = pickle.load(file)
            return elements,
        except KeyError:
            self.logger.warning(f"{self.__class__.__name__} task was executed "
                                f"but no serialized elements you could be"
                                f" found in path {pickle_path}")
