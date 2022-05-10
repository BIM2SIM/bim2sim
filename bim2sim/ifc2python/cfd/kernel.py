import trimesh
import ifcopenshell.geom
from OCC.BRepAlgoAPI import BRepAlgoAPI_Common
from OCC.TopAbs import TopAbs_FACE
from OCC.TopExp import TopExp_Explorer
from OCC.TopoDS import topods_Face
from OCC.BRep import BRep_Tool
from OCC.BRepMesh import BRepMesh_IncrementalMesh
from OCC.TopLoc import TopLoc_Location
import numpy as np
import math


# todo test this before merge into master

def filter_ifc_products(model, pc_incl, pc_excl, pg_incl, pg_excl):
    products_guid = []
    for p in model.by_type("IfcProduct"):

        to_be_included = False
        guid = p.GlobalId

        # Filter by classes
        for inc in pc_incl:
            if (p.is_a(inc) is True):
                to_be_included = True
                continue

        if (p.is_a() in pc_excl):
            to_be_included = False

        # Filter by GUID
        if (guid in pg_incl):
            to_be_included = True
        if (guid in pg_excl):
            to_be_included = False

        # Append
        if (to_be_included is True):
            products_guid.append(guid)

    return products_guid


def products_to_breps(model, products_guid, simplify_openings):
    products_guid_brep = {}

    brep_settings = ifcopenshell.geom.settings()
    brep_settings.set(brep_settings.USE_PYTHON_OPENCASCADE, True)
    brep_settings.set(brep_settings.SEW_SHELLS, True)
    brep_settings.set(brep_settings.DISABLE_OPENING_SUBTRACTIONS, False)

    if (simplify_openings is True):
        window_guids = {}  # key: door, value: [opening, wall]
        opening_geoms = {}  # opening: shape
        wall_geoms = {}  # wall: shape
        opening_settings = ifcopenshell.geom.settings()
        opening_settings.set(opening_settings.USE_PYTHON_OPENCASCADE, True)
        opening_settings.set(opening_settings.SEW_SHELLS, True)
        opening_settings.set(opening_settings.DISABLE_OPENING_SUBTRACTIONS, True)

    for g in products_guid:
        p = model.by_guid(g)
        if p.Representation is not None:
            if (p.is_a("IfcSite") or p.is_a("IfcSpace")):
                try:
                    products_guid_brep[g] = ifcopenshell.geom.create_shape(brep_settings, p).geometry
                except:
                    print("ERROR: A shape of the product with the GUID", g, "(", p.is_a(), ") could not be created!")
            else:
                if (simplify_openings is True and p.FillsVoids):

                    opening = p.FillsVoids[0].RelatingOpeningElement
                    wall = opening.VoidsElements[0].RelatingBuildingElement
                    window_guids[g] = [opening.GlobalId, wall.GlobalId]

                    shp_opening = ifcopenshell.geom.create_shape(opening_settings, opening).geometry
                    opening_geoms[opening.GlobalId] = shp_opening

                    if (wall.GlobalId not in wall_geoms):
                        shp_wall = ifcopenshell.geom.create_shape(opening_settings, wall).geometry
                        wall_geoms[wall.GlobalId] = shp_wall

                else:
                    try:
                        products_guid_brep[g] = ifcopenshell.geom.create_shape(brep_settings, p).geometry
                    except:
                        print("ERROR: A shape of the product with the GUID", g, "(", p.is_a(), ") could not be created!")

    if (simplify_openings is True):

        for key, value in list(window_guids.items()):
            products_guid_brep[key] = BRepAlgoAPI_Common(opening_geoms[value[0]], wall_geoms[value[1]]).Shape()

    return products_guid_brep


def breps_to_meshes(products_guid_brep, deflection_tolerance):
    products_guid_mesh = {}

    for key, value in list(products_guid_brep.items()):
        vts, fac = triangluate_shape(value, deflection_tolerance)
        products_guid_mesh[key] = [vts, fac]

    return products_guid_mesh


def triangluate_shape(s, deflection_tolerance):
    vertices = []
    faces = []

    BRepMesh_IncrementalMesh(s, deflection_tolerance, False, deflection_tolerance, True)

    ex = TopExp_Explorer(s, TopAbs_FACE)

    while ex.More():

        OF = topods_Face(ex.Current())
        L = TopLoc_Location()
        # das ...
        # mesh = (BRep_Tool().Triangulation(OF, L))
        # oder das ...
        mesh_handle = (BRep_Tool().Triangulation(OF, L))
        mesh = mesh_handle.GetObject()
        #

        tri = mesh.Triangles()
        nodes = mesh.Nodes()
        number_of_triangles = mesh.NbTriangles()

        for i in range(1, number_of_triangles + 1):
            trian = tri.Value(i)  # get pointer on triangle
            i1, i2, i3 = trian.Get()  # get indizes of vertices building the triangle

            p1 = nodes.Value(i1).Transformed(L.Transformation())  # get gp_pnt of vertices
            p2 = nodes.Value(i2).Transformed(L.Transformation())
            p3 = nodes.Value(i3).Transformed(L.Transformation())

            vertices.append([p1.X(), p1.Y(), p1.Z()])
            vertices.append([p2.X(), p2.Y(), p2.Z()])
            vertices.append([p3.X(), p3.Y(), p3.Z()])

            l = len(vertices)

            faces.append([l - 3, l - 2, l - 1])

        ex.Next()

    return vertices, faces


def create_obbs(products_guid_mesh):
    for key, value in list(products_guid_mesh.items()):
        mesh = trimesh.Trimesh(vertices=value[0], faces=value[1], validate=True, process=True)
        obb = mesh.convex_hull
        # obb = mesh.bounding_box_oriented
        products_guid_mesh[key] = [obb.vertices, obb.faces]


def create_building_mesh(products_guid_mesh):
    building_vertices = []
    building_faces = []
    building_attr_guid = []

    for key, value in list(products_guid_mesh.items()):
        k = len(building_vertices)
        building_vertices.extend(value[0])

        for t in value[1]:
            building_faces.append([t[0] + k, t[1] + k, t[2] + k])
            building_attr_guid.append(key)

    building_vertices = np.asarray(building_vertices)
    building_faces = np.asarray(building_faces)
    building_attr_guid = np.asarray(building_attr_guid)
    building_attr_guid_dict = {'guid': building_attr_guid}

    return trimesh.Trimesh(vertices=building_vertices, faces=building_faces, face_attributes=building_attr_guid_dict, validate=True, process=True)


def write_bof_file(building_mesh, filename, round_digits):
    w = open(filename + '.bof', 'w')
    w.write("BOF\n")
    w.write("#File Format BOF (BIM Octree Fileformat)\n")
    w.write("ascii\n")
    w.write(str(len(building_mesh.vertices)) + " " + str(len(building_mesh.faces)) + "\n")
    for v in building_mesh.vertices:
        w.write(str(round(v[0], round_digits)) + " " + str(round(v[1], round_digits)) + " " + str(round(v[2], round_digits)) + "\n")
    for i, f in enumerate(building_mesh.faces):
        w.write(str(f[0]) + " " + str(f[1]) + " " + str(f[2]) + " " + str(building_mesh.face_attributes["guid"][i]) + "\n")
    w.close()


def get_octree_level_by_minimal_width(msh, dmin):
    bounds = msh.bounds
    max_width = max(bounds[1][0] - bounds[0][0], bounds[1][1] - bounds[0][1], bounds[1][2] - bounds[0][2])
    return math.ceil(math.log2(max_width / dmin))


def visualize_products(building_mesh):
    vis = {}
    for f in range(0, len(building_mesh.faces)):
        guid = building_mesh.face_attributes['guid'][f]
        #   if(guid!='1zOBw0Gej5Wf0QAJfHnOc0'):
        #     continue
        if (guid in vis):
            building_mesh.visual.face_colors[f] = vis[guid]
        else:
            vis[guid] = trimesh.visual.color.random_color()
            building_mesh.visual.face_colors[f] = vis[guid]
    building_mesh.show(smooth=False)


def print_architecture():
    print("\nOS:\t\t\t", ifcopenshell.platform_system, ifcopenshell.platform_architecture)
    print("Python:\t\t", ifcopenshell.python_version_tuple, ifcopenshell.python_distribution)
    print("IfcOpenShell:", ifcopenshell.version, "\n")
