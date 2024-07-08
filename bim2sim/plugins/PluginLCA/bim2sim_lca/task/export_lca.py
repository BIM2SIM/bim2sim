import csv
from pathlib import Path

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


class ExportLCA(ITask):
    """Exports a CSV file with all relevant quantities of the BIM model"""
    reads = ('ifc_files', 'elements')
    final = True

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

    def run(self, ifc_files, elements):
        self.logger.info("Exporting LCA quantities to CSV")

        self.export_materials(elements)
        self.export_overview(elements)

    def export_materials(self, elements):
        """Exports only the materials and its total volume and mass if density
        is given in the IFC"""
        export_path = Path(
            self.paths.export) / ("Material_quantities_" + self.prj_name +
                                  ".csv")
        materials = {}
        for mat in filter_elements(elements, Material):
            materials[mat] = {
                "name": mat.name,
                "density": mat.density,
                "volume": 0 * ureg.m ** 3,
                "mass": None
            }
        # todo: if we have the volume of each layer we can do this more straight
        #  forward, until then this is a workaround
        for inst in elements.values():
            if not isinstance(inst, self.blacklist_elements):
                # uniform materials
                if inst.material:
                    if inst.volume:
                        materials[inst.material]["volume"] += inst.volume
                if hasattr(inst, "layerset"):
                    if inst.layerset:
                        for layer in inst.layerset.layers:
                            if inst.net_area and layer.thickness:
                                materials[layer.material]["volume"] += \
                                    inst.net_area * layer.thickness
                if hasattr(inst, 'material_set'):
                    if inst.material_set:
                        for fraction, material in inst.material_set.items():
                            if not "unknown" in fraction:
                                materials[material]["volume"] += \
                                    inst.volume * fraction

        # calculate mass if density is given in IFC
        with open(file=export_path, mode='w', newline='') as file:
            writer = csv.writer(file, delimiter=';', quotechar='"',
                                quoting=csv.QUOTE_MINIMAL)
            writer.writerow(
                ["Name",
                 "Density [kg/m³]",
                 "Total Volume[m³]",
                 "Total Mass[kg]"]
            )

            for mat in materials.keys():
                writer.writerow([
                    mat.name,
                    self.ureg_to_str(materials[mat]["density"],
                                     ureg.kg / ureg.m ** 3),
                    self.ureg_to_str(materials[mat]["volume"], ureg.m ** 3),
                    self.ureg_to_str(
                        materials[mat]["volume"] * materials[mat]["density"],
                        ureg.kg) if materials[mat]["density"] else "-"
                ])

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

    @staticmethod
    def ureg_to_str(value, unit, n_digits=3, ):
        """Transform pint unit to human readable value with given unit."""
        if value is not None and not isinstance(value, float):
            return round(value.to(unit).m, n_digits)
        elif value is None:
            return "-"
        else:
            return value
