import ifcopenshell
import ifcopenshell.geom
import math
import re

from googletrans import Translator


def get_disaggregations_instance(element, thermal_zone):
    """get all posible disaggregation of an instance, based on the IfcRelSpaceBoundary,
    return the disagreggation, area and relative position of it.
    if takes into account if the instances is vertical or horizontal"""

    vertical_instances = ['Wall', 'InnerWall', 'OuterWall']
    horizontal_instances = ['Roof', 'Floor', 'GroundFloor']

    # elements that doesnt apply for a disaggregation
    if element.__class__.__name__ not in vertical_instances and element.__class__.__name__ not in horizontal_instances:
        return None

    disaggregations = {}
    settings = ifcopenshell.geom.settings()

    # thermal zone information
    dis_counter = 0
    for binding in element.ifc.ProvidesBoundaries:
        x, y, z = [], [], []
        # find just the disaggregation that corresponds the space
        if binding.RelatingSpace == thermal_zone.ifc:
            try:
                shape = ifcopenshell.geom.create_shape(settings, binding.ConnectionGeometry.SurfaceOnRelatingElement)
            except RuntimeError:
                try:
                    shape = ifcopenshell.geom.create_shape(settings,
                                                           binding.ConnectionGeometry.SurfaceOnRelatingElement.BasisSurface)
                except RuntimeError:
                    element.logger.warning("Found no geometric information for %s in %s" % (element.name, thermal_zone.name))
                    continue
            # get relative position of resultant disaggregation
            if hasattr(binding.ConnectionGeometry.SurfaceOnRelatingElement, 'BasisSurface'):
                pos = binding.ConnectionGeometry.SurfaceOnRelatingElement.BasisSurface.Position.Location.Coordinates
            else:
                pos = binding.ConnectionGeometry.SurfaceOnRelatingElement.Position.Location.Coordinates

            i = 0
            while i < len(shape.verts):
                x.append(shape.verts[i])
                y.append(shape.verts[i + 1])
                z.append(shape.verts[i + 2])
                i += 3

            x.sort()
            y.sort()
            z.sort()

            try:
                x = x[len(x) - 1] - x[0]
                y = y[len(y) - 1] - y[0]
                z = z[len(z) - 1] - z[0]
            except IndexError:
                continue

            coordinates = [x, y, z]

            # filter for vertical or horizontal instance -> gets area properly
            if element.__class__.__name__ in vertical_instances:
                for a in coordinates:
                    if a <= 0:
                        del coordinates[coordinates.index(a)]
            elif element.__class__.__name__ in horizontal_instances:
                del coordinates[2]

            # returns disaggregation, area and relative position
            disaggregations['disaggregation_%d' % dis_counter] = [coordinates[0]*coordinates[1], pos]
            dis_counter += 1

    if len(disaggregations) == 0:
        return None

    return disaggregations


def orientation_verification(instance):
    supported_classes = {'Window', 'OuterWall', 'Door'}
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


def get_matches_list(search_words, search_list, transl=True):
    """get patterns for a material name in both english and original language,
    and get afterwards the related elements from list"""

    translator = Translator()
    material_ref = []

    pattern_material = re.sub('[!@#$-_1234567890]', '', search_words.lower()).split()
    if transl:
        pattern_material.extend(translator.translate(re.sub('[!@#$-_1234567890]', '', search_words.lower())).text.split())

    for i in pattern_material:
        material_ref.append(re.compile('(.*?)%s' % i, flags=re.IGNORECASE))

    material_options = []
    for ref in material_ref:
        for mat in search_list:
            if ref.match(mat):
                if mat not in material_options:
                    material_options.append(mat)

    return material_options





