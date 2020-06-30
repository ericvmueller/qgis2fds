# -*- coding: utf-8 -*-

"""qgis2fds"""

__author__ = "Emanuele Gissi, Ruggero Poletto"
__date__ = "2020-05-04"
__copyright__ = "(C) 2020 by Emanuele Gissi"
__revision__ = "$Format:%H$"  # replaced with git SHA1

from qgis.core import QgsExpressionContextUtils, QgsProject
from qgis.utils import pluginMetadata
import time
from . import utils

# Config

landuse_types = "Landfire FBFM13", "CIMA Propagator"

landuse_types_selections = {
    0: {  # "Landfire FBFM13"
        0: 19,  # if not available
        1: 1,
        2: 2,
        3: 3,
        4: 4,
        5: 5,
        6: 6,
        7: 7,
        8: 8,
        9: 9,
        10: 10,
        11: 11,
        12: 12,
        13: 13,
        91: 14,
        92: 15,
        93: 16,
        98: 17,
        99: 18,
    },
    1: {  # "CIMA Propagator"  # TODO finish porting
        0: 19,  # if not available
        1: 5,
        2: 4,
        3: 18,
        4: 10,
        5: 10,
        6: 1,
        7: 1,
    },
}


def _get_surf_str():
    return "\n".join(
        (
            f"! Boundary conditions",
            f"! 13 Anderson Fire Behavior Fuel Models",
            f"&SURF ID='A01', VEG_LSET_FUEL_INDEX= 1 /",
            f"&SURF ID='A02', VEG_LSET_FUEL_INDEX= 2 /",
            f"&SURF ID='A03', VEG_LSET_FUEL_INDEX= 3 /",
            f"&SURF ID='A04', VEG_LSET_FUEL_INDEX= 4 /",
            f"&SURF ID='A05', VEG_LSET_FUEL_INDEX= 5 /",
            f"&SURF ID='A06', VEG_LSET_FUEL_INDEX= 6 /",
            f"&SURF ID='A07', VEG_LSET_FUEL_INDEX= 7 /",
            f"&SURF ID='A08', VEG_LSET_FUEL_INDEX= 8 /",
            f"&SURF ID='A09', VEG_LSET_FUEL_INDEX= 9 /",
            f"&SURF ID='A10', VEG_LSET_FUEL_INDEX=10 /",
            f"&SURF ID='A11', VEG_LSET_FUEL_INDEX=11 /",
            f"&SURF ID='A12', VEG_LSET_FUEL_INDEX=12 /",
            f"&SURF ID='A13', VEG_LSET_FUEL_INDEX=13 /",
            f"&SURF ID='Urban' RGB=186,119, 80 /",
            f"&SURF ID='Snow-Ice' RGB=234,234,234 /",
            f"&SURF ID='Agricolture' RGB=253,242,242 /",
            f"&SURF ID='Water' RGB=137,183,221 /",
            f"&SURF ID='Barren' RGB=133,153,156 /",
            f"&SURF ID='NA' RGB=255,255,255 /",
            f" ",
        )
    )


def _get_geom_str(verts, faces, landuses, landuse_type):
    landuse_select = landuse_types_selections[landuse_type]
    surfid_str = "\n            ".join(
        (
            f"'A01','A02','A03','A04','A05','A06','A07','A08','A09','A10','A11','A12','A13',",
            f"'Urban','Snow-Ice','Agricolture','Water','Barren','NA'",
        )
    )
    verts_str = "\n            ".join(
        (f"{v[0]:.3f},{v[1]:.3f},{v[2]:.3f}," for v in verts)
    )
    faces_str = "\n            ".join(
        (
            f"{f[0]},{f[1]},{f[2]},{landuse_select.get(landuses[i], landuses[0])},"  # on error, choose NA
            for i, f in enumerate(faces)
        )
    )
    return "\n".join(
        (
            f"! Terrain",
            f"&GEOM ID='Terrain' IS_TERRAIN=T EXTEND_TERRAIN=F",
            f"      SURF_ID={surfid_str}",
            f"      VERTS={verts_str}",
            f"      FACES={faces_str} /",
        )
    )


# FIXME
def _write_terrain_bingeom(feedback, path, chid, verts, faces, landuses, landuse_type):
    landuse_select = landuse_types_selections[landuse_type]
    fds_surfs = list(
        landuse_select.get(landuses[i], landuses[0]) for i, _ in enumerate(faces)
    )
    n_surf_id = max(fds_surfs)
    fds_verts = list(v for vs in verts for v in vs)
    fds_faces = list(f for fs in faces for f in fs)
    # feedback.pushInfo(f"n_surf_id: {n_surf_id}")
    # feedback.pushInfo(f"fds_verts: {fds_verts}")
    # feedback.pushInfo(f"fds_faces: {fds_faces}")
    # feedback.pushInfo(f"fds_surfs: {fds_surfs}")
    utils.write_bingeom(
        geom_type=2,
        n_surf_id=n_surf_id,
        fds_verts=fds_verts,
        fds_faces=fds_faces,
        fds_surfs=fds_surfs,
        fds_volus=list(),
        filepath=f"{path}/{chid}_Terrain.bingeom",
    )


def get_case(
    feedback,
    dem_layer,
    landuse_layer,
    path,
    chid,
    wgs84_origin,
    utm_origin,
    wgs84_fire_origin,
    utm_fire_origin,
    utm_crs,
    verts,
    faces,
    landuses,
    landuse_type,
    landuses_set,
    mesh_extent,
):
    """
    Get FDS case.
    """

    # Write bingeom
    _write_terrain_bingeom(feedback, path, chid, verts, faces, landuses, landuse_type)

    # Calc header
    pv = pluginMetadata("qgis2fds", "version")
    qv = QgsExpressionContextUtils.globalScope().variable("qgis_version")
    now = time.strftime("%a, %d %b %Y, %H:%M:%S", time.localtime())
    filepath = QgsProject.instance().fileName() or "not saved"
    if len(filepath) > 60:
        filepath = "..." + filepath[-57:]

    # Calc MESH XB
    mesh_xb = (
        mesh_extent.xMinimum() - utm_origin.x(),
        mesh_extent.xMaximum() - utm_origin.x(),
        mesh_extent.yMinimum() - utm_origin.y(),
        mesh_extent.yMaximum() - utm_origin.y(),
        min(v[2] for v in verts) - 1.0,
        max(v[2] for v in verts) + 50.0,
    )
    # Calc center of VENT patch
    fire_x, fire_y = (
        utm_fire_origin.x() - utm_origin.x(),  # relative to origin
        utm_fire_origin.y() - utm_origin.y(),
    )

    surfid_str = "\n            ".join(
        (
            f"'A01','A02','A03','A04','A05','A06','A07','A08','A09','A10','A11','A12','A13',",
            f"'Urban','Snow-Ice','Agricolture','Water','Barren','NA'",
        )
    )

    return "\n".join(
        (
            f"! Generated by qgis2fds <{pv}> on QGIS <{qv}>",
            f"! QGIS file: <{filepath}>",
            f"! Selected UTM CRS: <{utm_crs.description()}>",
            f"! Terrain extent: <{mesh_extent.toString(precision=1)}>",
            f"! DEM layer: <{dem_layer.name()}>",
            f"! Landuse layer: <{landuse_layer and landuse_layer.name() or 'None'}>",
            f"! Landuse type: <{landuse_layer and ('Landfire FBFM13', 'CIMA Propagator')[landuse_type] or 'None'}>",
            f"! Domain Origin: <{utm_origin.x():.1f}, {utm_origin.y():.1f}>",
            f"! Domain Origin Link: <{utils.get_lonlat_url(wgs84_origin)}>",
            f"! Fire Origin: <{utm_fire_origin.x():.1f}, {utm_fire_origin.y():.1f}>",
            f"! Fire Origin Link: <{utils.get_lonlat_url(wgs84_fire_origin)}>",
            f"! Date: <{now}>",
            f" ",
            f"&HEAD CHID='{chid}' TITLE='Description of {chid}' /",
            f"&TIME T_END=1. /",
            f" ",
            f"&MISC ORIGIN_LAT={wgs84_origin.y():.7f}, ORIGIN_LON={wgs84_origin.x():.7f}, NORTH_BEARING=0.",
            f"      TERRAIN_CASE=T, TERRAIN_IMAGE='{chid}_tex.png', LEVEL_SET_MODE=1 /",
            f" ",
            f"! Domain and its boundary conditions",
            f"&MESH IJK=50,50,50, XB={mesh_xb[0]:.3f},{mesh_xb[1]:.3f},{mesh_xb[2]:.3f},{mesh_xb[3]:.3f},{mesh_xb[4]:.3f},{mesh_xb[5]:.3f} /",
            f"&VENT MB='XMIN', SURF_ID='OPEN' /",
            f"&VENT MB='XMAX', SURF_ID='OPEN' /",
            f"&VENT MB='YMIN', SURF_ID='OPEN' /",
            f"&VENT MB='YMAX', SURF_ID='OPEN' /",
            f"&VENT MB='ZMAX', SURF_ID='OPEN' /",
            f" ",
            f"! Fire origin",
            f"&SURF ID='Ignition', VEG_LSET_IGNITE_TIME=0., COLOR='RED' /",
            f"&VENT XB={fire_x-5:.3f},{fire_x+5:.3f},{fire_y-5:.3f},{fire_y+5:.3f},{mesh_xb[4]:.3f},{mesh_xb[4]:.3f}, SURF_ID='Ignition', GEOM=T /",
            f" ",
            f"! Output quantities",
            f"&SLCF AGL_SLICE=1., QUANTITY='LEVEL SET VALUE' /",
            f" ",
            f"! Wind",
            f"&WIND SPEED=1., RAMP_SPEED='ws', RAMP_DIRECTION='wd' /",
            f"&RAMP ID='ws', T=   0, F= 0. /",
            f"&RAMP ID='ws', T= 600, F=10. /",
            f"&RAMP ID='ws', T=1200, F=20. /",
            f"&RAMP ID='wd', T=   0, F=330. /",
            f"&RAMP ID='wd', T= 600, F=300. /",
            f"&RAMP ID='wd', T=1200, F=270. /",
            f" ",
            _get_surf_str(),  # TODO should send the right ones
            f" ",
            f"! Terrain",
            f"&GEOM ID='Terrain'",
            f"      READ_BINARY=T IS_TERRAIN=T EXTEND_TERRAIN=F" f" ",
            f"      SURF_ID={surfid_str} /",
            f" ",
            # _get_geom_str(verts, faces, landuses, landuse_type),
            f" ",
            f"&TAIL /\n",
        )
    )
