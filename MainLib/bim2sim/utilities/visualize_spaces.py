from random import randrange
from pathlib import Path

import ifcopenshell.geom
from OCC.Display.SimpleGui import init_display
from OCC.Display.OCCViewer import get_color_from_name


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

    color_bg = get_color_from_name('White')
    display, start_display, add_menu, add_function_to_menu = init_display(
        display_triedron=False, background_gradient_color1=3 * [255],
        background_gradient_color2=3 * [255])

    # color numbers coming from to OCC.Core.Quantity.py
    predefined_col = [78, 422, 106, 318, 250, 489, 469, 314, 417, 444, 473, 102]
    if len(zone_dict.items()) > len(predefined_col):
        # create random color list
        col = []
        for x in range(0, len(zone_dict.items())):
            col.append(randrange(0, 516))
    else:
        # use predifined colors
        col = predefined_col
    for i, (name, zones) in enumerate(zone_dict.items()):
        for tz in zones:
            display.DisplayShape(tz.space_shape, update=True, color=col[i],
                                 transparency=0.5)
    nr_zones = len(zone_dict)
    filename = 'zonemodel_'+ str(nr_zones) +'.png'

    save_path = Path(export_path / filename)
    display.View.Dump(str(save_path))
