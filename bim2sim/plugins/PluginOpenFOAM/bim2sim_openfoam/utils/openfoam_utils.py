from bim2sim.utilities.common_functions import filter_elements


class OpenFOAMUtils:
    @staticmethod
    def split_openfoam_elements(openfoam_elements: dict) -> tuple[list, list,
    list]:
        stl_bounds = filter_elements(openfoam_elements, 'StlBound')
        heaters = filter_elements(openfoam_elements, 'Heater')
        air_terminals = filter_elements(openfoam_elements, 'AirTerminal')
        return stl_bounds, heaters, air_terminals
