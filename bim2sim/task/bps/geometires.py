import ifcopenshell
import ifcopenshell.geom
from pathlib import Path
import contextlib
import ifcopenshell.util.element
import ifcopenshell.util.classification
import ifcopenshell.util.placement
import ifcopenshell.util.unit


class geometry():

    def __init__(self, ifc_file):
        self.model = ifcopenshell.open(ifc_file)

    def wall_types(self):
        for wall_type in self.model.by_type("IfcWallType"):
            print("The wall type element is", wall_type)
            print("The name of the wall type is", wall_type.Name)

    def door_types(self):
        for door_type in self.model.by_type("IfcDoorType"):
            print("The door type is", door_type.Name)
            doors = ifcopenshell.util.element.get_type(door_type)
            if doors is not None:
                print(f"There are {len(doors)} of this type")
                for door in doors:
                    print("The door name is", door.Name)

    def type_wall(self):
        walls = self.model.by_type("IfcWall")
        for wall in walls:
            wall_type = ifcopenshell.util.element.get_type(wall)
            print(f"The wall type of {wall.Name} is {wall_type.Name}")

    def properties_wall(self):
        walls = self.model.by_type("IfcWall")[0]
        wall_type = ifcopenshell.util.element.get_type(walls)
        print(wall_type)

        """for wall in walls:
            wall_type = ifcopenshell.util.element.get_type(wall)
            print(wall_type)"""
    def container_name(self):
        walls = self.model.by_type("IfcWall")
        for wall in walls:
            # Walls are typically located on a storey, equipment might be located in spaces, etc
            container = ifcopenshell.util.element.get_container(wall)
            # The wall is located on Level 01
            print(f"The wall is located on {container.Name}")

    def element_container(self):
        #for storey in self.model.by_type("IfcBuildingStorey"):
        for storey in self.model.by_type("IfcSpace"):
            elements = ifcopenshell.util.element.get_decomposition(storey)
            print(f"There are {len(elements)} located on storey {storey.Name}, they are:")
            for element in elements:
                print(element.Name)


    def _get_info(self):
        products = self.model.by_type("IfcProduct")
        obj_info = products[0].get_info()
        print(obj_info.keys())

    def get_coordiantes_space(self):
        rooms = self.model.by_type("IfcSpace")
        _dict = {}
        for room in rooms:
            # array([[ 1.00000000e+00,  0.00000000e+00,  0.00000000e+00, 2.00000000e+00],
            #        [ 0.00000000e+00,  1.00000000e+00,  0.00000000e+00, 3.00000000e+00],
            #        [ 0.00000000e+00,  0.00000000e+00,  1.00000000e+00, 5.00000000e+00],
            #        [ 0.00000000e+00,  0.00000000e+00,  0.00000000e+00, 1.00000000e+00]])
            matrix = ifcopenshell.util.placement.get_local_placement(room.ObjectPlacement)
            if room.LongName == "Schlafzimmer":
                print(matrix[:, 3][:3])
                print(matrix)
                #print(room.Geometry)

            # t = ifcopenshell.util.placement.get_storey_elevation(wall.IfcBuildingStorey)
            # The last column holds the XYZ values, such as:
            # array([ 2.00000000e+00,  3.00000000e+00,  5.00000000e+00])
            #print(matrix[:, 3][:3])
            _dict[room.Name] = (room.LongName, matrix[:, 3][:3])

    def choose_next_wall_element(self):
        rooms = self.model.by_type("IfcSpace")
        for room in rooms:
            if room.LongName == "Bad":
                print(type(room))


        pass

    def calculate_length(self):
        pass

    def get_coordinates(self):
        #walls = self.model.by_type("IfcWall")
        walls = self.model.by_type("IfcSpace")
        for wall in walls:
            print(wall)
            # array([[ 1.00000000e+00,  0.00000000e+00,  0.00000000e+00, 2.00000000e+00],
            #        [ 0.00000000e+00,  1.00000000e+00,  0.00000000e+00, 3.00000000e+00],
            #        [ 0.00000000e+00,  0.00000000e+00,  1.00000000e+00, 5.00000000e+00],
            #        [ 0.00000000e+00,  0.00000000e+00,  0.00000000e+00, 1.00000000e+00]])
            matrix = ifcopenshell.util.placement.get_local_placement(wall.ObjectPlacement)
            #t = ifcopenshell.util.placement.get_storey_elevation(wall.IfcBuildingStorey)
            # The last column holds the XYZ values, such as:
            # array([ 2.00000000e+00,  3.00000000e+00,  5.00000000e+00])
            print(matrix[:, 3][:3])

    def get_classification(self):
        walls = self.model.by_type("IfcWall")
        for wall in walls:
            # Elements may have multiple classification references assigned
            references = ifcopenshell.util.classification.get_references(wall)
            for reference in references:
                # A reference code might be Pr_30_59_99_02
                print("The wall has a classification reference of", reference[1])
                # A system might be Uniclass 2015
                system = ifcopenshell.util.classification.get_classification(reference)
                print("This reference is part of the system", system.Name)


    def _get_pipe(self):
        pipes = self.model.by_type("IfcPipeSegment")
        print(pipes)
        for pipe in pipes:
            # Elements may be assigned to multiple systems simultaneously, such as electrical, hydraulic, etc
            systems = ifcopenshell.util.system.get_element_systems(pipe)
            for system in systems:
                # For example, it might be part of a Chilled Water system
                print("This pipe is part of the system", system.Name)

    def full_geometry(self):
        elements = self.model.by_type('IfcWall')
        settings = ifcopenshell.geom.settings()
        for element in elements:
            shape = ifcopenshell.geom.create_shape(settings, element)

            # The GUID of the element we processed
            print(shape.guid)

            # The ID of the element we processed
            print(shape.id)

            # The element we are processing
            print(self.model.by_guid(shape.guid))

            # A unique geometry ID, useful to check whether or not two geometries are
            # identical for caching and reuse. The naming scheme is:
            # IfcShapeRepresentation.id{-layerset-LayerSet.id}{-material-Material.id}{-openings-[Opening n.id ...]}{-world-coords}
            # print(shape.geometry.id())

            # A 4x4 matrix representing the location and rotation of the element, in the form:
            # [ [ x_x, y_x, z_x, x   ]
            #   [ x_y, y_y, z_y, y   ]
            #   [ x_z, y_z, z_z, z   ]
            #   [ 0.0, 0.0, 0.0, 1.0 ] ]
            # The position is given by the last column: (x, y, z)
            # The rotation is described by the first three columns, by explicitly specifying the local X, Y, Z axes.
            # The first column is a normalised vector of the local X axis: (x_x, x_y, x_z)
            # The second column is a normalised vector of the local Y axis: (y_x, y_y, y_z)
            # The third column is a normalised vector of the local Z axis: (z_x, z_y, z_z)
            # The axes follow a right-handed coordinate system.
            # Objects are never scaled, so the scale factor of the matrix is always 1.
            matrix = shape.transformation.matrix.data

            # Indices of vertices per triangle face e.g. [f1v1, f1v2, f1v3, f2v1, f2v2, f2v3, ...]
            faces = shape.geometry.faces

            # Indices of vertices per edge e.g. [e1v1, e1v2, e2v1, e2v2, ...]
            edges = shape.geometry.edges

            # X Y Z of vertices in flattened list e.g. [v1x, v1y, v1z, v2x, v2y, v2z, ...]
            verts = shape.geometry.verts

            # Since the lists are flattened, you may prefer to group them like so depending on your geometry kernel
            grouped_verts = [[verts[i], verts[i + 1], verts[i + 2]] for i in range(0, len(verts), 3)]
            grouped_edges = [[edges[i], edges[i + 1]] for i in range(0, len(edges), 2)]
            grouped_faces = [[faces[i], faces[i + 1], faces[i + 2]] for i in range(0, len(faces), 3)]

            # A list of styles that are relevant to this shape
            styles = shape.geometry.materials

            for style in styles:
                # Each style is named after the entity class if a default
                # material is applied. Otherwise, it is named "surface-style-{SurfaceStyle.name}"
                # All non-alphanumeric characters are replaced with a "-".
                print(style.original_name())

                # A more human readable name
                print(style.name)

                # Each style may have diffuse colour RGB codes
                if style.has_diffuse:
                    print(style.diffuse)

                # Each style may have transparency data
                if style.has_transparency:
                    print(style.transparency)

            # Indices of material applied per triangle face e.g. [f1m, f2m, ...]
            material_ids = shape.geometry.material_ids

    def opencascade(self):
        elements = self.model.by_type('IfcWall')

        settings = ifcopenshell.geom.settings()
        settings.set(settings.USE_PYTHON_OPENCASCADE, True)
        for element in elements:
            try:
                shape = ifcopenshell.geom.create_shape(settings, element)
                geometry = shape.geometry  # see #1124
                # These are methods of the TopoDS_Shape class from pythonOCC
                shape_gpXYZ = geometry.Location().Transformation().TranslationPart()
                # These are methods of the gpXYZ class from pythonOCC
                print(shape_gpXYZ.X(), shape_gpXYZ.Y(), shape_gpXYZ.Z())
            except:
                print("Shape creation failed")

    def _create_offset(self, dx):
        x = 0
        x = dx + x
        #y = dy + y

    def coordiante_transformation(self):
        site = self.model.by_type('IFCSite')[0]
        site.ObjectPlacement.RelativePlacement.Location.Coordinates = (-4.040, -5.990, 0.000)
        self.model.write("C:/02_Masterarbeit/08_BIMVision//FZK-Haus_new.ifc")
        print(site)


    def _get_rooms(self):
        # IFC-Modell laden
        # Räume filtern
        rooms = self.model.by_type("IfcSpace")
        # Liste von Raumnamen erstellen
        #room_names = [room.LongName for room in rooms]
        for room in rooms:
            print(f"Raumname: {room.Name} , {room.LongName}, Raum-ID: {room.id()}")
            roo = self.model.by_id(room.id())
            # Wenn der Raum gefunden wurde, versuchen Sie, die Abmessungen aus den Attributen zu berechnen
            if roo is not None and hasattr(roo, "Width") and hasattr(roo, "Length") and hasattr(roo, "Height"):
                width = roo.Width
                length = roo.Length
                height = roo.Height
                print(f"Der Raum mit der ID {room.id()} hat die Abmessungen {width}m x {length}m x {height}m.")
            else:
                print(f"Der Raum mit der ID {room.id()} konnte nicht gefunden oder hat keine Abmessungen.")


    def room_coordiantes(self):
        room_id = 21283
        room = self.model.by_id(room_id)
        room_geometry = None
        for rel in room.IsDecomposedBy:
            if isinstance(rel.RelatingObject,
                          ifcopenshell.file.entity_instance._entity_instance) and rel.RelatingObject.is_a(
                    "IfcProductDefinitionShape"):
                for rep in rel.RelatingObject.Representations:
                    if isinstance(rep, ifcopenshell.file.entity_instance._entity_instance) and rep.is_a(
                            "IfcShapeRepresentation"):
                        if rep.RepresentationType == "Brep":
                            room_geometry = rep.Items[0]
                            break
                break

        if room_geometry is None:
            print(f"Keine Geometrie gefunden für den Raum mit ID {room_id}")
        else:
            # Raummaße berechnen
            room_dimensions = [abs(coord_max - coord_min) for coord_max, coord_min in
                               zip(room_geometry.Bounds[3:], room_geometry.Bounds[:3])]
            # Ausgabe der Raummaße
            print(f"Raumabmessungen des Raums mit ID {room_id}: {room_dimensions}")



    def room_dimension(self):
        room_id = 21283
        room = self.model.by_id(room_id)
        # Find the space object by its name
        #object = self.model.by_type("IfcFacetedBrep")[0]
        print(room.IfcProductDefinitionShape)
        for l in room:
            print(l)
        # Get the volume of the object
        volume = object.Volume

        # Calculate the linear dimensions from the volume
        length = volume ** (1 / 3)
        width = length
        height = length

        # Print the dimensions
        print(f"Object dimensions: {length}m x {width}m x {height}m")


        space_name = "Bad"
        space_object = self.model.by_type("IfcSpace")[0]
        print(space_object)

        # Get the space bounding box
        bounds = space_object.Representation.Representations[0].Items[0].BoundingBox

        # Calculate the space dimensions
        length = bounds[3] - bounds[0]
        width = bounds[4] - bounds[1]
        height = bounds[5] - bounds[2]

        # Print the dimensions
        print(f"Space dimensions: {length}m x {width}m x {height}m")
        """if room is not None:
            # Abrufen der globalen ID des Raums
            global_id = room.GlobalId
            print(f"Die globale ID des Raums mit der ID {room_id} lautet {global_id}")

            # Abrufen der Platzierung des Raums
            placement = room.ObjectPlacement
            print(f"Die Platzierung des Raums mit der ID {room_id} lautet {placement}")

            # Abrufen der Darstellung des Raums
            representation = room.Representation
            print(f"Die Darstellung des Raums mit der ID {room_id} lautet {representation}")

            # Abrufen der Geometrie des Raums aus der Darstellung
            shape = ifcopenshell.geom.create_shape(room, representation)

            # Wenn eine Geometrie gefunden wurde, berechnen Sie die Abmessungen des Raums aus der Geometrie
            if shape is not None:
                bounds = ifcopenshell.geom.specific_3d_bounding_box(shape)
                width = bounds[0][1] - bounds[0][0]
                length = bounds[1][1] - bounds[1][0]
                height = bounds[2][1] - bounds[2][0]
                print(f"Der Raum mit der ID {room_id} hat die Abmessungen {width}m x {length}m x {height}m.")
            else:
                print(f"Für den Raum mit der ID {room_id} konnte keine Geometrie gefunden werden.")
        else:
            print(f"Der Raum mit der ID {room_id} konnte nicht gefunden werden.")"""



if __name__ == '__main__':
    ifc_path = Path(__file__).parent.parent.parent \
               / 'assets/ifc_example_files/AC20-FZK-Haus.ifc'
    #ifc_path = f'C:/02_Masterarbeit/08_BIMVision/FZK-Haus.ifc'
    ifc_path = "C:/02_Masterarbeit/08_BIMVision//FZK-Haus_new.ifc"
    geo = geometry(ifc_file=ifc_path)
    # geo.wall_types()
    # geo.door_types()
    # geo.type_wall()
    # geo.properties_wall()
    #geo.container_name()
    #geo.element_container()
    # geo.get_coordinates()
    #geo.get_coordiantes_space()
    #geo.choose_next_wall_element()
    # geo.get_classification()
    # geo.unit()
    # geo._get_pipe()
    # geo.full_geometry()
    # geo.opencascade()
    #geo.coordiante_transformation()
    # geo._get_info()
    # geo.get_room_window()
    #geo._get_rooms()
    # geo.room_coordiantes()
    geo.room_dimension()