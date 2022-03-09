from random import uniform
from pathlib import Path

import ifcopenshell.geom
from OCC.Display.SimpleGui import init_display
from OCC.Display.OCCViewer import get_color_from_name
from OCC.Core.Quantity import Quantity_Color, Quantity_TOC_RGB
from PIL import Image, ImageFont, ImageDraw


def rgb_color(rgb):
    """ r,g,b must be a tuple with 3 values [0,1]. e.g. (0, 0.5, 0.7)"""
    return Quantity_Color(rgb[0], rgb[1], rgb[2], Quantity_TOC_RGB)


def visualize_zones(zone_dict, export_path):
    """
    Args:
        zone_dict: dict that has a grouping string as key and list of zones as
         values.
    """
    settings = ifcopenshell.geom.settings()
    settings.set(settings.USE_PYTHON_OPENCASCADE, True)
    settings.set(settings.USE_WORLD_COORDS, True)
    settings.set(settings.EXCLUDE_SOLIDS_AND_SURFACES, False)
    settings.set(settings.INCLUDE_CURVES, True)

    display, start_display, add_menu, add_function_to_menu = init_display(
        display_triedron=False, background_gradient_color1=3 * [255],
        background_gradient_color2=3 * [255])

    # todo multi storage floor plan where all floors are placed
    #  next to each other

    legend = {}
    for i, (name, zones) in enumerate(zone_dict.items()):
        # todo dja clarify where 'internal_' comes from and if its robust
        if "internal_" in name:
            rgb_tuple = (
            uniform(0.0, 1.0), uniform(0.0, 1.0), uniform(0.0, 1.0))
            usage = name.split('internal_')[-1]
            if usage.endswith('_'):
                usage = usage[0:-1]
            legend[usage+'*'] = tuple([int(255*x) for x in rgb_tuple])
            for zone in zones:
                display.DisplayShape(zone.space_shape, update=True,
                                     color=rgb_color(rgb_tuple),
                                     transparency=0.5)
        else:
            for zone in zones:
                rgb_tuple = (
                uniform(0.0, 1.0), uniform(0.0, 1.0), uniform(0.0, 1.0))
                legend[zone.usage] = tuple([int(255*x) for x in rgb_tuple])
                display.DisplayShape(zone.space_shape, update=True,
                                     color=rgb_color(rgb_tuple),
                                     transparency=0.5)
    nr_zones = len(zone_dict)
    filename = 'zonemodel_' + str(nr_zones) + '.png'

    save_path = Path(export_path / filename)
    display.View.Dump(str(save_path))

    title_font = ImageFont.truetype(str(Path('D:/01_Kurzablage/arial.ttf')), 20)
    zone_image = Image.open(save_path)
    image_editable = ImageDraw.Draw(zone_image)
    text_size = 20
    zone_image_size_y = zone_image.size[1]

    rec_size = 20
    space = 30
    buffer = 10

    legend_height = len(zone_dict) * (text_size + space) + buffer
    x0 = 0
    rec_to_text_spacing = 10
    y0 = zone_image_size_y - legend_height
    xy_legend_corners = [(x0, y0-5), (x0 + 500, zone_image_size_y-3)]
    image_editable.rectangle(xy_legend_corners, fill=None, outline=(0, 0, 0),
                             width=2)

    for zone_name, color in legend.items():
        xy = [(x0 + rec_to_text_spacing, y0),
              (x0 + + rec_to_text_spacing + rec_size, y0 + rec_size)]
        image_editable.rectangle(xy, fill=color, outline=None, width=text_size)
        image_editable.text((x0 + rec_to_text_spacing + rec_size + 10, y0), zone_name, (0, 0, 0), font=title_font)
        y0 += space

    zone_image.save(Path('D:/01_Kurzablage/zonemodel_7_edited.png'))
