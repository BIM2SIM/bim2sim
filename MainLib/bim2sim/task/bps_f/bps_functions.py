import ifcopenshell
import ifcopenshell.geom
import math
import re
import json
import translators as ts

from bim2sim.enrichment_data.data_class import DataClass
from bim2sim.decision import ListDecision, RealDecision
from teaser.data.input import inputdata


def get_disaggregations_instance(element, thermal_zone):
    """get all posible disaggregation of an instance, based on the IfcRelSpaceBoundary,
    return the disagreggation, area and relative position of it.
    if takes into account if the instances is vertical or horizontal"""

    vertical_instances = ['Wall', 'InnerWall', 'OuterWall']
    horizontal_instances = ['Roof', 'Floor', 'GroundFloor']

    # elements who doesnt apply for a disaggregation
    if type(element).__name__ not in vertical_instances+horizontal_instances:
        return None

    disaggregations = {}
    settings = ifcopenshell.geom.settings()

    # thermal zone information
    dis_counter = 0
    for binding in element.ifc.ProvidesBoundaries:
        x, y, z = [], [], []
        # find just the disaggregation that corresponds the space
        if binding.RelatingSpace == thermal_zone.ifc:
            # gets geometrical intersection area between space and element
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
            if len(shape.verts) > 0:
                while i < len(shape.verts):
                    x.append(shape.verts[i])
                    y.append(shape.verts[i + 1])
                    z.append(shape.verts[i + 2])
                    i += 3
            else:
                for point in binding.ConnectionGeometry.SurfaceOnRelatingElement.OuterBoundary.Points:
                    x.append(point.Coordinates[0])
                    y.append(point.Coordinates[1])
                    z.append(0)

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
            elif type(element).__name__ in horizontal_instances:
                del coordinates[2]

            # returns disaggregation, area and relative position
            disaggregations['disaggregation_%d' % dis_counter] = [coordinates[0]*coordinates[1], pos]
            dis_counter += 1

    if len(disaggregations) == 0:
        return None

    return disaggregations

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

    material_ref = []

    if type(search_words) is str:
        pattern_material = re.sub('[!@#$-_1234567890]', '', search_words.lower()).split()
        if transl:
            # use of yandex, bing--- https://pypi.org/project/translators/#features
            pattern_material.extend(ts.bing(re.sub('[!@#$-_1234567890]', '', search_words.lower())).split())

        for i in pattern_material:
            material_ref.append(re.compile('(.*?)%s' % i, flags=re.IGNORECASE))

    material_options = []
    for ref in material_ref:
        for mat in search_list:
            if ref.match(mat):
                if mat not in material_options:
                    material_options.append(mat)

    return material_options


def get_material_templates_resumed(name, tc_range):
    material_templates = dict(DataClass(used_param=2).element_bind)
    del material_templates['version']

    resumed = {}
    for k in material_templates:
        if tc_range is not None:
            if tc_range[0] < material_templates[k][name] < tc_range[1]:
                resumed[material_templates[k]['name']] = material_templates[k]
        else:
            resumed[material_templates[k]['name']] = material_templates[k]

    return resumed


def get_material_value_templates_resumed(name, tc_range=None):
    material_templates = dict(DataClass(used_param=2).element_bind)
    del material_templates['version']

    resumed = {}
    for k in material_templates:
        if tc_range is not None:
            if tc_range[0] < material_templates[k][name] < tc_range[1]:
                resumed[material_templates[k]['name']] = material_templates[k][name]
        else:
            resumed[material_templates[k]['name']] = material_templates[k][name]
    return resumed


def real_decision_user_input(bind, name):
    material = bind.material
    decision2 = RealDecision("Enter value for the parameter %s" % name,
                             global_key="%s" % name,
                             allow_skip=False, allow_load=True, allow_save=True,
                             collect=False, quick_decide=False)
    decision2.decide()
    if material not in bind.material_selected:
        bind.material_selected[material] = {}
    bind.material_selected[material][name] = decision2.value

    return decision2.value


def filter_instances(instances, type_name):
    """Filters the inspected instances by type name (e.g. Wall) and
    returns them as list"""
    instances_filtered = []
    if type(instances) is dict:
        list_instances = instances.values()
    else:
        list_instances = instances
    for instance in list_instances:
        if type_name in type(instance).__name__:
            instances_filtered.append(instance)
    return instances_filtered


def get_pattern_usage():
    """get usage patterns to use it on the thermal zones get_usage"""
    use_conditions_path = inputdata.__file__.replace('__init__.py', '') + 'UseConditions.json'
    with open(use_conditions_path, 'r+') as f:
        use_conditions = list(json.load(f).keys())
        use_conditions.remove('version')

    common_translations = {
        'Single office': ['Office'],
        'Group Office (between 2 and 6 employees)': ['Office'],
        'Open-plan Office (7 or more employees)': ['Office'],
        'Kitchen in non-residential buildings': ['Kitchen'],
        'Kitchen - preparations, storage': ['Kitchen'],
        'Traffic area': ['Hall'],
        'WC and sanitary rooms in non-residential buildings': ['bath', 'bathroom', 'WC', 'Toilet'],
        'Stock, technical equipment, archives': ['Technical room']
    }

    pattern_usage_teaser = {}
    for i in use_conditions:
        pattern_usage_teaser[i] = []
        list_engl = re.sub('\((.*?)\)', '', i).replace(' - ', ', ').replace(' and ', ', ').replace(' in ', ', ')\
            .replace(' with ', ', ').replace(' or ', ', ').replace(' the ', ' ').split(', ')
        for i_eng in list_engl:
            new_i_eng = i_eng.replace(' ', '(.*?)')
            pattern_usage_teaser[i].append(re.compile('(.*?)%s' % new_i_eng, flags=re.IGNORECASE))
            if i in common_translations:
                for c_trans in common_translations[i]:
                    pattern_usage_teaser[i].append(re.compile('(.*?)%s' % c_trans, flags=re.IGNORECASE))
    return pattern_usage_teaser
