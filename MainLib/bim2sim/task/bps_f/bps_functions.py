import ifcopenshell
import ifcopenshell.geom


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
    for binding in thermal_zone.ifc.BoundedBy:
        x = []
        y = []
        z = []
        if binding.RelatedBuildingElement == element.ifc:
            try:
                shape = ifcopenshell.geom.create_shape(settings, binding.ConnectionGeometry.SurfaceOnRelatingElement)
            except RuntimeError:
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
    for binding in thermal_zone.ifc.BoundedBy:
        if binding.RelatedBuildingElement == element.ifc:
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



