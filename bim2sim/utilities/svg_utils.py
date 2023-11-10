import os

import ifcopenshell.geom
import xml.etree.ElementTree as ET

from pathlib import Path
from xml.etree.ElementTree import Element, ElementTree
from ifcopenshell import open as ifc_open

est_time = 10
aggregate_model = True


def convert_ifc_to_svg(ifc_file_path: Path) -> Path:
    settings = ifcopenshell.geom.settings(
        INCLUDE_CURVES=True,
        EXCLUDE_SOLIDS_AND_SURFACES=False,
        APPLY_DEFAULT_MATERIALS=True,
        DISABLE_TRIANGULATION=True
    )

    # cache = ifcopenshell.geom.serializers.hdf5("cache.h5", settings)
    # sr = ifcopenshell.geom.serializers.svg(utils.storage_file_for_id(self.id, "svg"), settings)
    ifc_file_dir = Path(os.path.dirname(ifc_file_path))

    filename = ifc_file_path.stem

    file_base = str(ifc_file_dir / filename)

    sr = ifcopenshell.geom.serializers.svg(
        file_base + ".svg", settings)

    # @todo determine file to select here or unify building storeys accross files somehow
    file_path = file_base + ".ifc"

    file = ifc_open(file_path)

    sr.setFile(file)
    # sr.setFile(context.models[context.input_ids[0]])
    sr.setSectionHeightsFromStoreys()

    sr.setDrawDoorArcs(True)
    sr.setPrintSpaceAreas(True)
    sr.setPrintSpaceNames(True)
    sr.setBoundingRectangle(1024., 1024.)

    """
    sr.setProfileThreshold(128)
    sr.setPolygonal(True)
    sr.setAlwaysProject(True)
    sr.setAutoElevation(True)
    """

    # sr.setAutoSection(True)

    sr.writeHeader()

    # for ii in context.input_ids:
    f = file_base + ".ifc"
    # f = context.models[ii]
    for progress, elem in ifcopenshell.geom.iterate(
            settings,
            file,
            with_progress=True,
            exclude=("IfcOpeningElement",),
            # cache=utils.storage_file_for_id(id, "cache.h5"),
            cache=str(
                Path(file_base + ".cache.h5")),
            num_threads=8
    ):
        try:
            sr.write(elem)
        except:
            print("On %s:" % f[elem.id])
            # traceback.print_exc(file=sys.stdout)
        # self.sub_progress(progress)

    sr.finalize()

    return Path(file_base + ".svg")


def split_svg_by_storeys(svg: Path):
    # Deine SVG-Daten hier einfügen
    with open(svg) as svg_file:
        svg_data = svg_file.read()

    file_dir = Path(os.path.dirname(svg))
    # Namespace-Präfixe definieren
    namespaces = {"svg": "http://www.w3.org/2000/svg", "xmlns:xlink": "http://www.w3.org/1999/xlink"}
    #
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
    # SVG-ElementTree erstellen
    tree = ET.ElementTree(ET.fromstring(svg_data))

    # Extrahiere das <style>-Element aus der ursprünglichen SVG
    style_element = tree.find(".//svg:style", namespaces)

    # Iteriere durch alle 'IfcBuildingStorey'-Elemente
    for building_storey in tree.findall(".//svg:g[@class='IfcBuildingStorey']", namespaces):
        # Erstelle ein neues SVG-Dokument für jedes 'IfcBuildingStorey'-Element
        svg_element = Element("svg", attrib=building_storey.attrib)

        # Füge das <style>-Element dem neuen SVG hinzu
        if style_element is not None:
            svg_element.append(style_element)

        # Füge die 'IfcBuildingStorey'-Elemente dem neuen SVG hinzu
        svg_element.append(building_storey)

        # Speichere das neue SVG in einer Datei mit dem Namen des 'data-name'-Attributs
        storey_name = building_storey.get("data-name")
        with open(f"{file_dir}/{storey_name}.svg", "wb") as f:
            # Verwende einen angepassten Serializer, um das 'ns0'-Präfix zu vermeiden
            ElementTree(svg_element).write(f, encoding="utf-8", xml_declaration=True)


if __name__ == "__main__":
    path_to_ifc_file = Path("D:/projects/bim2sim/ifc_files/AC20-FZK-Haus.ifc")

    svg_file_path = convert_ifc_to_svg(path_to_ifc_file)
    split_svg_by_storeys(svg_file_path)
