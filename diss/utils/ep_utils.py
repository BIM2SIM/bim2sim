from eppy.function_helpers import azimuth
from eppy.geometry import surface as g_surface


def true_azimuth(ddtt):
    """true azimuth of the surface"""
    idf = ddtt.theidf
    coord_system = idf.idfobjects["GlobalGeometryRules".upper()][0].Coordinate_System
    if coord_system.lower() == "relative":
        zone_name = ddtt.Zone_Name
        bldg_north = idf.idfobjects["Building".upper()][0].North_Axis
        zone_rel_north = idf.getobject("Zone".upper(),
                                       zone_name).Direction_of_Relative_North
        surf_azimuth = azimuth(ddtt)
        return g_surface.true_azimuth(bldg_north, zone_rel_north, surf_azimuth)
    elif coord_system.lower() in ("world", "absolute"):
        # NOTE: "absolute" is not supported in v9.3.0
        return azimuth(ddtt)
    else:
        raise ValueError(
            "'{:s}' is no valid value for 'Coordinate System'".format(coord_system)
        )

azimuth_orientations = {
    0: 'N',
    45: 'NE',
    90: 'E',
    135: 'SE',
    180: 'S',
    225: 'SW',
    270: 'W',
    315: 'NW'
}