import colorsys
from pathlib import Path
from typing import List

import ifcopenshell
import ifcopenshell.geom
import pandas as pd
from OCC.Core.Quantity import Quantity_Color, Quantity_TOC_RGB
from OCC.Core.TopoDS import TopoDS_Shape
from OCC.Core.gp import gp_Pnt
from OCC.Display.SimpleGui import init_display
from PIL import Image, ImageFont, ImageDraw

from bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus.utils import \
    PostprocessingUtils
from bim2sim.utilities.pyocc_tools import PyOCCTools


class VisualizationUtils:

    @staticmethod
    def _display_shape_of_space_boundaries(elements):
        """Display topoDS_shapes of space boundaries"""
        display, start_display, add_menu, add_function_to_menu = init_display()
        colors = ['blue', 'red', 'magenta', 'yellow', 'green', 'white', 'cyan']
        col = 0
        for inst in elements:
            if elements[inst].ifc.is_a('IfcRelSpaceBoundary'):
                col += 1
                bound = elements[inst]
                if bound.bound_element is None:
                    continue
                if not bound.bound_element.ifc.is_a("IfcWall"):
                    pass
                try:
                    display.DisplayShape(bound.bound_shape, color=colors[(col - 1) % len(colors)])
                except:
                    continue
        display.FitAll()
        start_display()

    @staticmethod
    def _display_bound_normal_orientation(elements):
        display, start_display, add_menu, add_function_to_menu = init_display()
        col = 0
        for inst in elements:
            if not elements[inst].ifc.is_a('IfcSpace'):
                continue
            space = elements[inst]
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
        ratio = 2 * (value - minimum) / (maximum - minimum)
        r = int(max(0, 255 * (1 - ratio))) / 255
        b = int(max(0, abs(255 * (ratio - 1)))) / 255
        g = 1
        return (r, g, b)

    @staticmethod
    def interpolate_to_rgb(minimum, maximum, value, color_min=50,
                           color_max=340):
        s = 1
        l = 0.5
        h = (color_min + (color_max - color_min) / (maximum - minimum) * (
                value - minimum)) / 360
        r, g, b = colorsys.hls_to_rgb(h, l, s)

        return r, g, b

    @staticmethod
    def get_column_from_ep_results(csv_name: str, column_key: str) -> \
            pd.DataFrame:
        """
        This function extracts a column per energyplus column_key from a
        dataframe. It removes the full column_key from the column name
        afterwards, such that only the zone identifier (guid) of the column
        name remains as column key.

        Args:
            csv_name: csv name including file name as string
            column_key: full variable key that is removed afterwards from
                    column name. Must not include the zone guid
        Returns:
            df: pandas dataframe
        """
        res_df = pd.read_csv(csv_name)
        # extract data that includes the column_key
        df = PostprocessingUtils._extract_cols_from_df(
            res_df, column_key)
        # rename column name to zone guid (remove column_key from column
        # name and keep guid only)
        df.columns = [
            col.replace(column_key, '') for col in
            df.columns]
        return df

    @staticmethod
    def add_legend(save_path, paths, minimum, maximum, unit,
                   text_size=25, text_color=(0, 0, 0,), legend_height=800,
                   title=None):
        # add legend to 3D image
        im = Image.open(save_path)
        draw = ImageDraw.Draw(im)
        #font_path = folder_structure.assets / 'fonts' / 'arial.ttf'
        #title_font = ImageFont.truetype(str(font_path), text_size)
        blind_counter = 0
        im_width, im_heigth = im.size
        line_width = int(legend_height / maximum)
        xmin = 20
        xmax = 100
        xbuffer = 20
        ybuffer = 30
        draw.text(((xmax+xmin)/2, 200 - ybuffer), unit, text_color,
                  #font=title_font,
                  anchor='ms')
        if title:
            draw.text((im_width/2, text_size/2 + ybuffer), title, text_color,
                      #font=title_font,
                      anchor='ms')
        mid_count = 0
        for i in range(0, int(maximum)):
            color = VisualizationUtils.interpolate_to_rgb(minimum, maximum, i)
            color = tuple(tuple([int(color[0] * 255), int(color[1] * 255),
                                 int(color[2] * 255)]))
            draw.line([(xmin, 200 + i * line_width),
                       (xmax, 200 + i * line_width)], color, width=line_width)
            if i == 0:
                draw.text((xmax + xbuffer, 200 + i * line_width), str(i),
                          text_color, #font=title_font,
                          anchor='ms')
            elif i % (int(maximum / 2)) == 0 and mid_count == 0:
                mid_count += 1
                blind_counter += 1
                draw.text((xmax + xbuffer, 200 + i * line_width), str(i),
                          text_color, #font=title_font,
                          anchor='ms')
        draw.text((xmax + xbuffer, 200 + int(maximum) * line_width),
                  str(int(maximum)), text_color, #font=title_font,
                  anchor='ms')
        im.save(str(save_path).strip('.png') + '_legende.png')

    @staticmethod
    def visualize_zones(zone_dict, export_path, paths):
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

        # todo multi storage floor plan where all floors are placed
        #  next to each other
        csv_name = export_path / 'eplusout.csv'
        full_key_total_heat_rate = ' IDEAL LOADS AIR SYSTEM:Zone Ideal Loads ' \
                                  'Zone Total Heating Rate [W](Hourly)'
        zone_total_heating_rate = \
            VisualizationUtils.get_column_from_ep_results(
            csv_name=csv_name, column_key=full_key_total_heat_rate)
        # get maximum total heating rate per zone
        max_zone_total_heat_rate = zone_total_heating_rate.max()
        # fill new dict with key: guid and value :zone net area
        area_dict = {}
        for i, (guid, zone) in enumerate(zone_dict.items()):
            area_dict[guid.upper()] = zone.net_area.m
        # add zone net heat area to maximum heat area dataframe
        max_heat_rate_df = pd.DataFrame(max_zone_total_heat_rate,
                                        columns=['max_zone_total_heat_rate'])
        max_heat_rate_df['net_area'] = pd.DataFrame.from_dict(area_dict,
                                                              orient='index')
        # compute maximum total heat rate per zone area (normalization)
        max_heat_rate_df['max_per_area'] = \
            max_heat_rate_df['max_zone_total_heat_rate'] / max_heat_rate_df[
                'net_area']

        # add colored 3D plot of space geometry
        minimum = 0
        maximum = max_heat_rate_df['max_per_area'].max()

        settings = ifcopenshell.geom.settings()
        settings.set(settings.USE_PYTHON_OPENCASCADE, True)
        settings.set(settings.USE_WORLD_COORDS, True)
        settings.set(settings.EXCLUDE_SOLIDS_AND_SURFACES, False)
        settings.set(settings.INCLUDE_CURVES, True)

        display, start_display, add_menu, add_function_to_menu = init_display(
            display_triedron=False, background_gradient_color1=3 * [255],
            background_gradient_color2=3 * [255], size=(1920, 1080))

        for i, (guid, zone) in enumerate(zone_dict.items()):
            current_value = max_heat_rate_df['max_per_area'].loc[guid.upper()]
            color = VisualizationUtils.rgb_color(
                VisualizationUtils.interpolate_to_rgb(minimum, maximum,
                                                      current_value))
            display.DisplayShape(zone.space_shape, update=True, color=color,
                                 transparency=0.5)
        nr_zones = len(zone_dict)
        filename = 'zonemodel_' + str(nr_zones) + '.png'

        save_path = Path(export_path / filename)
        display.View.Dump(str(save_path))

        # add floorplan
        floorplan_dict = {}

        for i, (guid, zone) in enumerate(zone_dict.items()):
            floorplan_dict[guid.upper()] = zone.footprint_shape

        storey_list = list(set([zone.storey for i, (guid, zone) in
                                enumerate(zone_dict.items())]))

        for storey in storey_list:
            display, start_display, add_menu, add_function_to_menu = \
                init_display(display_triedron=False,
                             background_gradient_color1=3 * [255],
                             background_gradient_color2=3 * [255],
                             size=(1920, 1080))
            for zone in storey.thermal_zones:
                guid = zone.guid
                shape = floorplan_dict.get(guid.upper())
                current_value = max_heat_rate_df['max_per_area'].loc[
                    guid.upper()]
                color = VisualizationUtils.rgb_color(
                    VisualizationUtils.interpolate_to_rgb(minimum, maximum,
                                                          current_value))
                display.DisplayShape(shape, update=True, color=color,
                                     transparency=0)
                center = PyOCCTools.get_center_of_face(shape)
                if not center:
                    center = PyOCCTools.get_center_of_shape(shape)
                display.DisplayMessage(
                     gp_Pnt(center.X(), center.Y(), center.Z() + 1.),
                     str(round(current_value, 2))+' W/m2',
                     message_color=(0, 0, 0))
            display.View_Top()
            display.FitAll()
            this_floorplan_path = str(str(save_path).strip('.png') + storey.name +
                                      '_floorplan.png')
            display.View.Dump(this_floorplan_path)
            VisualizationUtils.add_legend(
                this_floorplan_path, paths, minimum, maximum,
                unit='W/m²'
            )
            #todo: rescale underlying image so that the floorplan does not
            # overlap with legend.

        VisualizationUtils.add_legend(
            save_path, paths, minimum, maximum, unit='W/m²',
            title='Maximum total heating rate per area'
        )
