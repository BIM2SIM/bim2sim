"""
Thermal Zone Visualization Module
=================================

This module provides functionality to visualize thermal zones and save the
output as an image. It includes functions to convert RGB values to
OCC-compatible colors and to generate visualizations of thermal zones grouped
by various criteria.

Example:
    For an example, please see e4_visualize_zone_binding.py in PluginTEASER.

Functions:
    rgb_color(rgb): Returns an OCC viewer compatible color quantity based on
    r,g,b values.
    visualize_zones(zone_dict, folder_structure): Visualizes the thermal
    zones and saves the picture as a .png.

Notes:
    Any additional information about the module, its purpose, and its usage
    can be included here.
"""
import logging
from pathlib import Path
from typing import Union

import numpy as np
import ifcopenshell.geom
from OCC.Display.SimpleGui import init_display
from OCC.Core.Quantity import Quantity_Color, Quantity_TOC_RGB
from PIL import Image, ImageDraw

from bim2sim.elements.aggregation.bps_aggregations import AggregatedThermalZone
from bim2sim.elements.bps_elements import ThermalZone

logger = logging.getLogger(__name__)


def rgb_color(rgb) -> Quantity_Color:
    """Returns a OCC viewer compatible color quantity based on r,g,b values.

    Args:
         rgb: must be a tuple with 3 values [0,1]. e.g. (0, 0.5, 0.7)

    Returns:
        Quantity_Color object which is compatible with with the OCC viewer.
    """
    return Quantity_Color(rgb[0], rgb[1], rgb[2], Quantity_TOC_RGB)


def visualize_zones(
        thermal_zones: list[ThermalZone],
        path: Path,
        filename: Union[str, None] = None):
    """Visualizes the ThermalZone element entities and saves the picture as
    a .png. Fetches the ThermalZone which are grouped before and creates an
    abstract building image, where each grouped zone has its own color.
    Afterwards, a legend is added with zone names and corresponding colors.
    The file is exported as .png to the export folder.

    Args:
        thermal_zones: list of ThermalZone and AggregatedThermalZone instances
        path: pathlib Path where image is exported to
        filename: str of filename

    Returns:
        No return value, image is saved directly.
    """
    settings = ifcopenshell.geom.settings()
    settings.set(settings.USE_PYTHON_OPENCASCADE, True)
    settings.set(settings.USE_WORLD_COORDS, True)
    settings.set(settings.EXCLUDE_SOLIDS_AND_SURFACES, False)
    settings.set(settings.INCLUDE_CURVES, True)

    # Call init_display
    # TODO this messes with the logger, but method like below doesn't work
    #  with open(os.devnull, 'w') as devnull:
    display, start_display, add_menu, add_function_to_menu = init_display(
        display_triedron=False, background_gradient_color1=3 * [255],
        background_gradient_color2=3 * [255], size=(1920, 1080))

    fixed_colors = [
        (255, 255, 0),  # Yellow
        (255, 0, 0),  # Red
        (0, 255, 0),  # Green
        (0, 0, 255),  # Blue
        (255, 165, 0),  # Orange
        (128, 0, 128),  # Purple
        (0, 255, 255),  # Cyan
        (255, 192, 203),  # Pink
        (128, 128, 0),  # Olive
        (0, 128, 128),  # Teal
        (192, 192, 192),  # Silver
        (255, 255, 255),  # White
        (0, 0, 0),  # Black
        (165, 42, 42),  # Brown
        (255, 20, 147),  # Deep Pink
        (0, 100, 0),  # Dark Green
        (255, 105, 180),  # Hot Pink
        (75, 0, 130),     # Indigo
        (255, 69, 0),     # Red-Orange
        (100, 149, 237),  # Cornflower Blue
        (34, 139, 34)     # Forest Green
    ]

    legend = {}
    num = 1
    # if len(thermal_zones) > len (fixed_colors):

    for i, tz in enumerate(thermal_zones):
        name = tz.name
        # rgb_tuple = tuple((np.random.choice(range(256), size=3)))
        rgb_tuple = fixed_colors[i]
        rgb_tuple_norm = tuple([round(x / 256, 2) for x in rgb_tuple])
        if name in list(legend.keys()):
            name = name + ' ' + str(num)
            num += 1
        legend[name] = rgb_tuple
        color = rgb_color(rgb_tuple_norm)
        # handle AggregatedThermalZone
        if isinstance(tz, AggregatedThermalZone):
            zones = tz.elements
            for zone in zones:

                display.DisplayShape(zone.space_shape, update=True,
                                     color=color, transparency=0.6,
                                     )
        # handle normal ThermalZone
        else:
            display.DisplayShape(tz.space_shape, update=True,
                                 color=color, transparency=0.6,
                                 )
    sorted_legend = {}
    for k in sorted(legend, key=len, reverse=False):
        sorted_legend[k] = legend[k]

    nr_zones = len(thermal_zones)
    if not filename:
        filename = f"zoning_visualization_{str(nr_zones)}_zones.png"

    save_path = Path(path / filename)
    display.View.Dump(str(save_path))

    text_size = 25
    zone_image = Image.open(save_path)
    image_editable = ImageDraw.Draw(zone_image)
    zone_image_size_y = zone_image.size[1]

    rec_size = 20
    space = 30
    buffer = 10

    legend_height = len(sorted_legend) * (text_size + space / 3) + buffer
    x0 = 0
    rec_to_text_spacing = 10
    y0 = zone_image_size_y - legend_height

    for zone_name, color in sorted_legend.items():
        xy = [(x0 + rec_to_text_spacing, y0),
              (x0 + + rec_to_text_spacing + rec_size, y0 + rec_size)]
        image_editable.rectangle(xy, fill=color, outline=None, width=text_size)
        image_editable.text(
            (x0 + rec_to_text_spacing + rec_size + 10, y0), zone_name,
            (0, 0, 0))
        y0 += space

    zone_image.save(save_path)
    logger.info(f"Exported visualization of combined ThermalZone instances to "
                f"{save_path}.")


def visualize_zones_with_sbs(
        thermal_zones: list[ThermalZone],
        path: Path,
        filename: Union[str, None] = None,
        with_legend=True,
        size=(1024, 768),
):
    """Visualizes the ThermalZone element entities and saves the picture as
    a .png. Fetches the ThermalZone which are grouped before and creates an
    abstract building image, where each grouped zone has its own color.
    Afterwards, a legend is added with zone names and corresponding colors.
    The file is exported as .png to the export folder.

    Args:
        thermal_zones: list of ThermalZone and AggregatedThermalZone instances
        path: pathlib Path where image is exported to
        filename: str of filename

    Returns:
        No return value, image is saved directly.
    """
    settings = ifcopenshell.geom.settings()
    settings.set(settings.USE_PYTHON_OPENCASCADE, True)
    settings.set(settings.USE_WORLD_COORDS, True)
    settings.set(settings.EXCLUDE_SOLIDS_AND_SURFACES, False)
    settings.set(settings.INCLUDE_CURVES, True)

    # Call init_display
    # TODO this messes with the logger, but method like below doesn't work
    #  with open(os.devnull, 'w') as devnull:
    display, start_display, add_menu, add_function_to_menu = init_display(
        display_triedron=False, background_gradient_color1=3 * [255],
        background_gradient_color2=3 * [255]
        , size=size
    )

    fixed_colors = [
        (255, 255, 0),  # Yellow
        (255, 0, 0),  # Red
        (0, 255, 0),  # Green
        (0, 0, 255),  # Blue
        (255, 165, 0),  # Orange
        (128, 0, 128),  # Purple
        (0, 255, 255),  # Cyan
        (255, 192, 203),  # Pink
        (128, 128, 0),  # Olive
        (0, 128, 128),  # Teal
        (0, 0, 0),  # Black
        (165, 42, 42),  # Brown
        (255, 20, 147),  # Deep Pink
        (0, 100, 0),  # Dark Green
        (255, 105, 180),  # Hot Pink
        (75, 0, 130),     # Indigo
        (255, 69, 0),     # Red-Orange
        (100, 149, 237),  # Cornflower Blue
        (34, 139, 34),     # Forest Green
        (192, 192, 192),  # Silver
        (255, 255, 255),  # White
    ]

    legend = {}
    num = 1
    if len(thermal_zones) == 2:
        fixed_colors[0], fixed_colors[1] = fixed_colors[1], fixed_colors[0]
    transparency_external = 0.75
    sb_color = 'black'
    for i, tz in enumerate(thermal_zones):
        name = tz.name
        # rgb_tuple = tuple((np.random.choice(range(256), size=3)))
        rgb_tuple = fixed_colors[i]
        rgb_tuple_norm = tuple([round(x / 256, 2) for x in rgb_tuple])
        if name in list(legend.keys()):
            name = name + ' ' + str(num)
            num += 1
        legend[name] = rgb_tuple
        color = rgb_color(rgb_tuple_norm)


        # handle normal ThermalZone
        if not isinstance(tz, AggregatedThermalZone):
            if tz.is_external:
                transparency = transparency_external
            else:
                transparency = 0.0
            display.DisplayShape(tz.space_shape,
                                 color=color, transparency=transparency,
                                 )
            for sb in tz.space_boundaries:
                # if not (sb.ifc.RelatedBuildingElement.is_a(
                #         'IfcWall') or sb.ifc.RelatedBuildingElement.is_a(
                #     'IfcSlab')):
                #     continue
                if sb.ifc.InternalOrExternalBoundary == 'EXTERNAL':
                    transparency = 0.95
                    display.DisplayShape(sb.bound_shape, color=sb_color,
                                         transparency=transparency, )
        # handle AggregatedThermalZone
        else:
            zones = tz.elements
            for zone in zones:
                if zone.is_external:
                    transparency = transparency_external
                else:
                    transparency = 0.0
                display.DisplayShape(zone.space_shape,
                                     color=color, transparency=transparency,
                                     )
                for sb in zone.space_boundaries:
                    # if not (sb.ifc.RelatedBuildingElement.is_a(
                    #         'IfcWall') or sb.ifc.RelatedBuildingElement.is_a(
                    #     'IfcSlab')):
                    #     continue
                    if sb.ifc.InternalOrExternalBoundary == 'EXTERNAL':
                        transparency = 0.95
                        display.DisplayShape(sb.bound_shape, color=sb_color,
                                             transparency=transparency, )

    display.FitAll()
    nr_zones = len(thermal_zones)
    if not filename:
        filename = f"zoning_visualization_{str(nr_zones)}_zones.png"

    save_path = Path(path / filename)
    display.View.Dump(str(save_path))
    if with_legend:
        sorted_legend = {}
        for k in sorted(legend, key=len, reverse=False):
            sorted_legend[k] = legend[k]
        text_size = 25
        zone_image = Image.open(save_path)
        image_editable = ImageDraw.Draw(zone_image)
        zone_image_size_y = zone_image.size[1]

        rec_size = 20
        space = 30
        buffer = 10

        legend_height = len(sorted_legend) * (text_size + space / 3) + buffer
        x0 = 0
        rec_to_text_spacing = 10
        y0 = zone_image_size_y - legend_height

        for zone_name, color in sorted_legend.items():
            xy = [(x0 + rec_to_text_spacing, y0),
                  (x0 + + rec_to_text_spacing + rec_size, y0 + rec_size)]
            image_editable.rectangle(xy, fill=color, outline=None, width=text_size)
            image_editable.text(
                (x0 + rec_to_text_spacing + rec_size + 10, y0), zone_name,
                (0, 0, 0))
            y0 += space

        zone_image.save(save_path)
    logger.info(f"Exported visualization of combined ThermalZone instances to "
                f"{save_path}.")
