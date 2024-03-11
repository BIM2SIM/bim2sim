import ifcopenshell
import ifcopenshell.geom
from OCC.Display.SimpleGui import init_display

settings = ifcopenshell.geom.settings()
settings.set(settings.USE_PYTHON_OPENCASCADE, True)
settings.set(settings.USE_WORLD_COORDS, True)
settings.set(settings.EXCLUDE_SOLIDS_AND_SURFACES, False)
settings.set(settings.INCLUDE_CURVES, True)

# TODO have a look at #387

class ThermalZone:
    ifc_type = 'IfcSpace'

    def __init__(self, ifc_space):
        self.ifc = ifc_space
        self.space_shape = ifcopenshell.geom.create_shape(settings,
                                                          ifc_space).geometry


if __name__ == '__main__':
    ifc_file = ifcopenshell.open(
        # '/home/veronika/PycharmProjects/bim2sim-coding/ExampleFiles/AC20-FZK-Haus.ifc')
        'D:/02_Git/bim2sim-coding/ExampleFiles/AC20-Institute-Var-2.ifc')
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
        display.DisplayShape(tz.space_shape, update=True, color=color,
                             transparency=0.7)
    display.FitAll()
    start_display()
