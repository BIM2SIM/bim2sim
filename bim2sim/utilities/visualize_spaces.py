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

    legend = {}
    num = 1
    for tz in thermal_zones:
        name = tz.name
        rgb_tuple = tuple((np.random.choice(range(256), size=3)))
        rgb_tuple_norm = tuple([round(x / 256, 2) for x in rgb_tuple])
        if name in list(legend.keys()):
            name = name + ' ' + str(num)
            num += 1
        legend[name] = rgb_tuple
        color = rgb_color(rgb_tuple_norm)
        # handle AggregatedThermalZone
        if hasattr(tz, "elements"):
            zones = tz.elements
            for zone in zones:
                display.DisplayShape(zone.space_shape, update=True,
                                     color=color, transparency=0.5)
        # handle normal ThermalZone
        else:
            display.DisplayShape(tz.space_shape, update=True,
                                 color=color, transparency=0.5)
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
