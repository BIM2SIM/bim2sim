import ifcopenshell
import ifcopenshell.geom
from OCC.Display.SimpleGui import init_display
from bim2sim.task.base import ITask
from pathlib import Path
from bim2sim.workflow import Workflow

settings = ifcopenshell.geom.settings()
settings.set(settings.USE_PYTHON_OPENCASCADE, True)
settings.set(settings.USE_WORLD_COORDS, True)
settings.set(settings.EXCLUDE_SOLIDS_AND_SURFACES, False)
settings.set(settings.INCLUDE_CURVES, True)

class VisualizeThermalZone(ITask):
    ifc_type = 'IfcSpace'
    reads = ('ifc', 'instances')

    def run(self, workflow, ifc, instances):
        self.logger.info("Display a geometry shape of ifc file")
        thermal_zones = self._get_ifcspace(ifc=ifc)
        #self._visualize_thermal_zone(thermal_zones=thermal_zones)
        # todo: thermalzone nach räumen aufgelistet
        #self._get_thermalzone_objects(thermal_zones=thermal_zones)
        _dict_room_position = self._get_position(instances=instances)
        print(_dict_room_position)

    def _visualize_thermal_zone(self, thermal_zones):
        display, start_display, add_menu, add_function_to_menu = init_display()
        for tz in thermal_zones:
            color = 'blue'
            if tz.ifc.LongName:
                if 'Buero' in tz.ifc.LongName:
                    color = 'red'
                elif 'Besprechungsraum' in tz.ifc.LongName:
                    color = 'green'
                elif 'Schlafzimmer' in tz.ifc.LongName:
                    color = 'yellow'
            display.DisplayShape(tz.space_shape, update=True, color=color,
                                 transparency=0.7)
        display.FitAll()
        start_display()

    def _get_thermalzone_objects(self, thermal_zones):
        for room in thermal_zones:
            for l in room.ifc:
                print(l)

    def _get_ifcspace(self, ifc ):
        ifc_spaces = ifc.by_type('IfcSpace')
        thermal_zones = []
        for ifc_space in ifc_spaces:
            thermal_zones.append(ThermalZone(ifc_space))
        return thermal_zones

    def _get_position(self, instances):
        _dict_room_position = {}
        for inst in instances.values():
            if inst.__class__.__name__ == "ThermalZone":
                _dict_room_position[inst.zone_name] = inst.position
        return _dict_room_position

class ThermalZone:
    ifc_type = 'IfcSpace'

    def __init__(self, ifc_space):
        self.ifc = ifc_space
        self.space_shape = ifcopenshell.geom.create_shape(settings, ifc_space).geometry
        #self.space_shape = ifcopenshell.geom.create_shape(settings, ifc_space).geo
        #default_ifc_types = {'IfcBuildingElementProxy', 'IfcUnitaryEquipment'}
        #relevant_ifc_types = self.get_ifc_types(workflow.relevant_elements)
        #relevant_ifc_types.update(default_ifc_types)


if __name__ == '__main__':
    ifc_path = Path(__file__).parent.parent.parent \
               / 'assets/ifc_example_files/AC20-FZK-Haus.ifc'
    ifc_file = ifcopenshell.open(ifc_path)
    ifc_spaces = ifc_file.by_type('IfcSpace')

    thermal_zones = []
    for ifc_space in ifc_spaces:
        thermal_zones.append(ThermalZone(ifc_space))

    display, start_display, add_menu, add_function_to_menu = init_display()
    for tz in thermal_zones:
        color = 'blue'
        if tz.ifc.LongName:
            if 'Buero' in tz.ifc.LongName:
                color = 'red'
            elif 'Besprechungsraum' in tz.ifc.LongName:
                color = 'green'
            elif 'Schlafzimmer' in tz.ifc.LongName:
                color = 'yellow'
        print(tz.space_shape)
        t = display.DisplayShape(tz.space_shape, update=True, color=color,
                             transparency=0.7)
        print(t[0])

    display.FitAll()
    start_display()