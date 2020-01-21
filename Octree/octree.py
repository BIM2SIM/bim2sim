from octree_kernel import *
from timeit import default_timer as timer
import os

filename = "AC-20-Smiley-West-10-Bldg"
simplify_openings = True
use_obb = False
deflection_tolerance = 1.0e-1
product_classes_include = ["IfcProduct"]
product_classes_exclude = ["IfcAnnotation", "IfcOpeningElement", "IfcSpace", "IfcSite"]
product_guid_include = []
product_guid_exclude = []

print_architecture()

total_start = timer()

##################################################################################################################################################################
print("### Open IFC file. ###")
model = ifcopenshell.open(filename + ".ifc")
##################################################################################################################################################################


##################################################################################################################################################################
print("### Filter products. ###")
products_guid = filter_ifc_products(model, product_classes_include, product_classes_exclude, product_guid_include, product_guid_exclude)
##################################################################################################################################################################


##################################################################################################################################################################
print("### Create breps. ###")
start = timer()
products_guid_brep = products_to_breps(model=model, products_guid=products_guid, simplify_openings=simplify_openings)
print("... Needed processing time (s):", timer() - start)
##################################################################################################################################################################


##################################################################################################################################################################
print("### Create meshes. ###")
start = timer()
products_guid_mesh = breps_to_meshes(products_guid_brep=products_guid_brep, deflection_tolerance=deflection_tolerance)
print("... Needed processing time (s):", timer() - start)
# disp = []
# for key, value in list(products_guid_mesh.items()):
#     disp.append(trimesh.Trimesh(vertices=value[0], faces=value[1], validate=True, process=True))
# scene = trimesh.scene.Scene(disp)
# scene.show()
##################################################################################################################################################################


##################################################################################################################################################################
if use_obb:
    print("### Simplify meshes. ###")
    create_obbs(products_guid_mesh)
##################################################################################################################################################################


##################################################################################################################################################################
print("### Create building mesh and export. ###")
start = timer()
building_mesh = create_building_mesh(products_guid_mesh)
building_mesh.export(filename + '.stl')
write_bof_file(building_mesh, filename, 6)
print("... Needed processing time (s):", timer() - start)
# visualize_products(building_mesh)
##################################################################################################################################################################


##################################################################################################################################################################
print("### Generate Octree. ###")
start = timer()
filetype = ".bof"  # .bof or .stl
if filetype == ".stl":
    result_file = "Faces_Index.txt"
else:
    result_file = "Faces_Guid.txt"
write_vtk = True
dmin = 0.15
max_depth = get_octree_level_by_minimal_width(building_mesh, dmin)
if (max_depth > 10):
    max_depth = 10
# max_depth = 10
path_cpp = "."
octree = os.system(path_cpp + "/VisGeomLinux " + filename + filetype + " " + str(max_depth) + " " + str(int(write_vtk)))
if octree == 0:
    print("Octree done.")
print("... Needed processing time (s):", timer() - start)
##################################################################################################################################################################


##################################################################################################################################################################
print("### Define facade guids. ###")
start = timer()
facade_guids = []
with open(path_cpp + "/" + result_file) as fp:
    line = fp.readline()
    while line:
        # print(line.strip())
        if filetype == ".stl":
            idx = int(line.strip())
            facade_guids.append(building_mesh.face_attributes["guid"][idx])
        else:
            guid = line.strip()
            facade_guids.append(guid)
        line = fp.readline()
fp.close()

facade_guids = list(set(facade_guids))

# delete facade_guids
os.remove(path_cpp + "/" + result_file)

building_mesh.visual.face_colors = [0, 0, 255, 255]
for f in range(0, len(building_mesh.faces)):
    guid = building_mesh.face_attributes['guid'][f]
    if (guid in facade_guids):
        building_mesh.visual.face_colors[f] = [0, 255, 0, 255]
    else:
        building_mesh.visual.face_colors[f] = [255, 0, 0, 255]
building_mesh.show(smooth=False)
print("... Needed processing time (s):", timer() - start)

# TODO write isExternal information back to ifc file
print("Finish script... Needed processing time (s):", timer() - total_start)
##################################################################################################################################################################
