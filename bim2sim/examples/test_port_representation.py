from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeSphere
from OCC.Core.gp import gp_Pnt
from pathlib import Path


import ifcopenshell.geom
settings = ifcopenshell.geom.settings()

# Read in the IFC file
ifc_path = Path(
    __file__).parent.parent / 'assets/ifc_example_files/hvac_heating.ifc'
ifc_file = ifcopenshell.open(ifc_path)

# Filter all IfcDistributionPort
ports = ifc_file.by_type("IfcDistributionPort")
for port in ports:
    # generate sphere shape
    sphere_radius = 0.1
    vert = gp_Pnt(0, 0, 0)  # these are relative coordinates to the port
    sphere_shape = BRepPrimAPI_MakeSphere(vert, sphere_radius).Shape()

    # convert shape to ifc geometry
    prox = ifcopenshell.geom.tesselate('IFC4', sphere_shape, 1)
    prox.Representations[0].RepresentationIdentifier = 'Body'
    context = \
    [c for c in ifc_file.by_type('IfcGeometricRepresentationSubcontext') if
     c.ContextIdentifier == 'Body' and c.ContextType == 'Model'][0]
    # set representation of port to created representation
    port.Representation = prox
    port.Representation.Representations[0].ContextOfItems = context
    ifc_file.add(port)

ifc_file.write("example.ifc")
