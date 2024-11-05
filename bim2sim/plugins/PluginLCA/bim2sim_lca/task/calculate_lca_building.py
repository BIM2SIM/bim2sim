import csv
from pathlib import Path

import pandas as pd

from bim2sim.elements.base_elements import Material
from bim2sim.elements.bps_elements import LayerSet, Layer, Site, Building, \
    Storey, SpaceBoundary, ExtSpatialSpaceBoundary, SpaceBoundary2B
from bim2sim.elements.mapping.units import ureg
from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_elements

KG_names = {
    300: "Building Construction",
    310: "excavation/earthwork",
    311: "fabrication",
    312: "enclosure",
    313: "dewatering",
    314: "Excavation",
    319: "Other to KG 310: excavation/earthwork",
    320: "Foundation, Subgrade",
    321: "Subsoil Improvement",
    322: "Shallow Foundations and Base Slabs",
    323: "Deep Foundations",
    324: "Foundation Coverings",
    325: "Waterproofing and Cladding",
    326: "Drainage",
    329: "Miscellaneous to KG 320: Foundation, Substructure",
    330: "Exterior walls/vertical building structures, exterior",
    331: "Load-bearing exterior walls",
    332: "Non-bearing exterior walls",
    333: "Exterior Supports",
    334: "Exterior Wall Openings",
    335: "Exterior wall coverings, exterior",
    336: "Exterior wall claddings, interior",
    337: "Elemental exterior wall assemblies",
    338: "Light protection to KG 330: Exterior walls/vertical building structures, exterior",
    339: "Other to KG 330: Exterior Walls/Vertical Building Structures, Exterior",
    340: "Interior walls/vertical building structures, interior",
    341: "Load-bearing interior walls",
    342: "Non-bearing interior walls",
    343: "Interior Supports",
    344: "Interior wall openings",
    345: "Interior wall cladding",
    346: "Elemental interior wall constructions",
    347: "Light protection to KG 340: Interior walls/vertical building structures, interior",
    349: "Other to KG 340: Interior Walls/Vertical Building Structures, Interior",
    350: "Ceilings/Horizontal Building Structures",
    351: "Ceiling Structures",
    352: "Ceiling Openings",
    353: "Ceiling coverings",
    354: "Ceiling Coverings",
    355: "Elemental ceiling structures",
    359: "Other to KG 350: Ceilings/Horizontal Building Structures",
    360: "Roofs",
    361: "Roof Structures",
    362: "Roof Openings",
    363: "Roof Coverings",
    364: "Roof Coverings",
    365: "Elemental roof structures",
    366: "Light protection to KG 360: Roofs",
    369: "Other to KG 360: Roofs",
    400: "Building - technical installations",
    410: "Sewage, water, gas installations",
    411: "Sewage Plants",
    412: "Water Plants",
    413: "Gas installations",
    419: "Other to KG 410: sewage, water, gas installations",
    420: "Heat supply plants",
    421: "Heat generation plants",
    422: "Heat distribution networks",
    423: "Space heating surfaces",
    424: "Traffic heating surfaces",
    429: "Other to KG 420: Heat supply systems",
    430: "Ventilation and air-conditioning systems",
    431: "Ventilation systems",
    432: "Partial air conditioning systems",
    433: "Air conditioning systems",
    434: "Refrigeration plants",
    439: "Other to KG 430: Ventilation and air-conditioning systems",
    440: "Electrical installations",
    441: "High and medium voltage installations",
    442: "In-house power supply systems",
    443: "Low-voltage switchgear",
    444: "Low-voltage installation plants",
    445: "Lighting installations",
    446: "Lightning protection and grounding systems",
    447: "Catenary systems",
    449: "Other to KG 440: Electrical installations",
    450: "Communication, security and information technology installations",
    451: "Telecommunication systems",
    452: "Search and signal systems",
    453: "Time Service Installations",
    454: "Electroacoustic installations",
    455: "Audiovisual media and antenna systems",
    456: "Hazard detection and alarm systems",
    457: "Data transmission networks",
    458: "Traffic control systems",
    459: "Other KG 450: Communication, security and information technology systems, Conveyor systemsen",
    460: "Conveyor systems",
    461: "Elevator systems",
    462: "Escalators, moving walks",
    463: "Access systems",
    464: "Transportation systems",
    465: "crane systems",
    466: "Hydraulic plants",
    469: "Other to KG 460: Conveyor systems",
    470: "Use-specific and process engineering plants",
    471: "Kitchen technical installations",
    472: "Laundry, cleaning and bathing technical plants",
    473: "Media supply plants, medical and laboratory plants",
    474: "Fire extinguishing systems",
    475: "Process heating, cooling and air systems",
    476: "Other use-specific plants",
    477: "Process plants, water, wastewater and gases",
    478: "Process plants, solids, recyclables and waste",
    479: "Other to KG 470: Use-specific and process plants",
    480: "Building and plant automation",
    481: "Automation Equipment",
    482: "Control Cabinets, Automation Focuses",
    483: "Automation management",
    484: "Cables, conduits and installation systems",
    485: "Data transmission networks",
    489: "Other to KG 480: Building and Plant Automation",
    600: "Equipment and Artwork",
    610: "General Equipment",
    620: "Special Equipment",
    630: "Information Technology Equipment",
    640: "Artistic Equipment",
    690: "Other Equipment",
    000: "Cost group cannot be determined. Reason is lack of information."}


class CalculateEmissionBuilding(ITask):
    """Exports a CSV file with all relevant quantities of the BIM model"""
    reads = ('ifc_files', 'elements', 'material_emission_dict')
    touches = ()

    def __init__(self, playground):
        super().__init__(playground)
        # some elements should not be exported or exported as relation to
        # others
        self.blacklist_elements = (
            Site,
            Building,
            Storey,
            SpaceBoundary,
            ExtSpatialSpaceBoundary,
            SpaceBoundary2B,
            Material,
            LayerSet,
            Layer
        )

    def run(self, ifc_files, elements, material_emission_dict):
        if self.playground.sim_settings.calculate_lca_building:
            self.logger.info("Exporting material quantities to CSV")

            building_material_dict = self.export_materials(elements)
            self.export_overview(elements)

            self.logger.info("Calculate building lca and export to csv")
            building_material_dict = self.calculate_building_emissions(material_emission=material_emission_dict,
                                                                       building_material=building_material_dict)
            total_gwp = self.total_sum_emission(building_material=building_material_dict)
            self.export_material_data_and_lca(building_material=building_material_dict,
                                              total_gwp=total_gwp)


    def export_materials(self, elements):
        """Exports only the materials and its total volume and mass if density
        is given in the IFC"""
        export_path = Path(
            self.paths.export) / ("material_quantities_building.csv")
        data = {}
        for material in filter_elements(elements, Material):
            data[material] = {
                "name": material.name,
                "density": material.density,
                "volume": 0 * ureg.m ** 3,
                "mass": None
            }
        # todo: if we have the volume of each layer we can do this more straight
        #  forward, until then this is a workaround
        for inst in elements.values():
            if not isinstance(inst, self.blacklist_elements):
                # uniform data
                if inst.material:
                    if inst.volume:
                        data[inst.material]["volume"] += inst.volume
                if hasattr(inst, "layerset"):
                    if inst.layerset:
                        for layer in inst.layerset.layers:
                            if inst.net_area and layer.thickness:
                                data[layer.material]["volume"] += \
                                    inst.net_area * layer.thickness
                if hasattr(inst, 'material_set'):
                    if inst.material_set:
                        for fraction, material in inst.material_set.items():
                            if not "unknown" in fraction:
                                data[material]["volume"] += \
                                    inst.volume * fraction

        material_data = {}
        for key in data.keys():
            material_data[data[key]["name"]] = {}
            material_data[data[key]["name"]]["Density [kg/m³]"] = self.ureg_to_str(data[key]["density"],
                                                                                        ureg.kg / ureg.m ** 3)
            material_data[data[key]["name"]]["Total Volume [m³]"] = self.ureg_to_str(data[key]["volume"],
                                                                                         ureg.m ** 3)
            material_data[data[key]["name"]]["Total Mass [kg]"] = self.ureg_to_str(
                data[key]["volume"] * data[key]["density"],
                ureg.kg) if data[key]["density"] else 0

        df = pd.DataFrame.from_dict(material_data, orient="index")
        with pd.ExcelWriter(self.paths.export / "material_quantities_building.xlsx") as writer:
            df.to_excel(writer, sheet_name="Materials", index=True, index_label="Material")

        return material_data

    def export_overview(self, elements):
        export_path = Path(
            self.paths.export) / \
                      ("Quantities_overview_" + self.prj_name + ".csv")
        with open(file=export_path, mode='w', newline='') as file:
            writer = csv.writer(file, delimiter=';', quotechar='"',
                                quoting=csv.QUOTE_MINIMAL)
            writer.writerow(
                ['GUID', 'Storey', 'Type', 'Cost Group Number',
                 'Cost Group Name', 'Name', 'Material Type', 'Material Name',
                 'Material Density [kg/m³]',
                 'Material Specific Heat Capacity [kJ/ (kg K)]',
                 'Material Thermal Conductivity [W/(m K)]',
                 'Area[m²]', 'Thickness[m] / Fraction [-]', 'Volume [m³]'
                 ])
            for inst in elements.values():
                if not isinstance(inst, self.blacklist_elements):
                    # General information
                    inst_guid = inst.guid
                    storey_names = ", ".join(
                        [storey.name for storey in inst.storeys])
                    inst_cls_name = inst.__class__.__name__
                    inst_cost_group = inst.cost_group
                    inst_cost_group_name = KG_names[inst.cost_group]
                    inst_name = inst.name
                    inst_material_type = 'Uniform' if inst.material else '-'
                    inst_material_name = inst.material.name if inst.material \
                        else '-'
                    inst_mat_dens = self.ureg_to_str(
                        inst.material.density, ureg.kg / ureg.m ** 3) \
                        if inst.material else '-'
                    inst_mat_heat_capac = self.ureg_to_str(
                        inst.material.spec_heat_capacity,
                        ureg.kilojoule / (ureg.kg * ureg.K)) \
                        if inst.material else '-'
                    inst_mat_conduc = self.ureg_to_str(
                        inst.material.thermal_conduc,
                        ureg.W / ureg.m / ureg.K) if inst.material else '-'
                    inst_area = self.ureg_to_str(
                        inst.net_area, ureg.m ** 2) if inst.net_area \
                        else self.ureg_to_str(inst.gross_area, ureg.m ** 2)
                    inst_width = self.ureg_to_str(inst.width, ureg.m)
                    inst_vol = self.ureg_to_str(inst.volume, ureg.m ** 3)

                    # export instance itself
                    writer.writerow([
                        inst_guid,
                        storey_names,
                        inst_cls_name,
                        inst.cost_group,
                        inst_cost_group_name,
                        inst_name,
                        inst_material_type,
                        inst_material_name,
                        inst_mat_dens,
                        inst_mat_heat_capac,
                        inst_mat_conduc,
                        inst_area,
                        inst_width,
                        inst_vol
                    ])
                    # export elements layers
                    if hasattr(inst, 'layerset'):
                        if inst.layerset:
                            for layer in inst.layerset.layers:
                                layer_cls_name = layer.__class__.__name__
                                layer_mat_name = layer.material.name \
                                    if layer.material else '-'
                                writer.writerow([
                                    inst_guid,
                                    storey_names,
                                    inst_cls_name,
                                    inst_cost_group,
                                    inst_cost_group_name,
                                    inst_name,
                                    layer_cls_name,
                                    layer_mat_name,
                                    self.ureg_to_str(layer.material.density,
                                                     ureg.kg / ureg.m ** 3)
                                    if layer.material else '-',
                                    self.ureg_to_str(
                                        layer.material.spec_heat_capacity,
                                        ureg.kilojoule / (ureg.kg * ureg.K))
                                    if layer.material else '-',
                                    self.ureg_to_str(
                                        layer.material.thermal_conduc,
                                        ureg.W / ureg.m / ureg.K)
                                    if layer.material else '-',
                                    inst_area,
                                    self.ureg_to_str(layer.thickness, ureg.m),
                                    self.ureg_to_str(layer.volume, ureg.m ** 3),
                                ])
                    # export elements constituent sets
                    if hasattr(inst, 'material_set'):
                        if inst.material_set:
                            for fraction, material in inst.material_set.items():
                                writer.writerow([
                                    inst_guid,
                                    storey_names,
                                    inst_cls_name,
                                    inst_cost_group,
                                    inst_cost_group_name,
                                    inst_name,
                                    "Material Constituent",
                                    material.name,
                                    self.ureg_to_str(material.density,
                                                     ureg.kg / ureg.m ** 3),
                                    self.ureg_to_str(
                                        material.spec_heat_capacity,
                                        ureg.kilojoule / (ureg.kg * ureg.K)),
                                    self.ureg_to_str(material.thermal_conduc,
                                                     ureg.W / ureg.m / ureg.K),
                                    inst_area,
                                    fraction if 'unknown' in fraction
                                    else self.ureg_to_str(fraction,
                                                          ureg.dimensionless),
                                    "-" if 'unknown' in fraction
                                    else inst.volume * fraction
                                ])

    def calculate_building_emissions(self,
                                     material_emission,
                                     building_material):

        mapping = {"Kalksandstein 2774059904": "Kalksandstein",
                    "Kalksandstein 2816491304": "Kalksandstein",
                    "Aluminium 131198" : "Aluminium",
                    "Stahlbeton 2747937872": "concrete_CEM_II_BS325R_wz05",
                    "Glas1995_2015AluoderStahlfensterWaermeschutzverglasungzweifach": "Glas1995_2015AluoderStahlfensterWaermeschutzverglasungzweifach",
                    "Glas1995_2015AluoderStahlfensterIsolierverglasung": "Glas1995_2015AluoderStahlfensterIsolierverglasung",
                    "Glas1995_2015Waermeschutzverglasungdreifach": "Glas1995_2015Waermeschutzverglasungdreifach",
                    "concrete_CEM_II_BS325R_wz05": "concrete_CEM_II_BS325R_wz05",
                    "foam_glass_board_130": "foam_glass_board_130",
                    "gravel_single_granular": "gravel_single_granular",
                    "lime_plaster": "lime_plaster",
                    "vertical_core_brick_700": "vertical_core_brick_700",
                    "EPS_040_15": "EPS_040_15",
                    "cement_floating_screed_2_bottom": "cement_floating_screed_2_bottom",
                    "Stahlbeton 2747937872": "2747937872",
                    "Door0_2015Typical": "Door0_2015Typical",
                    "plasterboard" :"plasterboard",
                    "mineral_wool_040" :"mineral_wool_040",
                    "steel_sheet": "steel_sheet",
                    "XPS_3_core_layer": "XPS_3_core_layer",
                    "fibreboard": "fibreboard",
                    "footstep_sound_insulation": "footstep_sound_insulation",
                    "wooden_beams_with_insulation" : "wooden_beams_with_insulation",
                    "oak_longitudinal": "oak_longitudinal",
                    "wood_wool_board_magnesia_460": "wood_wool_board_magnesia_460"
                    }
        for key, values in building_material.items():
            if key in mapping:
                corresponding_material = mapping[key]
                if corresponding_material in material_emission:
                    if values["Total Mass [kg]"] is None or material_emission[corresponding_material] is None:
                        emissions = 0
                    else:
                        emissions = values["Total Mass [kg]"] * material_emission[corresponding_material]
                    values["GWP [kg CO2-eq]"] = emissions
            else:
                print(f'Material {key} nicht erkannt.')
                exit(1)
        return building_material


    def total_sum_emission(self, building_material):
        total_gwp  = 0
        for key in building_material:
            if "GWP [kg CO2-eq]" in building_material[key].keys():
                total_gwp += (building_material[key]["GWP [kg CO2-eq]"])
        return total_gwp

    def export_material_data_and_lca(self,
                   building_material,
                   total_gwp):

        building_material["Total"] = {"Density [kg/m³]": "", "Total Volume [m³]": "", "Total Mass [kg]": "",
                                      "GWP [kg CO2-eq]": total_gwp}

        with pd.ExcelWriter(self.paths.export / "lca_building.xlsx") as writer:
            df = pd.DataFrame.from_dict(building_material, orient="index")
            df.to_excel(writer, index=True, index_label="Material", sheet_name="Materials")

    @staticmethod
    def ureg_to_str(value, unit, n_digits=3, ):
        """Transform pint unit to human readable value with given unit."""
        if value is not None and not isinstance(value, float):
            return round(value.to(unit).m, n_digits)
        elif value is None:
            return "-"
        else:
            return value
