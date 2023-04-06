import colorsys
from pathlib import Path
from typing import List
import re

import ifcopenshell
import ifcopenshell.geom
import numpy as np
import pandas as pd
from OCC.Core.BRepGProp import BRepGProp_Face
from OCC.Core.Quantity import Quantity_Color, Quantity_TOC_RGB
from OCC.Core.TopAbs import TopAbs_FACE
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopoDS import TopoDS_Shape, topods
from OCC.Core.gp import gp_Vec, gp_Pnt
from OCC.Display.SimpleGui import init_display
from PIL import Image, ImageFont, ImageDraw

from bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus.utils import \
    PostprocessingUtils
from bim2sim.utilities import pyocc_tools
from bim2sim.utilities.pyocc_tools import PyOCCTools


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
                    display.DisplayShape(bound.bound_shape,
                                         color=colors[(col - 1) % len(colors)])
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
                face_towards_center = space.space_center.XYZ() - \
                                      bound.bound_center
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
        """Returns a OCC viewer compatible color quantity based on r,g,
        b values.
        Args:
             rgb: must be a tuple with 3 values [0,1]. e.g. (0, 0.5, 0.7)
        Returns:
            Quantity_Color object which is compatible with with the OCC viewer.
        """
        return Quantity_Color(rgb[0], rgb[1], rgb[2], Quantity_TOC_RGB)

    @staticmethod
    def rgb(minimum, maximum, value):
        minimum, maximum = float(minimum), float(maximum)
        # ratio = 2 * (value-minimum) / (maximum - minimum)
        ratio = 2 * (value - minimum) / (maximum - minimum)
        r = int(max(0, 255 * (1 - ratio))) / 255
        # r = int(max(0, abs(255*(ratio - 1))))/255
        # g = int(max(0, (255 - b - r)/255))
        b = int(max(0, abs(255 * (ratio - 1)))) / 255
        # g = int((255 - b - r)/255)
        g = 1
        return (r, g, b)

    @staticmethod
    def interpolate_to_rgb(minimum, maximum, value, color_min=0,
                           color_max=360):
        s = 1
        l = 0.55
        h = (color_min + (color_max - color_min) / (maximum - minimum) * (
                value - minimum)) / 360
        r, g, b = colorsys.hls_to_rgb(h, l, s)

        return r, g, b

    @staticmethod
    def visualize_zones(zone_dict, folder_structure):
        """Visualizes the thermalzones and saves the picture as a .png.
        Fetches the thermalzones which are grouped before and creates an
        abstract
        building image, where each grouped zone has its own color. Afterwards a
        legend is added with zone names and corresponding colors. The file is
        exported as .png to the export folder.
        Args:
            zone_dict: dict that has a grouping string as key and list of
            zones as
             values.
            folder_structure: instance of Folderstructure which is assigend
            to the
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
        csv_name = folder_structure.export / 'EP-results/eplusout.csv'
        res_df = pd.read_csv(csv_name)
        # extract zone ideal loads zone sensible
        full_key_sens_cool_rate = ' IDEAL LOADS AIR SYSTEM:Zone Ideal Loads ' \
                                  'Zone Sensible Cooling Rate [W](Hourly)'
        # extract the columns holding the zone sensible heating rates
        full_key_sens_heat_rate = ' IDEAL LOADS AIR SYSTEM:Zone Ideal Loads ' \
                                  'Zone Sensible Heating Rate [W](Hourly)'
        zone_sensible_heating_rate = PostprocessingUtils._extract_cols_from_df(
            res_df, full_key_sens_heat_rate)
        # rename column name to zone guid
        zone_sensible_heating_rate.columns = [
            col.replace(full_key_sens_heat_rate, '') for col in
            zone_sensible_heating_rate.columns]
        # get maximum sensible heating rate per zone
        max_zone_sens_heat_rate = zone_sensible_heating_rate.max()
        # fill new dict with key: guid and value :zone net area
        area_dict = {}
        for i, (guid, zone) in enumerate(zone_dict.items()):
            area_dict[guid.upper()] = zone.net_area.m
        # add zone net heat area to maximum heat area dataframe
        max_heat_rate_df = pd.DataFrame(max_zone_sens_heat_rate,
                                        columns=['max_zone_sens_heat_rate'])
        max_heat_rate_df['net_area'] = pd.DataFrame.from_dict(area_dict,
                                                              orient='index')
        # compute maximum sensible heat rate per zone area (normalization)
        max_heat_rate_df['max_per_area'] = \
            max_heat_rate_df['max_zone_sens_heat_rate'] / max_heat_rate_df[
                'net_area']

        # add colored 3D plot of space geometry
        minimum = 0
        maximum = max_heat_rate_df['max_per_area'].max()

        for i, (guid, zone) in enumerate(zone_dict.items()):
            current_value = max_heat_rate_df['max_per_area'].loc[guid.upper()]
            color = VisualizationUtils.rgb_color(
                VisualizationUtils.interpolate_to_rgb(minimum, maximum,
                                                      current_value))
            display.DisplayShape(zone.space_shape, update=True, color=color,
                                 transparency=0.5)
        nr_zones = len(zone_dict)
        filename = 'zonemodel_' + str(nr_zones) + '.png'

        save_path = Path(folder_structure.export / filename)
        display.View.Dump(str(save_path))

        # add floorplan
        floorplan_dict = {}

        for i, (guid, zone) in enumerate(zone_dict.items()):
            footprint = []
            shape = ifcopenshell.geom.create_shape(settings,
                                                   zone.ifc).geometry
            exp = TopExp_Explorer(shape, TopAbs_FACE)

            while exp.More():
                face = topods.Face(exp.Current())
                prop = BRepGProp_Face(face)
                p = gp_Pnt()
                normal_direction = gp_Vec()
                prop.Normal(0.,0., p, normal_direction)
                if abs(1. - normal_direction.Z()) < 1.e-5:
                    display.DisplayShape(face)
                    footprint.append(face)
                exp.Next()
            floorplan_dict[guid.upper()] = footprint
        # display.FitAll()
        # ifcopenshell.geom.utils.main_loop()

        display, start_display, add_menu, add_function_to_menu = init_display(
            display_triedron=False, background_gradient_color1=3 * [255],
            background_gradient_color2=3 * [255], size=(1920, 1080))
        for i, (guid, shapes) in enumerate(floorplan_dict.items()):
            current_value = max_heat_rate_df['max_per_area'].loc[guid.upper()]
            color = VisualizationUtils.rgb_color(
            VisualizationUtils.interpolate_to_rgb(minimum, maximum,
                                                  current_value))
            for shape in shapes:
                display.DisplayShape(shape, update=True, color=color)
                # todo: display message only in center of largest shape in zone
                display.DisplayMessage(PyOCCTools._get_center_of_face(
                    shape), str(round(current_value,2))+' W/m2',
                    message_color=(0,0,0))
        display.FitAll()
        display.View.Dump(str(str(save_path).strip('.png') + '_floorplan.png'))
        # todo: add legend to floorplan.


        # add legend to 3D image
        im = Image.open(save_path)
        text_size = 25
        draw = ImageDraw.Draw(im)
        font_path = folder_structure.assets / 'fonts' / 'arial.ttf'
        text_color = (0, 0, 0)
        title_font = ImageFont.truetype(str(font_path), text_size)
        blind_counter = 0
        legend_height = 800
        im_width, im_heigth = im.size
        line_width = int(legend_height / maximum)
        title = 'Maximum sensible heating rate per area'
        unit = 'W/m²'
        xmin = 20
        xmax = 100
        xbuffer = 20
        ybuffer = 30
        draw.text(((xmax+xmin)/2, 200 - ybuffer), unit, text_color,
                  font=title_font, anchor='ms')
        draw.text((im_width/2, text_size/2 + ybuffer), title, text_color,
                  font=title_font, anchor='ms')
        for i in range(0, int(maximum)):
            color = VisualizationUtils.interpolate_to_rgb(minimum, maximum, i)
            print(i, color)
            color = tuple(tuple([int(color[0] * 255), int(color[1] * 255),
                                 int(color[2] * 255)]))
            draw.line([(xmin, 200 + i * line_width),
                       (xmax, 200 + i * line_width)], color, width=line_width)
            if i == 0:
                draw.text((xmax + xbuffer, 200 + i * line_width), str(i),
                          text_color, font=title_font, anchor='ms')
            if i % int(maximum / 2) == 0:
                blind_counter += 1
                draw.text((xmax + xbuffer, 200 + i * line_width), str(i),
                          text_color, font=title_font, anchor='ms')
        draw.text((xmax + xbuffer, 200 + int(maximum) * line_width),
                  str(int(maximum)), text_color, font=title_font, anchor='ms')
        im.save(str(save_path).strip('.png') + '_mod.png')
