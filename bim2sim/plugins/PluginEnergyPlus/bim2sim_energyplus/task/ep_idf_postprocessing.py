import json
from pathlib import Path
import pandas as pd
from geomeppy import IDF

from bim2sim.elements.bps_elements import ThermalZone
from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_elements

# — robust GUID→name & TOC fixer for any EP HTML file —
def replace_guids_in_html(report_dir, zone_dict_path):
    """
    Finds whichever .htm contains the “People Internal Gains Nominal” table,
    moves its TOC to the top under <body>, replaces GUIDs in its “Zone Name”
    column (and anywhere they occur) with human-readable labels from zone_dict.json,
    and writes out a new file *_with_names.htm.
    """
    import json
    from bs4 import BeautifulSoup

    # load the mapping (normalize keys to uppercase)
    raw = json.loads((zone_dict_path).read_text(encoding='utf-8'))
    zone_map = {k.upper(): v for k, v in raw.items()}

    # scan all .htm files until we find the right one
    html_path = None
    for f in report_dir.glob("*.htm"):
        text = f.read_text(encoding='utf-8')
        if "People Internal Gains Nominal" in text:
            html_path = f
            break
    if html_path is None:
        raise FileNotFoundError(f"No HTML file in {report_dir} contains the target table")

    soup = BeautifulSoup(text, 'html.parser')

    # 1) Move TOC: find all <a href="#toc">, remove the 2nd, insert the 1st under <body>
    toc_links = soup.find_all('a', href="#toc")
    if len(toc_links) >= 2:
        first_p = toc_links[0].find_parent('p')
        second_p = toc_links[1].find_parent('p')
        second_p.decompose()
        first_p.extract()
        soup.body.insert(1, first_p)

    # 2) Replace GUIDs in the “People Internal Gains Nominal” table
    header = soup.find('b', string="People Internal Gains Nominal")
    if not header:
        raise RuntimeError("Found HTML but no ‘People Internal Gains Nominal’ header")
    # detect which column is “Zone Name”
    idx = None
    for i, cell in enumerate(tbl.find('tr').find_all(['td','th'])):
        if "Zone Name" in cell.get_text(strip=True):
            idx = i
            break

    if idx is not None:
        for tr in tbl.find_all('tr')[1:]:
            cols = tr.find_all('td')
            if len(cols) > idx:
                guid = cols[idx].get_text(strip=True).upper()
                if guid in zone_map:
                    cols[idx].string.replace_with(zone_map[guid])

    # write updated HTML
    out = report_dir / f"{html_path.stem}_with_names{html_path.suffix}"
    out.write_text(str(soup), encoding='utf-8')
    return out

class IdfPostprocessing(ITask):
    """Idf Postprocessin task.

    See run function for further details. """
    reads = ('elements', 'idf', 'ifc_files', 'sim_results_path')

    def run(self, elements: dict, idf: IDF, ifc_files: list,
            sim_results_path: Path):
        """EnergyPlus postprocessing for further evaluation and debugging.

        This task holds export functions for further evaluation and
        debugging. Information on spaces and space boundaries are exported
        and the zone names are exported in json format.

        Args:
            elements (dict): dictionary in the format dict[guid: element],
                holds preprocessed elements including space boundaries.
            idf (IDF): eppy idf, EnergyPlus input file.
            ifc_files (list): list of ifc files used in this project
            sim_results_path (Path): path to simulation results.
            """

        self.logger.info("IDF Postprocessing started...")

        self._export_surface_areas(elements, idf)
        self._export_space_info(elements, idf)
        self._export_boundary_report(elements, idf, ifc_files)
        self.write_zone_names(idf, elements,
                              sim_results_path / self.prj_name)
        self._export_combined_html_report()
        self.logger.info("IDF Postprocessing finished!")


    @staticmethod
    def write_zone_names(idf, elements, exportpath: Path):
        """
        Write a dictionary of the bim2sim ThermalZone names and usages.

        This method creates a dict and exports it to a json file (
        zone_dict.json) to the path defined in exportpath. This dict
        includes the zone name and the selected usage within bim2sim. All
        zones are considered that are created within the bim2sim elements.

        Args:
            idf: eppy idf
            elements: bim2sim elements
            exportpath: base path to place the resulting zone_dict.json

        """
        zones = idf.idfobjects['ZONE']
        zone_dict = {}
        ifc_zones = filter_elements(elements, ThermalZone)
        zone_dict_ifc_names = {}
        for zone in zones:
            # find the matching BIM2SIM ThermalZone element
            matches = [z for z in ifc_zones if z.guid == zone.Name]
            if matches:
                # use the .name property (i.e. IFC Reference)
                zone_dict[zone.Name] = matches[0].zone_name
            else:
                # fallback to GUID
                zone_dict[zone.Name] = zone.Name

        with open(exportpath / 'zone_dict.json', 'w+') as file:
            json.dump(zone_dict, file, indent=4)
        with open(exportpath / 'zone_dict_ifc_names.json', 'w+') as file:
            json.dump(zone_dict_ifc_names, file, indent=4)

    def _export_surface_areas(self, elements, idf):
        """ combines sets of area sums and exports to csv """
        area_df = pd.DataFrame(
            columns=["granularity", "ID", "long_name", "out_bound_cond",
                     "area_wall", "area_ceiling", "area_floor",
                     "area_roof", "area_window", "area_door",
                     "total_surface_area", "total_opening_area"])
        surf = [s for s in idf.idfobjects['BuildingSurface:Detailed'.upper()]
                if s.Construction_Name != 'Air Wall']
        glazing = [g for g in idf.idfobjects[
            'FenestrationSurface:Detailed'.upper()]]
        area_df = self._append_set_of_area_sum(area_df, granularity="GLOBAL",
                                               guid="GLOBAL",
                                               long_name="GLOBAL",
                                               surface=surf, glazing=glazing)
        zones = [z for z in idf.idfobjects['zone'.upper()]]
        zone_names = [z.Name for z in zones]

        for z_name in zone_names:
            surf_zone = [s for s in surf if s.Zone_Name == z_name]
            surf_names = [s.Name for s in surf_zone]
            long_name = elements[z_name].ifc.LongName
            glazing_zone = [g for g in glazing for s_name in surf_names if
                            g.Building_Surface_Name == s_name]
            area_df = self._append_set_of_area_sum(area_df, granularity="ZONE",
                                                   guid=z_name,
                                                   long_name=long_name,
                                                   surface=surf_zone,
                                                   glazing=glazing_zone)
        area_df.to_csv(path_or_buf=str(self.paths.export) + "/area.csv")

    def _append_set_of_area_sum(self, area_df, granularity, guid, long_name,
                                surface, glazing):
        """ generate set of area sums for a given granularity for outdoor,
        surface and adiabatic boundary conditions.
        Appends set to a given dataframe.
        """
        surf_outdoors = [s for s in surface if s.Outside_Boundary_Condition ==
                         "Outdoors" or s.Outside_Boundary_Condition == "Ground"]
        surf_surface = [s for s in surface if s.Outside_Boundary_Condition ==
                        "Surface"]
        surf_adiabatic = [s for s in surface if s.Outside_Boundary_Condition ==
                          "Adiabatic"]
        glazing_outdoors = [g for g in glazing if
                            g.Outside_Boundary_Condition_Object == ""]
        glazing_surface = [g for g in glazing if
                           g.Outside_Boundary_Condition_Object != ""]
        glazing_adiabatic = []

        area_df = pd.concat([area_df, pd.DataFrame.from_records([
            self._sum_of_surface_area(
                granularity=granularity, guid=guid, long_name=long_name,
                out_bound_cond="ALL", surface=surface, glazing=glazing),
            self._sum_of_surface_area(
                granularity=granularity, guid=guid, long_name=long_name,
                out_bound_cond="Outdoors",surface=surf_outdoors,
                glazing=glazing_outdoors),
            self._sum_of_surface_area(
                granularity=granularity, guid=guid, long_name=long_name,
                out_bound_cond="Surface", surface=surf_surface,
                glazing=glazing_surface),
            self._sum_of_surface_area(
                granularity=granularity, guid=guid, long_name=long_name,
                out_bound_cond="Adiabatic", surface=surf_adiabatic,
                glazing=glazing_adiabatic)
        ])],
                             ignore_index=True)
        return area_df

    @staticmethod
    def _sum_of_surface_area(granularity, guid, long_name, out_bound_cond,
                             surface, glazing):
        """ generate row with sum of surface and opening areas to be appended
        to larger dataframe"""
        row = {
            "granularity": granularity,
            "ID": guid,
            "long_name": long_name,
            "out_bound_cond": out_bound_cond,
            "area_wall": sum(s.area for s in surface if s.Surface_Type ==
                             "Wall"),
            "area_ceiling": sum(s.area for s in surface if s.Surface_Type ==
                                "Ceiling"),
            "area_floor": sum(s.area for s in surface if s.Surface_Type ==
                              "Floor"),
            "area_roof": sum(s.area for s in surface if s.Surface_Type ==
                             "Roof"),
            "area_window": sum(g.area for g in glazing if g.Surface_Type ==
                               "Window"),
            "area_door": sum(g.area for g in glazing if g.Surface_Type ==
                             "Door"),
            "total_surface_area": sum(s.area for s in surface),
            "total_opening_area": sum(g.area for g in glazing)
        }
        return row

    def _export_space_info(self, elements, idf):
        space_df = pd.DataFrame(
            columns=["ID", "long_name", "space_center", "space_volume"])
        spaces = filter_elements(elements, 'ThermalZone')
        for space in spaces:
            space_df = pd.concat([space_df, pd.DataFrame.from_records([{
                    "ID": space.guid,
                    "long_name": space.ifc.LongName,
                    "space_center": space.space_center.XYZ().Coord(),
                    "space_volume": space.space_shape_volume.m
                }])],
                ignore_index=True)
        space_df.to_csv(path_or_buf=str(self.paths.export) + "/space.csv")

    def _export_combined_html_report(self):
        """Create an HTML report combining area.csv and bound_count.csv data.
        
        This method reads the previously exported CSV files and combines them
        into a single HTML report with basic visualization.
        The HTML file is saved in the same directory as the CSV files.
        """
        export_path = Path(str(self.paths.export))
        area_file = export_path / "area.csv"
        bound_count_file = export_path / "bound_count.csv"
        html_file = export_path / "area_bound_count_energida.htm"
        
        # Read the CSV files
        area_df = pd.read_csv(area_file)
        bound_count_df = pd.read_csv(bound_count_file)
        
        # Convert DataFrames to HTML tables
        area_table = area_df.to_html(index=False)
        bound_count_table = bound_count_df.to_html(index=False)
        
        # Create HTML content without complex formatting
        html_content = """<!DOCTYPE html>
    <html>
    <head>
        <title>BIM2SIM Export Report</title>
        <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        h1 { color: #333366; }
        h2 { color: #336699; margin-top: 30px; }
        table { border-collapse: collapse; width: 100%; margin-bottom: 30px; } 
        th { background-color: #336699; color: white; text-align: left; padding: 8px; }
        td { border: 1px solid #ddd; padding: 8px; }
        tr:nth-child(even) { background-color: #f2f2f2; }
        tr:hover { background-color: #e6e6e6; }
        </style>
    </head>
    <body>
        <h1>BIM2SIM Export Report</h1>
        
        <h2>Surface Areas</h2>
    """ + area_table + """
        
        <h2>Boundary Counts</h2>
    """ + bound_count_table + """
    </body>
    </html>"""
        
        # Save the HTML file
        with open(html_file, 'w') as f:
            f.write(html_content)
        
        self.logger.info(f"Combined HTML report saved to {html_file}")

    def _export_boundary_report(self, elements, idf, ifc_files):
        """Export a report on the number of space boundaries.
        Creates a report as a DataFrame and exports it to csv.

        Columns:
            IFC_SB_all: Number of IfcRelSpaceBoundary elements included in
                the given IFC files,
            IFC_SB_2a: Number of IfcRelSpaceBoundary elements included in
                the given IFC files of type 2a,
            IFC_SB_2b: Number of IfcRelSpaceBoundary elements included in
                the given IFC files of type 2b,
            BIM2SIM_SB_2b: Number of SpaceBoundary elements created within
                the bim2sim tool generated from gaps within the IfcSpaces,
            IDF_all: Total number of FENESTRATIONSURFACE:DETAILED and
                BUILDINGSURFACE:DETAILED elements in the resulting IDF,
            IDF_all_B: Total number of BUILDINGSURFACE:DETAILED elements in
                the resulting IDF,
            IDF_ADB: Number of BUILDINGSURFACE:DETAILED elements with
                adiabatic boundary conditions,
            IDF_SFB: Number of BUILDINGSURFACE:DETAILED elements with
                "surface" boundary conditions,
            IDF_ODB: Number of BUILDINGSURFACE:DETAILED elements with
                outdoor boundary conditions,
            IDF_GDB: Number of BUILDINGSURFACE:DETAILED elements with
                ground boundary conditions,
            IDF_VTB:  Number of BUILDINGSURFACE:DETAILED elements with
                an air wall construction,
            IDF_all_F: Total number of FENESTRATIONSURFACE:DETAILED elements in
                the resulting IDF,
            IDF_ODF: Number of FENESTRATIONSURFACE:DETAILED elements in
                the resulting IDF without outside boundary condition object,
            IDF_INF: Total number of FENESTRATIONSURFACE:DETAILED elements in
                the resulting IDF with an outside boundary condition object.
        """
        bound_count = pd.DataFrame(
            columns=["IFC_SB_all", "IFC_SB_2a", "IFC_SB_2b", "BIM2SIM_SB_2b",
                     "IDF_all", "IDF_all_B", "IDF_ADB", "IDF_SFB",
                     "IDF_ODB", "IDF_GDB", "IDF_VTB", "IDF_all_F",
                     "IDF_ODF", "IDF_INF"])
        ifc_bounds = []
        for ifc in ifc_files:
            ifc_bounds.extend(ifc.file.by_type('IfcRelSpaceBoundary'))
        bounds_2b = filter_elements(elements, 'SpaceBoundary2B')
        idf_all_b = [s for s in idf.idfobjects["BUILDINGSURFACE:DETAILED"]]
        idf_adb = [s for s in idf.idfobjects["BUILDINGSURFACE:DETAILED"]
                   if s.Outside_Boundary_Condition == "Adiabatic"]
        idf_sfb = [s for s in idf.idfobjects["BUILDINGSURFACE:DETAILED"]
                   if s.Outside_Boundary_Condition == "Surface"]
        idf_odb = [s for s in idf.idfobjects["BUILDINGSURFACE:DETAILED"]
                   if s.Outside_Boundary_Condition == "Outdoors"]
        idf_gdb = [s for s in idf.idfobjects["BUILDINGSURFACE:DETAILED"]
                   if s.Outside_Boundary_Condition == "Ground"]
        idf_vtb = [s for s in idf.idfobjects["BUILDINGSURFACE:DETAILED"]
                   if s.Construction_Name == "Air Wall"]
        idf_all_f = [f for f in idf.idfobjects["FENESTRATIONSURFACE:DETAILED"]]
        idf_odf = [f for f in idf.idfobjects["FENESTRATIONSURFACE:DETAILED"] if
                   f.Outside_Boundary_Condition_Object == '']
        idf_inf = [f for f in idf.idfobjects["FENESTRATIONSURFACE:DETAILED"] if
                   f.Outside_Boundary_Condition_Object != '']

        bound_count = pd.concat([bound_count, pd.DataFrame.from_records([{
            "IFC_SB_all": len(ifc_bounds),
            "IFC_SB_2a": len([b for b in ifc_bounds if b.Description ==
                              "2a"]),
            "IFC_SB_2b": len([b for b in ifc_bounds if b.Description == "2b"]),
            "BIM2SIM_SB_2b": len(bounds_2b),
            "IDF_all": len(idf_all_b) + len(idf_all_f),
            "IDF_all_B": len(idf_all_b),
            "IDF_ADB": len(idf_adb),
            "IDF_SFB": len(idf_sfb),
            "IDF_ODB": len(idf_odb),
            "IDF_GDB": len(idf_gdb),
            "IDF_VTB": len(idf_vtb),
            "IDF_all_F": len(idf_all_f),
            "IDF_ODF": len(idf_odf),
            "IDF_INF": len(idf_inf)
        }])],
            ignore_index=True)
        bound_count.to_csv(
            path_or_buf=str(self.paths.export) + "/bound_count.csv")
