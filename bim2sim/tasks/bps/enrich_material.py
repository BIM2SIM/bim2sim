import ast
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from bim2sim.elements.base_elements import Material
from bim2sim.elements.bps_elements import Layer, LayerSet, Building
from bim2sim.kernel.decision import DecisionBunch
from bim2sim.sim_settings import BuildingSimSettings
from bim2sim.tasks.base import ITask
from bim2sim.tasks.base import Playground
from bim2sim.utilities.common_functions import filter_elements, \
    get_type_building_elements, get_material_templates
from bim2sim.utilities.types import LOD, AttributeDataSource


class EnrichMaterial(ITask):
    """Enriches material properties that were recognized as invalid
    LOD.layers = Medium & Full"""

    reads = ('elements',)

    mapping_templates_bim2sim = {
        "OuterWall": ["OuterWall", "OuterWallDisaggregated"],
        "InnerWall": ["InnerWall", "InnerWallDisaggregated"],
        "Window": ["Window"],
        "Roof": ["Roof"],
        "Floor": ["InnerFloor", "InnerFloorDisaggregated"],
        "GroundFloor": ["GroundFloor", "GroundFloorDisaggregated"],
        "Door": ["OuterDoor", "InnerDoor", "OuterDoorDisaggregated",
                 "InnerDoorDisaggregated"],
    }

    def __init__(self, playground: Playground):
        super().__init__(playground)
        self.layer_sets_added = []
        self.template_materials = {}

    def run(self, elements: dict):
        """Enriches materials and layer sets of building elements.

        Enrichment data in the files MaterialTemplates.json and
        TypeElements_IWU.json is taken from TEASER. The underlying data
        comes from IWU data. For more detailed information please review TEASER
        code documentation:
        https://rwth-ebc.github.io/TEASER//master/docs/index.html
        """
        # TODO add data_source also to non attributes values:
        #  layer and layerset
        [element_templates, material_template] = \
            yield from self.get_templates(elements)
        if self.playground.sim_settings.layers_and_materials is LOD.low:
            self.create_new_layer_sets_and_materials(
                elements, element_templates, material_template)

        if self.playground.sim_settings.layers_and_materials is LOD.full:
            # TODO #676
            raise NotImplementedError("layers_and_materials full is currently"
                                      " not supported.")
        for layer_set in self.layer_sets_added:
            elements[layer_set.guid] = layer_set
            for layer in layer_set.layers:
                elements[layer.guid] = layer
        for material in self.template_materials.values():
            elements[material.guid] = material

    def create_new_layer_sets_and_materials(
            self, elements: dict,
            element_templates: dict,
            material_template: dict):
        """Create a new layer set including layers and materials.

        This creates a completely new layer set, including the relevant layers
        and materials. Materials are only created once, even if they occur in
        multiple layer sets/layers.
        Additionally, some information on element level are overwritten with
        data from the templates, like inner_convection etc.
        """
        # TODO multi building support would require to have relations
        #  between each bim2sim element and its bim2sim Building
        #  instance. For now we always take the first building.
        element_template = element_templates[
            list(element_templates.keys())[0]]
        for template_name, ele_types in (
                self.mapping_templates_bim2sim.items()):
            layer_set = self.create_layer_set_from_template(
                element_template[template_name], material_template)
            ele_enrichment_data = self.enrich_element_data_from_template(
                element_template[template_name])
            elements_to_enrich = []
            # TODO no roof, groundfloor or floors in this project...
            for ele_type in ele_types:
                elements_to_enrich.extend(filter_elements(elements, ele_type))
            for element in elements_to_enrich:
                # set layer_set
                element.layerset = layer_set
                # TODO set layer_set also to not disaggregated parent, t.b.d.
                # if hasattr(element, "disagg_parent"):
                #     element.disagg_parent.layerset = layer_set
                # overwrite element level attributes like inner_convection
                for att, value in ele_enrichment_data.items():
                    if hasattr(element, att):
                        setattr(element, att, value)
                # overwrite thickness/width of element with enriched layer_set
                # thickness
                if hasattr(element, "width"):
                    element.width = (
                        layer_set.thickness, AttributeDataSource.enrichment)

    @staticmethod
    def enrich_element_data_from_template(element_template: dict) -> dict:
        """Get all element level enrichment data from templates."""
        ele_enrichment_data = {key: info for key, info in
                               element_template.items()
                               if type(info) not in [list, dict]}
        return ele_enrichment_data

    def create_layer_set_from_template(self, element_template: dict,
                                       material_template: dict) -> LayerSet:
        """Create layer set from template including layers and materials."""
        layer_set = LayerSet()
        for layer_template in element_template['layer'].values():
            layer = Layer()
            layer.thickness = layer_template['thickness']
            material_name = layer_template['material']['name']
            if material_name in self.template_materials:
                material = self.template_materials[material_name]
            else:
                material = self.create_material_from_template(
                    material_template[material_name])
                self.template_materials[material_name] = material
            material.parents.append(layer)
            layer.material = material
            layer.to_layerset.append(layer_set)
            layer_set.layers.append(layer)
        self.layer_sets_added.append(layer_set)
        return layer_set

    @staticmethod
    def create_material_from_template(material_template: dict) -> Material:
        """Creates a material from template."""
        material = Material()
        material.name = material_template['material']
        material.density = (
            material_template['density'], AttributeDataSource.enrichment)
        material.spec_heat_capacity = (
            material_template['heat_capac'], AttributeDataSource.enrichment)
        material.thermal_conduc = (
            material_template['thermal_conduc'],
            AttributeDataSource.enrichment)
        material.solar_absorp = (
            material_template['solar_absorp'], AttributeDataSource.enrichment)
        return material

    def get_templates(self, elements: dict) -> object:
        """Get templates for elements and materials.

        Args:
            elements: dict[guid: element] of bim2sim elements
        Returns:
            element_templates (dict): Holds enrichment templates for each
             Building with layer set information and material reference for
              different BPSProducts
            material_templates (dict): Holds information about physical
             attributes for each material referenced in the element_templates
        """
        buildings = filter_elements(elements, Building)
        element_templates = yield from self.get_templates_for_buildings(
            buildings, self.playground.sim_settings)
        if not element_templates:
            self.logger.warning(
                "Tried to run enrichment for layers structure and materials, "
                "but no fitting templates were found. "
                "Please check your settings.")
            return elements,
        material_templates = self.get_material_templates()
        return element_templates, material_templates

    @staticmethod
    def get_material_templates(attrs: dict = None) -> dict:
        """get dict with the material templates and its respective
        attributes"""
        material_templates = get_material_templates()
        resumed = {}
        for k in material_templates:
            resumed[material_templates[k]['name']]: dict = {}
            if attrs is not None:
                for attr in attrs:
                    if attr == 'thickness':
                        resumed[material_templates[k]['name']][attr] = \
                            material_templates[k]['thickness_default']
                    else:
                        resumed[material_templates[k]['name']][attr] = \
                            material_templates[k][attr]
            else:
                for attr in material_templates[k]:
                    if attr == 'thickness_default':
                        resumed[material_templates[k]['name']]['thickness'] = \
                            material_templates[k][attr]
                    elif attr == 'name':
                        resumed[material_templates[k]['name']]['material'] = \
                            material_templates[k][attr]
                    elif attr == 'thickness_list':
                        continue
                    else:
                        resumed[material_templates[k]['name']][attr] = \
                            material_templates[k][attr]
        return resumed

    @dataclass
    class ConstructionTemplate:
        """Data class to hold construction template information.

        Attributes:
            walls: Path to wall construction data file
            windows: Path to window construction data file
            doors: Path to door construction data file
        """
        walls: Path
        windows: Path
        doors: Path

    @staticmethod
    def determine_construction_data_file(construction_type: str,
                                         data_source: str) -> Path:
        """Determines the appropriate construction data file based on the data source.

        Args:
            construction_type: Type of construction element ('wall', 'window', or 'door')
            data_source: Source of construction data (e.g., 'iwu', 'kfw', 'tabula_de')

        Returns:
            Path: Path to the construction data file

        Raises:
            ValueError: If the construction data source is unknown
        """
        # Map of known data sources to their respective files
        source_to_file = {
            'iwu': 'TypeElements_IWU.json',
            'kfw': 'TypeElements_KFW.json',
            'tabula_de': 'TypeElements_TABULA_DE.json',
            'tabula_dk': 'TypeElements_TABULA_DK.json'
        }

        # Special case for IWU windows
        iwu_window_types = [
            'Holzfenster, zweifach',
            'Kunststofffenster, Isolierverglasung',
            'Alu- oder Stahlfenster, Isolierverglasung',
            'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach',
            'Waermeschutzverglasung, dreifach'
        ]

        if construction_type == 'window' and any(
                type_name in data_source for type_name in iwu_window_types):
            return Path('TypeElements_IWU.json')

        for source, filename in source_to_file.items():
            if source in data_source.lower():
                return Path(filename)

        raise ValueError(
            f"Unknown {construction_type} construction class: {data_source}")

    @staticmethod
    def get_element_template(element_type: str, year_of_construction: int,
                             years_dict: dict, construction_data: str,
                             logger: logging.Logger) -> dict:
        """Retrieves the template for a specific building element based on construction year.

        Args:
            element_type: Type of building element
            year_of_construction: Year when the building was constructed
            years_dict: Dictionary containing templates for different year ranges
            construction_data: Construction data identifier
            logger: Logger instance for warnings

        Returns:
            dict: Template for the specified building element
        """
        # Handle single template case
        if len(years_dict) == 1:
            template_options = years_dict[list(years_dict.keys())[0]]
            if len(template_options) == 1:
                return template_options[list(template_options.keys())[0]]
            return template_options[construction_data]

        # Find template for specific year range
        template_options = None
        for year_range, template in years_dict.items():
            years = ast.literal_eval(year_range)
            if years[0] <= year_of_construction <= years[1]:
                template_options = template
                break

        if not template_options:
            return None

        if len(template_options) == 1:
            return template_options[list(template_options.keys())[0]]

        # Special handling for windows
        if element_type == 'Window':
            try:
                return template_options[construction_data]
            except KeyError:
                # Fallback to last available window type
                new_construction_data = list(template_options.keys())[-1]
                logger.warning(
                    f"The window_construction_data {construction_data} is not "
                    f"available for year_of_construction {year_of_construction}. "
                    f"Using {new_construction_data} instead.")
                return template_options[new_construction_data]

        return template_options[construction_data]

    def get_templates_for_buildings(
            self, buildings: List,
            sim_settings: 'BuildingSimSettings') -> Dict:
        """Generate templates for building elements based on construction year.

        Args:
            buildings: List of building objects to process
            sim_settings: Settings object containing construction parameters

        Returns:
            Dict: Mapping of buildings to their construction templates

        Raises:
            ValueError: If no buildings are provided
        """
        if not buildings:
            raise ValueError(
                "No buildings found, without a building no template can be "
                "assigned and enrichment can't proceed.")

        templates = {}
        for building in buildings:
            # Handle construction year
            if sim_settings.year_of_construction_overwrite:
                building.year_of_construction = int(
                    sim_settings.year_of_construction_overwrite)
            if not building.year_of_construction:
                year_decision = building.request('year_of_construction')
                yield DecisionBunch([year_decision])

            year_of_construction = int(building.year_of_construction.m)

            # Get construction data files
            construction_files = self.ConstructionTemplate(
                walls=self.determine_construction_data_file(
                    'wall', sim_settings.construction_class_walls),
                windows=self.determine_construction_data_file(
                    'window', sim_settings.construction_class_windows),
                doors=self.determine_construction_data_file(
                    'door', sim_settings.construction_class_doors)
            )

            # Load element templates
            element_templates = {
                'walls': get_type_building_elements(construction_files.walls),
                'windows': get_type_building_elements(
                    construction_files.windows),
                'doors': get_type_building_elements(construction_files.doors)
            }

            # Build template for current building
            bldg_template = {}
            for element_type, years_dict in element_templates[
                'windows'].items():
                if element_type == 'Window':
                    bldg_template[element_type] = self.get_element_template(
                        element_type, year_of_construction, years_dict,
                        sim_settings.construction_class_windows, self.logger)

            for element_type, years_dict in element_templates['doors'].items():
                if element_type == 'Door':
                    bldg_template[element_type] = self.get_element_template(
                        element_type, year_of_construction, years_dict,
                        sim_settings.construction_class_doors, self.logger)

            for element_type, years_dict in element_templates['walls'].items():
                if element_type not in ('Window', 'Door'):
                    bldg_template[element_type] = self.get_element_template(
                        element_type, year_of_construction, years_dict,
                        sim_settings.construction_class_walls, self.logger)

            templates[building] = bldg_template

        return templates
