import os
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.etree.ElementTree import Element, ElementTree

import ifcopenshell.geom

from bim2sim.kernel.ifc_file import IfcFileClass

est_time = 10
aggregate_model = True
logger = logging.getLogger(__name__)


def create_svg_floor_plan_plot(
        ifc_file_class_inst: IfcFileClass,
        target_path: Path,
        svg_adjust_dict: dict,
        result_str: str):
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
        result_str (str): name of the results plotted (used for file naming)

    Example:
        # create nested dict, where "2eyxpyOx95m90jmsXLOuR0" is the storey guid
        # and "0Lt8gR_E9ESeGH5uY_g9e9", "17JZcMFrf5tOftUTidA0d3" and
        path_to_ifc_file = Path("my_path_to_ifc_folder/AC20-FZK-Haus.ifc")
        ifc_file_instance = ifcopenshell.open(path_to_ifc_file)
        target_path = Path("my_target_path")

        svg_adjust_dict = {
            "2eyxpyOx95m90jmsXLOuR0": {
                    {"space_data":
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
                    },
            }
        }
        create_svg_floor_plan_plot(
            path_to_ifc_file, target_path, svg_adjust_dict)
    """
    svg_path = convert_ifc_to_svg(ifc_file_class_inst, target_path)
    split_svg_by_storeys(svg_path)
    modify_svg_elements(svg_adjust_dict, target_path)
    combine_svgs_complete(
        target_path, list(svg_adjust_dict.keys()), result_str)


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
    # sr.setPrintSpaceNames(True)
    sr.setBoundingRectangle(1024., 576.)
    # sr.setScale(1 / 100)
    # sr.setWithoutStoreys(True)
    # sr.setPolygonal(True)
    # sr.setUseNamespace(True)
    # sr.setAlwaysProject(True)
    # sr.setScale(1 / 200)
    # sr.setAutoElevation(False)
    # sr.setAutoSection(True)
    # sr.setPrintSpaceNames(False)
    # sr.setPrintSpaceAreas(False)
    # sr.setDrawDoorArcs(False)
    # sr.setNoCSS(True)
    sr.writeHeader()

    for progress, elem in ifcopenshell.geom.iterate(
            settings,
            file,
            with_progress=True,
            exclude=("IfcOpeningElement", "IfcStair", "IfcSite", "IfcSlab",
                     "IfcMember", "IfcExternalSpatialElement",
                     "IfcBuildingElementProxy"),
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

        # Move element down by 100 pixel
        transform = building_storey.get('transform')
        new_transform = f'translate(0, 100) {transform}' if\
            transform else 'translate(0, 100)'
        building_storey.set('transform', new_transform)

        # store new SVG
        storey_guid = building_storey.get("data-guid")
        with open(f"{file_dir}/{storey_guid}.svg", "wb") as f:
            # use a custom Serializer, to prevent 'ns0'-prefix
            ElementTree(svg_element).write(f, encoding="utf-8",
                                           xml_declaration=True)
    # cleanup: remove original svg as no longer needed
    try:
        svg.unlink()
    except FileNotFoundError:
        logger.warning(
            f"{svg.name} in path {svg.parent} not found and thus "
            f"couldn't be removed.")
    except OSError as e:
        logger.warning(f"Error: {e.filename} - {e.strerror}")


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

    for storey_guid, storey_data in svg_adjust_dict.items():
        spaces_data = storey_data["space_data"]
        # get file path for SVG file
        file_path = Path(f"{path}/{storey_guid}.svg")
        tree = ET.parse(file_path)
        root = tree.getroot()

        # reset opacity to 0.7 for better colors
        namespace = {'svg': 'http://www.w3.org/2000/svg'}
        style_element = root.find('.//svg:style', namespace)
        if style_element is not None:
            # Get the text content of the style element
            style_content = style_element.text

            # Replace the desired style content
            style_content = style_content.replace(
                'fill-opacity: .2;',
                'fill-opacity: 0.7;')

            # Update the text content of the style element
            style_element.text = style_content
        all_space_text_elements = root.findall(
                f'.//svg:g[@class="IfcSpace"]/svg:text',
                namespaces=ns)
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
            # TODO set spacearea and space name to false in convert, store
            #  short space name in tz mapping and then in svg dict, add instead
            #  replace the string of zone name \n consumption here
            text_elements = root.findall(
                f".//svg:g[@data-guid='{space_guid}']/svg:text",
                namespaces=ns)
            if text_elements is not None:
                for text_element in text_elements:
                    all_space_text_elements.remove(text_element)
                    if text_element is not None:
                        att = text_element.attrib
                        text_element.clear()
                        tspan_element = ET.SubElement(
                            text_element, "tspan")
                        style = tspan_element.get('style')
                        if style:
                            style += ";fill:#FFFFFF"
                        else:
                            style = "fill:#FFFFFF"
                        style += ";font-weight:bold"
                        style += ";font-size:22px"
                        tspan_element.set('style', style)
                        tspan_element.text = text
                        text_element.attrib = att

        # for spaces without data add a placeholder
        for text_element in all_space_text_elements:
            if text_element is not None:
                att = text_element.attrib
                text_element.clear()
                tspan_element = ET.SubElement(
                    text_element, "tspan")
                style = tspan_element.get('style')
                if style:
                    style += ";fill:#FFFFFF"
                else:
                    style = "fill:#FFFFFF"
                style += ";font-weight:bold"
                style += ";font-size:22px"
                tspan_element.set('style', style)
                tspan_element.text = "-"
                text_element.attrib = att

        tree.write(Path(f"{path}/{storey_guid}_modified.svg"))


def combine_two_svgs(
        parent_svg_path: Path, child_svg_path: Path):
    """Combines the content of a child SVG file into a parent SVG file.

    Args:
      parent_svg_path (Path): Path to the parent SVG file.
      child_svg_path (Path): Path to the child SVG file.

    Returns:
      str: Combined SVG content as a string.
    """

    ET.register_namespace("", "http://www.w3.org/2000/svg")
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")

    # Read the contents of the parent SVG file
    with open(parent_svg_path, 'r') as parent_file:
        parent_content = parent_file.read()

    # Read the contents of the child SVG file
    with open(child_svg_path, 'r') as child_file:
        child_content = child_file.read()

    svg1_root = ET.fromstring(parent_content)
    svg2_root = ET.fromstring(child_content)

    # extract the <g> element from the child svg
    svg2_g_element = svg2_root.find(".//{http://www.w3.org/2000/svg}g")

    # append the <g> element from the child svg to the parent svg
    svg1_root.append(svg2_g_element)

    # Das aktualisierte XML als String zurückgeben
    combined_svg_string = ET.tostring(svg1_root, encoding="unicode", method="xml")

    return combined_svg_string


def combine_svgs_complete(
        file_path: Path, storey_guids: list, result_str: str) -> None:
    """Add color mapping svg to floor plan svg."""
    for guid in storey_guids:
        original_svg = file_path / f"{guid}.svg"
        svg_file = file_path / f"{guid}_modified.svg"
        color_mapping_file = file_path / f"color_mapping_{guid}.svg"
        new_svg_content = combine_two_svgs(svg_file, color_mapping_file,)
        with open(file_path / f"Floor_plan_{result_str}_{guid}.svg",
                  "w", encoding='utf-8') as f:
            f.write(new_svg_content)
        # cleanup
        for file in [original_svg, svg_file, color_mapping_file]:
            try:
                file.unlink()
            except FileNotFoundError:
                logger.warning(
                    f"{file.name} in path {file.parent} not found and thus "
                    f"couldn't be removed.")
            except OSError as e:
                logger.warning(f"Error: {e.filename} - {e.strerror}")
