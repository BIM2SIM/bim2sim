from typing import List

from OCC.Core.TopoDS import TopoDS_Shape
from OCC.Display.SimpleGui import init_display


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
                face_towards_center = space.space_center.XYZ() - bound.bound_center
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
