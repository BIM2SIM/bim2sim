import ifcopenshell
import ifcopenshell.geom

import multiprocessing
import numpy as np
import OCC

class geometry():

    def __init__(self, ifc_file):
        self.model = ifcopenshell.open(ifc_file)

    def get_room_coordinates(self):
        room_coordinates = {}
        for room in self.model.by_type("IfcSpace"):
            x, y, z = room.ObjectPlacement.RelativePlacement.Location.Coordinates[:3]
            room_coordinates[room.Name] = (x, y, z)
        return room_coordinates

    def write_pipe(self):
        pass



    def test_3(self):

        settings = ifcopenshell.geom.settings()
        iterator = ifcopenshell.geom.iterator(settings, self.model, multiprocessing.cpu_count())
        if iterator.initialize():
            while True:
                shape = iterator.get()
                matrix = shape.transformation.matrix.data
                print(matrix)
                faces = shape.geometry.faces
                edges = shape.geometry.edges
                # ... write code to process geometry here ...
                if not iterator.next():
                    break

    def tests(self):
        settings = ifcopenshell.geom.settings()
        settings.set(settings.USE_PYTHON_OPENCASCADE, True)
        settings.set(settings.USE_WORLD_COORDS, True)
        element = self.model.by_type('IfcWindow')[0]
        print(element.Name)
        body = ifcopenshell.util.representation.get_representation(element, "Model", "Body")
        geometry = ifcopenshell.geom.create_shape(settings, body)
        geometry = ifcopenshell.geom.create_shape(settings, self.model.by_type("IfcExtrudedAreaSolid")[0])
        geometry = ifcopenshell.geom.create_shape(settings, self.model.by_type("IfcProfileDef")[0])

        print(geometry)

    def test(self):
        settings = ifcopenshell.geom.settings()
        settings.set(settings.USE_PYTHON_OPENCASCADE, True)
        settings.set(settings.USE_WORLD_COORDS, True)
        spaces = self.model.by_type('IfcWindow')[0]
        print(spaces.Name)
        settings = ifcopenshell.geom.settings()
        shape = ifcopenshell.geom.create_shape(settings, spaces)
       # print(shape.guid)
       # print(shape.id)
       # print(self.model.by_guid(shape.guid))
        print(shape.geometry)
        matrix = shape.transformation.matrix.data
        print(matrix)
        faces = shape.geometry.faces
        edges = shape.geometry.edges
        verts = shape.geometry.verts
        grouped_verts = [[verts[i], verts[i + 1], verts[i + 2]] for i in range(0, len(verts), 3)]
        grouped_edges = [[edges[i], edges[i + 1]] for i in range(0, len(edges), 2)]
        grouped_faces = [[faces[i], faces[i + 1], faces[i + 2]] for i in range(0, len(faces), 3)]

    # Funktion zur Erstellung der Transformationsmatrix
    def create_transform_matrix(self, relative_placement):
        x_dir = relative_placement.Axis.DirectionRatios[0]
        y_dir = relative_placement.RefDirection.DirectionRatios[1]
        z_dir = relative_placement.Axis.DirectionRatios[2]
        origin = relative_placement.Location.Coordinates
        transform_matrix = np.zeros((4, 4))
        transform_matrix[3, 3] = 1
        transform_matrix[:3, :3] = np.array([[x_dir[0], y_dir[0], z_dir[0]],
                                             [x_dir[1], y_dir[1], z_dir[1]],
                                             [x_dir[2], y_dir[2], z_dir[2]]])
        transform_matrix[:3, 3] = np.array(origin)
        return transform_matrix

    def reference_point(self):
        pass


    def calc_pipe(self):
        spaces = self.model.by_type("IfcSpace")
        lowest_level_spaces = []
        for space in spaces:
            print(f'{space.Name} : {space.id()}')
            if space.ObjectPlacement:
                if ifc_obj.ObjectPlacement.is_a("IfcLocalPlacement"):
                    print(space.ObjectPlacement.RelativePlacement.Location.Coordinates[2])
                    #room.ObjectPlacement.RelativePlacement.Location.Coordinates[:3]
                    #if space.ObjectPlacementRelativePlacement.Location.Coordinates == 0:



    def get_global_coordiantes(self, ifc_obj=None):
        print(ifc_obj.Name)
        if ifc_obj.ObjectPlacement:
            # Überprüfen, ob das Objekt ein IfcLocalPlacement ist
            if ifc_obj.ObjectPlacement.is_a("IfcLocalPlacement"):
                local_placement = ifc_obj.ObjectPlacement.RelativePlacement
                print(local_placement)
                origin = local_placement.Location.Coordinates
                print(origin)
                # Drucke die globalen Koordinaten des Bezugspunkts
                print("Globale Koordinaten des Bezugspunkts von Raum {}:".format(ifc_obj.Name))
                print(origin)
            elif ifc_obj.ObjectPlacement.is_a("IfcGridPlacement"):
                # Bestimmung des Bezugspunkts (Origin) aus der absoluten Koordinate des GridPlacement
                grid_placement = ifc_obj.ObjectPlacement.PlacementLocation
                origin = grid_placement.Coordinates
                # Drucke die globalen Koordinaten des Bezugspunkts
                print("Globale Koordinaten des Bezugspunkts von Raum {}:".format(ifc_obj.Name))
                print(origin)


        """placement = ifc_obj.ObjectPlacement.PlacementRelTo
        if placement.is_a("IfcLocalPlacement"):
            relative_coordinates = placement.RelativePlacement.Location.Coordinates
            # Verarbeiten Sie die relativen Koordinaten entsprechend
        else:
            # Das Platzierungsobjekt ist global
            global_coordinates = placement.RelativePlacement.Location.Coordinates
            # Verarbeiten Sie die globalen Koordinaten entsprechend"""


        obj_placement = ifc_obj.ObjectPlacement
        if obj_placement.is_a('IfcLocalPlacement'):
            relative_placement = obj_placement.RelativePlacement
            coordinates = relative_placement.Location.Coordinates
            placement_in_space = obj_placement.PlacementRelTo

            """while placement_in_space.is_a("IfcLocalPlacement"):
                relative_placement = placement_in_space.RelativePlacement
                coordinates = [sum(x) for x in zip(coordinates, relative_placement.Location.Coordinates)]
                placement_in_space = obj_placement.PlacementRelTo
            print("Globale Koordinaten:", coordinates)"""

        elif obj_placement.is_a('IfcGridPlacement'):
            print('Platzierung ist ein Gitter')
        elif obj_placement.is_a('IfcAbsolutePlacement'):
            coords = obj_placement.Location.Coordinates
            print('Koordinaten:', coords)
        else:
            print('Ungültige Platzierung')


        #print(dir(ifc_obj.ObjectPlacement.wrap_value))

        #print(dir(ifc_obj))








        """# Konvertieren Sie die relative Platzierung des Raums in globale Koordinaten
        if ifc_obj.ObjectPlacement.is_a("IfcLocalPlacement"):
            placement = ifc_obj.ObjectPlacement.PlacementRelTo
            print(dir(placement.RelativePlacement))
            transform_matrix1 = self.create_transform_matrix(placement.RelativePlacement)
            transform_matrix2 = self.create_transform_matrix(ifc_obj.ObjectPlacement.RelativePlacement)
            transform_matrix = np.matmul(transform_matrix1, transform_matrix2)
        else:
            transform_matrix = self.create_transform_matrix(ifc_obj.ObjectPlacement.RelativePlacement)

        # Berechnen Sie die globalen Koordinaten des Raums
        relative_coords = np.array(ifc_obj.ObjectPlacement.RelativePlacement.Location.Coordinates)
        homogeneous_coords = np.concatenate([relative_coords, [1]])
        global_coords = np.matmul(transform_matrix, homogeneous_coords)[:3]

        # Die globalen Koordinaten werden als NumPy-Array zurückgegeben
        print('Globale Koordinaten:', global_coords)"""

        # Berechnen Sie die globalen Koordinaten des Raums
        #relative_coords = np.array(ifc_obj.ObjectPlacement.RelativePlacement.Location.Coordinates)
        #homogeneous_coords = np.concatenate([relative_coords, [1]])
        #global_coords = np.matmul(transform_matrix, homogeneous_coords)[:3]
        """print(ifc_obj)
        if ifc_obj.ObjectPlacement.is_a('IfcLocalPlacement'):
            coordinates = ifc_obj.ObjectPlacement.RelativePlacement.Location.Coordinates
            #print(ifc_obj.Name)
            #print(coordinates)
            if ifc_obj.ObjectPlacement.PlacementRelTo:
                parent_obj = self.model.by_id(ifc_obj.ObjectPlacement.PlacementRelTo.id())
                #print(parent_obj)
                parent_coords = self.get_global_coordiantes(parent_obj)
                for i in range(3):
                    coordinates[i] += parent_coords[i]
        return coordinates
        """
    def test_room(self):
        rooms = self.model.by_type("IfcSpace")
        for room in rooms:
            print(f"Name: {room.Name}, ID: {room.id()}")
            if room.ObjectPlacement.is_a('IfcLocalPlacement'):
                coordinates = room.ObjectPlacement.RelativePlacement.Location.Coordinates
                print('Koordinaten:', coordinates)




            """if space_obj.Representation:
                for rep in space_obj.Representation.Representations:
                    if rep.is_a('IfcShapeRepresentation'):
                        for item in rep.Items:
                            if item.is_a('IfcExtrudedAreaSolid'):
                                length = item.Depth
                                width = item.SweptArea.OuterCurve.Bound.PolyLoop.Polygon[1][0] - \
                                        item.SweptArea.OuterCurve.Bound.PolyLoop.Polygon[0][0]
                                height = item.Depth / item.SweptArea.OuterCurve.Bound.PolyLoop.Perimeter
                                print('Länge:', length)
                                print('Breite:', width)
                                print('Höhe:', height)"""



            room_geometry = room.Representation.Representations[0].Items[0]




            if room_geometry.is_a('IfcFacetedBrep'):
                print('Die Instanz ist eine IfcFacetedBrep-Instanz')
                print(room_geometry)

            else:
                print('Die Instanz ist kein IfcFacetedBrep-Objekt')

            #shape_gpXYZ = space.Location().Transformation().TranslationPart()
            #print(shape_gpXYZ.X(), shape_gpXYZ.Y(), shape_gpXYZ.Z())


            #print("Raumtyp:", room.IsDefinedBy)
            #print("Raumhöhe:", room.Height.NominalValue.wrappedValue)
            """for rel_def in room.IsDefinedBy:
                if rel_def.is_a("IfcRelDefinesByProperties"):
                    props = rel_def.RelatingPropertyDefinition
                    if props.is_a("IfcPropertySet"):
                        for prop in props.HasProperties:
                            print(prop)
                            if prop.Name == "Height":
                                height = prop.NominalValue.wrappedValue
                                print(height)
                            elif prop.Name == "Width":
                                width = prop.NominalValue.wrappedValue
                            elif prop.Name == "Length":
                                length = prop.NominalValue.wrappedValue"""

    def calculation_room(self):
        # todo überprüfte ob die koordinaten der walls, door, windows korrekt sind
        room_coordinates = {}
        for room in self.model.by_type("IfcSpace"):
            # Auslesen der globalen Koordinaten
            x, y, z = room.ObjectPlacement.RelativePlacement.Location.Coordinates[:3]
            #print("Koordinaten des Raums", room.Name, "sind:", x, y, z)
            # todo: globale Koordianten müssen x - length, y"""
            # todo: elements: Geometrien übertragen
            room_elements = []
            for boundary_element in self.model.by_type("IfcRelSpaceBoundary"):
                if boundary_element.RelatingSpace == room:
                    room_elements.append(boundary_element.RelatedBuildingElement)
            room_coordinates[room.Name] = {
                "coordinates": (x, y, z),
                "elements": []
            }
            for element in room_elements:
                if element is not None:
                    if element.is_a("IfcWall"):
                        # todo: wall: x: x_global, y: y_global+widith (Ist auf Raum bezogen, daher wird widith mitberechnet) z: correct:
                        # todo: bounding box Berechnen
                        # Auslesen der Wand-Koordinaten
                        x, y, z = element.ObjectPlacement.RelativePlacement.Location.Coordinates[:3]
                        room_coordinates[room.Name]["elements"].append(
                            {
                                "type": "Wall",
                                "name": element.Name,
                                "id": element.id(),
                                "coordinates": (x, y, z)
                            }
                        )
                    elif element.is_a("IfcDoor"):
                        # Auslesen der Tür-Koordinaten
                        local_placement = element.ObjectPlacement.RelativePlacement.Location
                        x, y, z = element.ObjectPlacement.RelativePlacement.Location.Coordinates[:3]
                        room_coordinates[room.Name]["elements"].append(
                            {
                                "type": "Door",
                                "name": element.Name,
                                "coordinates": (x, y, z)
                            }
                        )
                    elif element.is_a("IfcWindow"):
                        # Auslesen der Fenster-Koordinaten
                        local_placement = element.ObjectPlacement.RelativePlacement.Location
                        #print(local_placement)
                        if isinstance(local_placement, ifcopenshell.entity_instance):
                            if local_placement.is_a("IfcAxis2Placement3D"):
                                coordinates = local_placement.Location.Coordinates
                                print("Window coordinates: ", coordinates)
                        x, y, z = element.ObjectPlacement.RelativePlacement.Location.Coordinates[:3]
                        room_coordinates[room.Name]["elements"].append(
                            {
                                "type": "Window",
                                "name": element.Name,
                                "coordinates": (x, y, z)
                            }
                        )
        print(room_coordinates)
        return room_coordinates

    def calc(self):
        for room in self.model.by_type("IfcSpace"):
            # Lese die globalen Koordinaten des Raums aus
            x, y, z = room.ObjectPlacement.RelativePlacement.Location.Coordinates[:3]
            # Gehe durch alle Shapes in der Raumrepräsentation durch
            for shape in room.Representation.Representations:
                if shape.RepresentationType == "BoundingBox":
                    # Lese die Bounding Box Koordinaten aus
                    xmin, ymin, zmin, xmax, ymax, zmax = shape.Bounds.Coordinates
                    # Berechne die Längen, Breiten und Höhen der Bounding Box
                    length = xmax - xmin
                    width = ymax - ymin
                    height = zmax - zmin
                    # Gib die Maße des Raums aus
                    print("Maße des Raums", room.Name, "sind:", length, "x", width, "x", height)

    def is_global(self,coords):
        if isinstance(coords, ifcopenshell.geom.Point):
            return True
        elif isinstance(coords, ifcopenshell.geom.Vector):
            return False
        else:
            raise TypeError("Coordinates must be a Point or Vector")

    def gest_global_coordinates(self):
        from ifcopenshell import open as ifc_open
        from OCC.Core.gp import gp_Pnt, gp_Trsf, gp_XYZ
        from OCC.Core.TopLoc import TopLoc_Location

        settings = ifcopenshell.geom.settings()
        settings.set(settings.USE_PYTHON_OPENCASCADE, True)
        settings.set(settings.USE_WORLD_COORDS, True)
        settings.set(settings.EXCLUDE_SOLIDS_AND_SURFACES, False)
        settings.set(settings.INCLUDE_CURVES, True)
        for room in self.model.by_type('IfcSpace'):
            shape_tuple = ifcopenshell.geom.create_shape(settings, room)
            shape = shape_tuple.geometry
            location = room.ObjectPlacement.RelativePlacement.Location
            transform = BRepBuilderAPI_Transform(gp_Trsf(location.Transformation()))
            transformed_shape = transform.Shape(shape)

            # get global coordinates
            global_coords = []
            for i in range(transformed_shape.NbVertices()):
                vertex = transformed_shape.Vertex(i + 1)
                gp_pnt = vertex.Point()
                global_coords.append((gp_pnt.X(), gp_pnt.Y(), gp_pnt.Z()))

            print(global_coords)

    def get_relative_coordiantes(self):
        settings = ifcopenshell.geom.settings()
        settings.set(settings.USE_PYTHON_OPENCASCADE, True)
        settings.set(settings.USE_WORLD_COORDS, True)
        settings.set(settings.EXCLUDE_SOLIDS_AND_SURFACES, False)
        settings.set(settings.INCLUDE_CURVES, True)

        room_dict = {}
        for space in self.model.by_type("IfcSpace"):
            rooms = []
            if not space.Representation:
                continue
            room = {"id": space.id()}
            # get the room geometry
            shape_tuple = ifcopenshell.geom.create_shape(settings, space)
            # room["shape"] = shape_tuple.geometry
            # get the room placement
            room["x"], room["y"], room["z"] = space.ObjectPlacement.RelativePlacement.Location.Coordinates
            rooms.append(room)
            room_dict[space.LongName] = rooms
        print(room_dict)
        return room_dict

    def get_global_coordiantes(self):
        from ifcopenshell import open as ifc_open
        from OCC.Core.gp import gp_Pnt, gp_Vec, gp_Dir, gp_Trsf
        from OCC.Core.TopLoc import TopLoc_Location
        from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
        settings = ifcopenshell.geom.settings()
        settings.set(settings.USE_PYTHON_OPENCASCADE, True)
        settings.set(settings.USE_WORLD_COORDS, True)
        settings.set(settings.EXCLUDE_SOLIDS_AND_SURFACES, False)
        settings.set(settings.INCLUDE_CURVES, True)
        room = self.model.by_type("IfcSpace")[0]
        print(dir(room))
        print(room.ContainsElements)
        position = room.ConnectionGeometry.SurfaceOnRelatingElement. BasisSurface.Position.Location.Coordinates
        # Erstellen Sie eine Liste von Wänden und Decken



if __name__ == '__main__':
    ifc_path = "C:/02_Masterarbeit/08_BIMVision//FZK-Haus.ifc"
    geo = geometry(ifc_file=ifc_path)
    #geo.get_relative_coordiantes()
    #geo.get_global_coordiantes()
    geo.calculation_room()
    #geo.ifc_viewer()
    ifc_obj = geo.model.by_type("IfcSpace")[0]
    #global_coordinates = geo.get_global_coordiantes(ifc_obj)
    #geo.calc_pipe()
    #print(global_coordinates)
    #geo.test_room()
    #geo.test_function()
    #geo.test()
    #geo.tests()
    #geo.test_3()
    #geo.test_4()
    #geo.calc()
    # room_coordinates = geo.get_room_coordinates()
    # room_elements = geo.get_room_elements()
    #print("Room Coordinates:")
    #print(room_coordinates)
    #print("Room Elements:")
    #print(room_elements)