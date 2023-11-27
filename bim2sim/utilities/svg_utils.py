import os
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.etree.ElementTree import Element, ElementTree

import ifcopenshell.geom

from bim2sim.kernel.ifc_file import IfcFileClass

est_time = 10
aggregate_model = True


def create_svg_floor_plan_plot(
        ifc_file_class_inst: IfcFileClass,
        target_path: Path,
        svg_adjust_dict:dict):
    """Creates an SVG floor plan plot for every storey and adjust its design.

    This function first creates an SVG floor plan for the provided IFC file
    based on IfcConvert, then it splits the SVG floor plan into one file per
    storey. In the last step the floor plans for each storey can be adjusted
    regarding their background color and the text. This is useful to create a
    heatmap that e.g. shows the highest temperature in the specific room
    and colorize the rooms based on the data.

    Args:
        svg_adjust_dict: nexted dict that holds guid of storey, spaces and the
        attributes for "color" and "text" to overwrite existing data in the
        floor plan. See example for more information
        ifc_file_class_inst: bim2sim IfcFileClass instance
        target_path: Path to store the SVG files

    Example:
        # create nested dict, where "2eyxpyOx95m90jmsXLOuR0" is the storey guid
        # and "0Lt8gR_E9ESeGH5uY_g9e9", "17JZcMFrf5tOftUTidA0d3" and
        path_to_ifc_file = Path("my_path_to_ifc_folder/AC20-FZK-Haus.ifc")
        ifc_file_instance = ifcopenshell.open(path_to_ifc_file)
        target_path = Path("my_target_path")

        svg_adjust_dict = {
            "2eyxpyOx95m90jmsXLOuR0": {
                "0Lt8gR_E9ESeGH5uY_g9e9": {
                    "color": "#FF0000",
                    "text": 'my_text'
                },
                "17JZcMFrf5tOftUTidA0d3": {
                    "color": "#FF0000",
                    "text": 'my_text2'
                },
                "2RSCzLOBz4FAK$_wE8VckM": {
                    "color": "#FF0000",
                    "text": 'my_text3'
                },
            }
        }
        create_svg_floor_plan_plot(
            path_to_ifc_file, target_path, svg_adjust_dict)
    """
    svg_path = convert_ifc_to_svg(ifc_file_class_inst, target_path)
    split_svg_by_storeys(svg_path)
    modify_svg_elements(svg_adjust_dict, target_path)


def convert_ifc_to_svg(ifc_file_instance: IfcFileClass,
                       target_path: Path) -> Path:
    """Create an SVG floor plan based on the given IFC file using IfcConvert"""
    settings = ifcopenshell.geom.settings(
        INCLUDE_CURVES=True,
        EXCLUDE_SOLIDS_AND_SURFACES=False,
        APPLY_DEFAULT_MATERIALS=True,
        DISABLE_TRIANGULATION=True
    )
    svg_file_name = ifc_file_instance.ifc_file_name[:-4] + '.svg'
    svg_target_path = target_path / svg_file_name

    sr = ifcopenshell.geom.serializers.svg(
        str(svg_target_path), settings)

    file = ifc_file_instance.file
    sr.setFile(file)
    sr.setSectionHeightsFromStoreys()

    sr.setDrawDoorArcs(True)
    sr.setPrintSpaceAreas(True)
    sr.setPrintSpaceNames(True)
    sr.setBoundingRectangle(1024., 1024.)

    sr.writeHeader()

    for progress, elem in ifcopenshell.geom.iterate(
            settings,
            file,
            with_progress=True,
            exclude=("IfcOpeningElement", "IfcStair"),
            num_threads=8
    ):
        sr.write(elem)

    sr.finalize()

    return svg_target_path


def split_svg_by_storeys(svg: Path):
    """Splits the SVG of one building into single SVGs for each storey."""
    with open(svg) as svg_file:
        svg_data = svg_file.read()

    file_dir = Path(os.path.dirname(svg))
    # Namespace-Präfixe definieren
    namespaces = {
        "svg": "http://www.w3.org/2000/svg",
        "xmlns:xlink": "http://www.w3.org/1999/xlink"
    }
    #
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
    # create SVG-ElementTree
    tree = ET.ElementTree(ET.fromstring(svg_data))

    # extract the <style>-Element from the original SVG
    style_element = tree.find(".//svg:style", namespaces)

    # iterate over 'IfcBuildingStorey'-elements
    for building_storey in tree.findall(
            ".//svg:g[@class='IfcBuildingStorey']", namespaces):
        # create new element for each 'IfcBuildingStorey'-element
        svg_element = Element("svg", attrib=building_storey.attrib)

        # add <style>-element to new SVG
        if style_element is not None:
            svg_element.append(style_element)

        # add  'IfcBuildingStorey'-elemente to new SVG
        svg_element.append(building_storey)

        # store new SVG
        storey_guid = building_storey.get("data-guid")
        with open(f"{file_dir}/{storey_guid}.svg", "wb") as f:
            # use a custom Serializer, to prevent 'ns0'-prefix
            ElementTree(svg_element).write(f, encoding="utf-8",
                                           xml_declaration=True)


def modify_svg_elements(svg_adjust_dict: dict, path: Path):
    """Adjusts SVG floor plan for based on input data.

    Based on the inputs, you can colorize the different spaces in the SVG
    and/or add text to the space for each storey. The input is a nested
    dictionary that holds the relevant data.

    Args:
        svg_adjust_dict: nexted dict that holds guid of storey, spaces and the
        attributes for "color" and "text" to overwrite existing data in the
        floor plan.
        path: Path where the basic SVG files are stored.
    """
    # namespace
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
    ns = {'svg': 'http://www.w3.org/2000/svg'}

    for storey_guid, spaces_data in svg_adjust_dict.items():
        # get file path for SVG file
        file_path = Path(f"{path}/{storey_guid}.svg")
        tree = ET.parse(file_path)
        root = tree.getroot()
        for space_guid, adjust_data in spaces_data.items():
            color = adjust_data['color']
            text = adjust_data['text']
            path_elements = root.findall(
                f".//svg:g[@data-guid='{space_guid}']/svg:path",
                namespaces=ns)
            if path_elements is not None:
                for path_element in path_elements:
                    if path_element is not None:
                        path_element.set(
                            'style', f'fill: {color};')

            text_elements = root.findall(
                f".//svg:g[@data-guid='{space_guid}']/svg:text",
                namespaces=ns)
            if text_elements is not None:
                for text_element in text_elements:
                    if text_element is not None:
                        att = text_element.attrib
                        text_element.clear()
                        tspan_element = ET.SubElement(
                            text_element, "tspan")
                        tspan_element.text = text
                        text_element.attrib = att

        tree.write(Path(f"{path}/{storey_guid}_modified.svg"))


def combine_svgs(parent_svg_path, child_svg_path):
    """Combines the content of a child SVG file into a parent SVG file.

    Args:
      parent_svg_path (str): Path to the parent SVG file.
      child_svg_path (str): Path to the child SVG file.

    Returns:
      str: Combined SVG content as a string.
    """
    # Read the contents of the parent SVG file
    with open(parent_svg_path, 'r') as parent_file:
        parent_content = parent_file.read()

    # Read the contents of the child SVG file
    with open(child_svg_path, 'r') as child_file:
        child_content = child_file.read()

    # Parse XML content of parent and child SVG files
    parent_tree = ET.fromstring(parent_content)
    child_tree = ET.fromstring(child_content)

    # Find the <svg> tag in the parent SVG file
    parent_svg = parent_tree.find('.//{http://www.w3.org/2000/svg}svg')

    # Append the child SVG content to the parent SVG
    parent_svg.append(child_tree)

    # Convert the combined SVG content to a string
    merged_svg_content = ET.tostring(parent_tree, encoding='unicode')

    return merged_svg_content

