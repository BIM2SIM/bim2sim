from pathlib import Path
from typing import List
import re

import ifcopenshell
import numpy as np
from OCC.Core.Quantity import Quantity_Color, Quantity_TOC_RGB
from OCC.Core.TopoDS import TopoDS_Shape
from OCC.Display.SimpleGui import init_display
from PIL import Image, ImageFont, ImageDraw


class VisualizationUtils:

    @staticmethod
    def _display_shape_of_space_boundaries(instances):
        """Display topoDS_shapes of space boundaries"""
        display, start_display, add_menu, add_function_to_menu = init_display()
        colors = ['blue', 'red', 'magenta', 'yellow', 'green', 'white', 'cyan']
        col = 0
        for inst in instances:
            if instances[inst].ifc.is_a('IfcRelSpaceBoundary'):
                col += 1
                bound = instances[inst]
                if bound.bound_instance is None:
                    continue
                if not bound.bound_instance.ifc.is_a("IfcWall"):
                    pass
                try:
                    display.DisplayShape(bound.bound_shape, color=colors[(col - 1) % len(colors)])
                except:
                    continue
        display.FitAll()
        start_display()

    @staticmethod
    def _display_bound_normal_orientation(instances):
        display, start_display, add_menu, add_function_to_menu = init_display()
        col = 0
        for inst in instances:
            if not instances[inst].ifc.is_a('IfcSpace'):
                continue
            space = instances[inst]
            for bound in space.space_boundaries:
                face_towards_center = space.space_center.XYZ() - bound.bound_center
                face_towards_center.Normalize()
                dot = face_towards_center.Dot(bound.bound_normal)
                if dot > 0:
                    display.DisplayShape(bound.bound_shape, color="red")
                else:
                    display.DisplayShape(bound.bound_shape, color="green")
        display.FitAll()
        start_display()

    @staticmethod
    def display_occ_shapes(shapes: List[TopoDS_Shape]):
        """Display topoDS_shapes of space boundaries"""
        display, start_display, add_menu, add_function_to_menu = init_display()
        for shape in shapes:
            try:
                display.DisplayShape(shape)
            except:
                continue
        display.FitAll()
        start_display()

    @staticmethod
    def rgb_color(rgb) -> Quantity_Color:
        """Returns a OCC viewer compatible color quantity based on r,g,b values.
        Args:
             rgb: must be a tuple with 3 values [0,1]. e.g. (0, 0.5, 0.7)
        Returns:
            Quantity_Color object which is compatible with with the OCC viewer.
        """
        return Quantity_Color(rgb[0], rgb[1], rgb[2], Quantity_TOC_RGB)

    @staticmethod
    def visualize_zones(zone_dict, folder_structure):
        """Visualizes the thermalzones and saves the picture as a .png.
        Fetches the thermalzones which are grouped before and creates an abstract
        building image, where each grouped zone has its own color. Afterwards a
        legend is added with zone names and corresponding colors. The file is
        exported as .png to the export folder.
        Args:
            zone_dict: dict that has a grouping string as key and list of zones as
             values.
            folder_structure: instance of Folderstructure which is assigend to the
             projects attribute self.paths.
        Returns:
            No return value, image is saved directly.
        """
        settings = ifcopenshell.geom.settings()
        settings.set(settings.USE_PYTHON_OPENCASCADE, True)
        settings.set(settings.USE_WORLD_COORDS, True)
        settings.set(settings.EXCLUDE_SOLIDS_AND_SURFACES, False)
        settings.set(settings.INCLUDE_CURVES, True)

        display, start_display, add_menu, add_function_to_menu = init_display(
            display_triedron=False, background_gradient_color1=3 * [255],
            background_gradient_color2=3 * [255], size=(1920, 1080))

        # todo multi storage floor plan where all floors are placed
        #  next to each other

        legend = {}
        num = 1
        for i, (guid, zone) in enumerate(zone_dict.items()):
            rgb_tuple = tuple((np.random.choice(range(256), size=3)))
            rgb_tuple_norm = tuple([x / 256 for x in rgb_tuple])
            name = zone.name
            name = re.findall(
                r'[ A-Z a-z / \u00fc \u00dc \u00d6 \u00f6 \u00c4 \u00e4 \u00df]+|\d+',
                name)[0]
            if name.isdigit:
                name = \
                    zone.usage.split(' (')[0].split('_')[0]
            if name in list(legend.keys()):
                name = name + ' ' + str(num)
                num += 1
            legend[name] = rgb_tuple
            display.DisplayShape(zone.space_shape, update=True,
                                 color=VisualizationUtils.rgb_color(rgb_tuple_norm),
                                 transparency=0.5)
        sorted_legend = {}
        for k in sorted(legend, key=len, reverse=False):
            sorted_legend[k] = legend[k]

        nr_zones = len(zone_dict)
        filename = 'zonemodel_' + str(nr_zones) + '.png'

        save_path = Path(folder_structure.export / filename)
        display.View.Dump(str(save_path))

        text_size = 25
        font_path = folder_structure.assets / 'fonts' / 'arial.ttf'
        title_font = ImageFont.truetype(str(font_path), text_size)
        zone_image = Image.open(save_path)
        image_editable = ImageDraw.Draw(zone_image)
        zone_image_size_y = zone_image.size[1]

        rec_size = 20
        space = 30
        buffer = 10

        legend_height = len(sorted_legend) * (text_size + space/3) + buffer
        x0 = 0
        rec_to_text_spacing = 10
        y0 = zone_image_size_y - legend_height
        # xy_legend_corners = [(x0, y0-5), (x0 + 500, zone_image_size_y-3)]
        # image_editable.rectangle(xy_legend_corners, fill=None, outline=(0, 0, 0),
        #                          width=2)

        for zone_name, color in sorted_legend.items():
            xy = [(x0 + rec_to_text_spacing, y0),
                  (x0 + + rec_to_text_spacing + rec_size, y0 + rec_size)]
            image_editable.rectangle(xy, fill=color, outline=None, width=text_size)
            image_editable.text((x0 + rec_to_text_spacing + rec_size + 10, y0), zone_name, (0, 0, 0), font=title_font)
            y0 += space

        zone_image.save(save_path)
