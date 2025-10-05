import pickle

from OCC.Core.gp import gp_Pnt

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
            for element in elements.values():
                for key, value in vars(element).items():
                    if 'guid' in key:
                        continue
                    if isinstance(value, list):
                        new_list = []
                        for val in value:
                            if isinstance(val, str):
                                try:
                                    self.logger.info(
                                        f"try to convert string {val} to "
                                        f"element")
                                    new_val = elements[val]
                                    new_list.append(new_val)
                                except:
                                    new_list.append(val)
                                    self.logger.info(
                                        f"could not convert string {val} to "
                                        f"element")
                            else:
                                new_list.append(val)
                        setattr(element, key, new_list)
                    elif isinstance(value, str):
                        try:
                            self.logger.info(
                                f"try to convert string {value} to "
                                f"element")
                            new_val = elements[value]
                            setattr(element, key, new_val)
                        except:
                            self.logger.info(
                                f"could not convert string {value} to "
                                f"element")
                    elif isinstance(value, tuple) and len(value) == 3:
                        try:
                            self.logger.info(
                                f"try to convert tuple {value} to "
                                f"gp_Pnt (coordinates)")
                            new_val = gp_Pnt(*value)
                            setattr(element, key, new_val)
                        except ValueError:
                            self.logger.info(
                                f"could not convert tuple {value} to "
                                f"gp_Pnt (coordinates)")
                    else:
                        continue
            return elements,
        except KeyError:
            self.logger.warning(f"{self.__class__.__name__} task was executed "
                                f"but no serialized elements you could be"
                                f" found in path {pickle_path}")
