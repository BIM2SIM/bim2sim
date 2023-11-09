import ifcopenshell.geom
import os

from pathlib import Path
est_time = 10
aggregate_model = True

# def storage_dir_for_id(id):
#     id = id.split("_")[0]
#     return os.path.join(STORAGE_DIR, id[0:1], id[0:2], id[0:3], id)
#
#
# def storage_file_for_id(id, ext):
#     return os.path.join(storage_dir_for_id(id), id + "." + ext)


def execute():

    settings = ifcopenshell.geom.settings(
        INCLUDE_CURVES=True,
        EXCLUDE_SOLIDS_AND_SURFACES=False,
        APPLY_DEFAULT_MATERIALS=True,
        DISABLE_TRIANGULATION=True
    )

    # cache = ifcopenshell.geom.serializers.hdf5("cache.h5", settings)
    # sr = ifcopenshell.geom.serializers.svg(utils.storage_file_for_id(self.id, "svg"), settings)
    ifc_file_base = Path("C:/Users/Arbeit David/Documents/02_Git/bim2sim/test/resources/arch/ifc/")

    sr = ifcopenshell.geom.serializers.svg(
        str(ifc_file_base / "AC20-FZK-Haus.svg"), settings)

    # @todo determine file to select here or unify building storeys accross files somehow
    from ifcopenshell import open as ifc_open
    file_path = ifc_file_base / "AC20-FZK-Haus.ifc"

    file = ifc_open(file_path)

    sr.setFile(file)
    # sr.setFile(context.models[context.input_ids[0]])
    sr.setSectionHeightsFromStoreys()

    sr.setDrawDoorArcs(True)
    sr.setPrintSpaceAreas(True)
    sr.setPrintSpaceNames(True)
    sr.setBoundingRectangle(1024., 1024.)

    """
    sr.setProfileThreshold(128)
    sr.setPolygonal(True)
    sr.setAlwaysProject(True)
    sr.setAutoElevation(True)
    """

    # sr.setAutoSection(True)

    sr.writeHeader()

    # for ii in context.input_ids:
    f = ifc_file_base / "AC20-FZK-Haus.ifc"
    # f = context.models[ii]
    for progress, elem in ifcopenshell.geom.iterate(
            settings,
            file,
            with_progress=True,
            exclude=("IfcOpeningElement",),
            # cache=utils.storage_file_for_id(id, "cache.h5"),
            cache=str(Path("C:/Users/Arbeit David/Documents/02_Git/bim2sim/test/resources/arch/ifc/AC20-FZK-Haus.cache.h5")),
            num_threads=8
    ):
        try:
            sr.write(elem)
        except:
            print("On %s:" % f[elem.id])
            # traceback.print_exc(file=sys.stdout)
        # self.sub_progress(progress)

    sr.finalize()


if __name__=="__main__":
    execute()