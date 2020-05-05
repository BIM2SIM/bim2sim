import ifcopenshell
import ifcopenshell.geom
import math


def get_boundaries(ifc_element):
    # boundaries for a given wall or space element
    vertices = []
    settings = ifcopenshell.geom.settings()
    try:
        shape = ifcopenshell.geom.create_shape(settings, ifc_element)
    except RuntimeError:
        return 0, 0
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


def get_disaggregations_instance(element, thermal_zone):
    vertical_instances = ['Wall', 'InnerWall', 'OuterWall']
    horizontal_instances = ['Roof', 'Floor', 'GroundFloor']

    if element.__class__.__name__ not in vertical_instances and element.__class__.__name__ not in horizontal_instances:
        return None

    disaggregations = {}
    settings = ifcopenshell.geom.settings()

    # thermal zone information
    dis = 0
    for binding in element.ifc.ProvidesBoundaries:
        x = []
        y = []
        z = []
        if binding.RelatingSpace == thermal_zone.ifc:
            try:
                shape = ifcopenshell.geom.create_shape(settings, binding.ConnectionGeometry.SurfaceOnRelatingElement)
            except RuntimeError:
                element.logger.warning("Found no geometric information for %s in %s" % (element.name, thermal_zone.name))
                continue
            i = 0
            while i < len(shape.verts):
                x.append(shape.verts[i])
                y.append(shape.verts[i + 1])
                z.append(shape.verts[i + 2])
                i += 3

            x.sort()
            y.sort()
            z.sort()
            disaggregations['disaggregation_%d' % dis] = [x[len(x) - 1] - x[0], y[len(y) - 1] - y[0], z[len(z) - 1] - z[0]]
            dis += 1

    # diferent spaces element
    if element.__class__.__name__ in vertical_instances:
        for a in disaggregations:
            for b in disaggregations[a]:
                if b <= 0:
                    del disaggregations[a][disaggregations[a].index(b)]
    elif element.__class__.__name__ in horizontal_instances:
        for a in disaggregations:
            del disaggregations[a][2]
    if len(disaggregations) == 0:
        return None
    return disaggregations


def get_position_instance(element, thermal_zone):
    positions = []
    settings = ifcopenshell.geom.settings()

    # thermal zone information
    for binding in element.ifc.ProvidesBoundaries:
    # for binding in thermal_zone.ifc.BoundedBy:
        if binding.RelatingSpace == thermal_zone.ifc:
        # if binding.RelatedBuildingElement == element.ifc:
            try:
                ifcopenshell.geom.create_shape(settings, binding.ConnectionGeometry.SurfaceOnRelatingElement)
            except RuntimeError:
                continue
            if hasattr(binding.ConnectionGeometry.SurfaceOnRelatingElement, 'BasisSurface'):
                pos = binding.ConnectionGeometry.SurfaceOnRelatingElement.BasisSurface.Position.Location.Coordinates
            else:
                pos = binding.ConnectionGeometry.SurfaceOnRelatingElement.Position.Location.Coordinates
            positions.append(pos)

    return positions


def orientation_verification(instance):
    supported_classes = {'Window', 'OuterWall'}
    if instance.__class__.__name__ in supported_classes:
        if len(instance.thermal_zones) > 0:
            bo_spaces = {}
            boundaries1 = {}
            for i in instance.ifc.ProvidesBoundaries:
                rel_vector_space = i.ConnectionGeometry.SurfaceOnRelatingElement.\
                    BasisSurface.Position.Axis.DirectionRatios
                rel_angle_space = vector_angle(rel_vector_space)
                boundaries1[i.RelatingSpace.Name] = rel_angle_space
            for i in instance.thermal_zones:
                bo_spaces[i.name] = i.orientation
            new_angles = []
            for i in bo_spaces:
                new_angles.append(bo_spaces[i] + boundaries1[i]-180)
            # can't determine a possible new angle (very rare case)
            if len(set(new_angles)) > 1:
                return None
            # no true north necessary
            new_angle = angle_equivalent(new_angles[0])
            # new angle return
            if new_angle - instance.orientation > 0.1:
                return new_angle
        else:
            instance.logger.warning('No space relation for %s found' % instance.name)
            return None
    # not relevant for internal instances
    else:
        return None


def angle_equivalent(angle):
    while angle >= 360 or angle < 0:
        if angle >= 360:
            angle -= 360
        elif angle < 0:
            angle += 360
    return angle


def vector_angle(vector):
    x = vector[0]
    y = vector[1]
    try:
        tang = math.degrees(math.atan(x / y))
    except ZeroDivisionError:
        if x > 0:
            return 90
        elif x < 0:
            return 270
        else:
            return 0
    if x >= 0:
        # quadrant 1
        if y > 0:
            return tang
        # quadrant 2
        else:
            return tang + 180
    else:
        # quadrant 3
        if y < 0:
            return tang + 180
        # quadrant 4
        else:
            return tang + 360






