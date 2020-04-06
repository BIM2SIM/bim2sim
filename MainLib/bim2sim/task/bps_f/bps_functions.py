from bim2sim.kernel.element import Element
import ifcopenshell
import ifcopenshell.geom
import math
from shapely.geometry.polygon import Polygon
from shapely.geometry import Point
import matplotlib.pyplot as plt


def find_building_polygon(slabs):
    settings = ifcopenshell.geom.settings()
    area_slab = 0
    slab_big = 0
    slab_rep = 0
    for slab in slabs:
        representation = Element.factory(slab)
        area_element = representation.area
        if area_element > area_slab:
            area_slab = area_element
            slab_big = slab
            slab_rep = representation

    shape = ifcopenshell.geom.create_shape(settings, slab_big)
    vertices = []
    i = 0
    while i < len(shape.geometry.verts):
        vertices.append(shape.geometry.verts[i:i + 2])
        i += 3

    p1 = [float("inf"), 0]
    p3 = [-float("inf"), 0]
    p4 = [0, float("inf")]
    p2 = [0, -float("inf")]

    for element in vertices:

        if element[0] < p1[0]:
            p1 = [element[0], element[1]]
        if element[0] > p3[0]:
            p3 = [element[0], element[1]]
        if element[1] < p4[1]:
            p4 = [element[0], element[1]]
        if element[1] > p2[1]:
            p2 = [element[0], element[1]]

    p1[0] = p1[0] + slab_rep.position[0]
    p3[0] = p3[0] + slab_rep.position[0]
    p4[0] = p4[0] + slab_rep.position[0]
    p2[0] = p2[0] + slab_rep.position[0]
    p1[1] = p1[1] + slab_rep.position[1]
    p3[1] = p3[1] + slab_rep.position[1]
    p4[1] = p4[1] + slab_rep.position[1]
    p2[1] = p2[1] + slab_rep.position[1]

    slope = (p2[1] - p1[1]) / (p2[0] - p1[0])
    if 0.4 > slope > -0.4:
        cardinal_direction = ['E', 'W', 'N', 'S']
    elif 2.4 > slope > 0.4:
        cardinal_direction = ['NE', 'SW', 'NW', 'SE']
    elif -0.4 > slope > -2.4:
        cardinal_direction = ['SE', 'NW', 'SW', 'NE']
    else:
        cardinal_direction = []

    return p1, p2, p3, p4, cardinal_direction


def find_building_envelope(p1, p2, p3, p4):
    building_envelope = []
    tolerance = 4

    slope = abs((p2[1] - p1[1]) / (p2[0] - p1[0]))
    tolerance_x = tolerance * math.cos(slope)
    tolerance_y = tolerance * math.sin(slope)
    building_envelope.append(Polygon([(p1[0] - tolerance_x, p1[1] + 2 * tolerance_y),
                                      (p2[0] + tolerance_x, p2[1] + 2 * tolerance_y),
                                      (p2[0] + tolerance_x, p2[1] - tolerance_y),
                                      (p1[0] - tolerance_x, p1[1] - tolerance_y)]))

    slope = abs((p3[1] - p2[1]) / (p3[0] - p2[0]))
    tolerance_x = 2 * tolerance * math.cos(slope)
    tolerance_y = tolerance * math.sin(slope)
    building_envelope.append(Polygon([(p3[0] - tolerance_x, p3[1] - tolerance_y),
                                      (p2[0] - tolerance_x, p2[1] + tolerance_y),
                                      (p2[0] + 2 * tolerance_x, p2[1] + tolerance_y),
                                      (p3[0] + 2 * tolerance_x, p3[1] - tolerance_y)]))

    slope = abs((p4[1] - p3[1]) / (p4[0] - p3[0]))
    tolerance_x = tolerance * math.cos(slope)
    tolerance_y = tolerance * math.sin(slope)
    building_envelope.append(Polygon([(p3[0] + tolerance_x, p3[1] - 2 * tolerance_y),
                                      (p4[0] - tolerance_x, p4[1] - 2 * tolerance_y),
                                      (p4[0] - tolerance_x, p4[1] + tolerance_y),
                                      (p3[0] + tolerance_x, p3[1] + tolerance_y)]))

    slope = abs((p1[1] - p4[1]) / (p1[0] - p4[0]))
    tolerance_x = 2 * tolerance * math.cos(slope)
    tolerance_y = tolerance * math.sin(slope)
    building_envelope.append(Polygon([(p1[0] + tolerance_x, p1[1] + tolerance_y),
                                      (p4[0] + tolerance_x, p4[1] - tolerance_y),
                                      (p4[0] - 2 * tolerance_x, p4[1] - tolerance_y),
                                      (p1[0] - 2 * tolerance_x, p1[1] + tolerance_y)]))

    return building_envelope


def get_orientation(building_envelope, centroid, cardinal_direction):
    orientation = "Intern"
    if building_envelope[1].contains(centroid):
        orientation = cardinal_direction[0]
    elif building_envelope[3].contains(centroid):
        orientation = cardinal_direction[1]
    elif building_envelope[0].contains(centroid):
        orientation = cardinal_direction[2]
    elif building_envelope[2].contains(centroid):
        orientation = cardinal_direction[3]
    return orientation


def get_centroid(ifc_element):
    representation = Element.factory(ifc_element)
    pos_x = representation.position[0]
    pos_y = representation.position[1]
    settings = ifcopenshell.geom.settings()
    shape = ifcopenshell.geom.create_shape(settings, ifc_element)
    vertices = []
    i = 0
    while i < len(shape.geometry.verts):
        vertices.append((shape.geometry.verts[i] + pos_x, shape.geometry.verts[i + 1] + pos_y))
        i += 3
    element_polygon = Polygon(vertices)

    # plt.plot(*wall_polygon.exterior.xy)
    # plt.plot(*wall_polygon.envelope.centroid.xy, marker='o')
    # plt.show()

    return element_polygon.envelope.centroid


def get_natural_position(ifc_element):
    natural_position = ''
    settings = ifcopenshell.geom.settings()
    shape = ifcopenshell.geom.create_shape(settings, ifc_element)
    vertices_xy = []
    vertices_yz = []
    vertices_xz = []
    i = 0
    while i < len(shape.geometry.verts):
        vertices_xy.append(shape.geometry.verts[i:i + 2])
        vertices_yz.append(shape.geometry.verts[i + 1:i + 3])
        vertices_xz.append((shape.geometry.verts[i], shape.geometry.verts[i + 2]))
        i += 3
    area = [Polygon(vertices_xy).envelope.area, Polygon(vertices_yz).envelope.area, Polygon(vertices_xz).envelope.area]
    area_sorted = sorted(area, key=float)
    print("")
    # if (element_polygon_xy.envelope.area > element_polygon_yz.envelope.area) and (element_polygon_xy.envelope.area
    #                                                                               > element_polygon_xz.envelope.area):
    #     natural_position = 'Vertical'
    # elif (element_polygon_yz.envelope.area > element_polygon_xy.envelope.area) and (element_polygon_yz.envelope.area
    #                                                                                 > element_polygon_xz.envelope.area):
    #     natural_position = 'Horizontal'
    # elif (element_polygon_xz.envelope.area > element_polygon_yz.envelope.area) and (element_polygon_xz.envelope.area
    #                                                                                 > element_polygon_xy.envelope.area):
    #     natural_position = 'Horizontal'

    return natural_position


def get_polygon(ifc_element):
    vertices = []
    tolerance = [[0.5, 0.5], [0.5, -0.5], [-0.5, -0.5], [-0.5, 0.5]]
    representation = Element.factory(ifc_element)
    settings = ifcopenshell.geom.settings()
    #point + tolerance
    if 'IfcWindow' in str(ifc_element):
        for i in tolerance:
            i_new = [i[0] + representation.position[0], i[1] + representation.position[1]]
            vertices.append(i_new)
    #polygon
    else:
        shape = ifcopenshell.geom.create_shape(settings, ifc_element)
        i = 0
        while i < len(shape.geometry.verts):
            vertices.append((shape.geometry.verts[i] + representation.position[0],
                             shape.geometry.verts[i + 1] + representation.position[1]))
            i += 3
    vertices2 = list(dict.fromkeys(vertices))
    vertices2.sort(key=lambda tup: tup[0])
    vertices2.append(vertices2[0])

    pol = Polygon(vertices)
    pol2 = Polygon(vertices2)
    plt.plot(*pol.exterior.xy)
    plt.show()
    plt.plot(*pol2.exterior.xy)
    plt.show()
    # return Polygon(vertices).exterior
    return Polygon(vertices)


def get_boundaries(ifc_element):
    # boundaries for a given wall or space element
    vertices = []
    settings = ifcopenshell.geom.settings()
    try:
        shape = ifcopenshell.geom.create_shape(settings, ifc_element)
    except RuntimeError:
        return None
    i = 0
    while i < len(shape.geometry.verts):
        vertices.append([shape.geometry.verts[i], shape.geometry.verts[i + 1]])
        i += 3
    vertices2 = []
    for element in vertices:
        if element not in vertices2:
            vertices2.append(element)

    x, y = zip(*vertices2)

    x = list(x)
    y = list(y)
    x.sort()
    y.sort()
    length = x[len(x)-1]-x[0]
    width = y[len(y)-1]-y[0]

    return length, width


def get_boundaries_vertical_instance(element, thermal_zone):
    sum_ele = []
    length = 0
    width = 0
    settings = ifcopenshell.geom.settings()

    # thermal zone information
    for binding in thermal_zone.ifc.BoundedBy:
        x = []
        y = []
        if binding.RelatedBuildingElement == element.ifc:
            try:
                shape = ifcopenshell.geom.create_shape(settings, binding.ConnectionGeometry.SurfaceOnRelatingElement)
            except RuntimeError:
                continue
            i = 0
            while i < len(shape.verts):
                x.append(shape.verts[i])
                y.append(shape.verts[i + 1])
                i += 3

            x.sort()
            y.sort()
            sum_ele.append([x[len(x) - 1] - x[0], y[len(y) - 1] - y[0]])

    # diferent spaces element
    for a, b in sum_ele:
        length += a
        width += b
    if length == 0 and width == 0:
        return None
    if length <= 0:
        return width
    if width <= 0:
        return length
    return length, width

