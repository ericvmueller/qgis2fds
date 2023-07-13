# -*- coding: utf-8 -*-

"""qgis2fds"""

__author__ = "Eric Mueller"
__date__ = "2023-07-10"
__revision__ = "$Format:%H$"  # replaced with git SHA1

import zarr
import json
import geopandas as gpd
from fastfuels_sdk import create_dataset,export_zarr_to_fds
from fastfuels_sdk.treelists import list_treelists,get_treelist



from qgis.core import QgsJsonExporter,QgsGeometry,QgsFeature,QgsField
from qgis.PyQt.QtCore import QVariant

# from qgis.utils import iface
# from qgis.PyQt.QtCore import QSize, QCoreApplication


class FastFuels:

    def __init__(
        self,
        feedback,
        wgs84_extent,
        utm_id,
        fds_offset,
        path,
        name,
        dx,
        dz,
        pad=0
    ) -> None:
        self.feedback = feedback
        self.path = path
        self.name = name
        self.extent = wgs84_extent
        self.utm_id = utm_id
        self.fds_offset = fds_offset
        self.dx = dx
        self.dz = dz
        self.pad = pad

        self._generateFuel(feedback)
        # self._save()

    def _generateFuel(self,feedback):
        # perhaps one day a cleaner method to create geojson
        geom=QgsGeometry.fromRect(self.extent)
        feat=QgsFeature()
        feat.setGeometry(geom)
        geojson=QgsJsonExporter().exportFeature(feat)

        # Create a geojson polygon to pass to FastFuels
        geojson = {
          "type": "Feature",
          "geometry": {
            "type": "Polygon",
            "coordinates":  [[[self.extent.xMinimum(), self.extent.yMinimum()],
                            [self.extent.xMinimum(), self.extent.yMaximum()],
                            [self.extent.xMaximum(), self.extent.yMaximum()],
                            [self.extent.xMaximum(), self.extent.yMinimum()]]]
          },
          "properties": {
            "name": "WGS84 domain"
          }
        }

        # Create a dataset
        dataset = create_dataset(name=self.name+" dataset",
                                 description="FastFuels data generated for qgis2fds",
                                 spatial_data=geojson)

        # Create a treelist from a dataset
        treelist = dataset.create_treelist(name=self.name+" treelist",
                                           description="treelist generated from FastFuels for qgis2fds")

        # Wait for a treelist to finish generating
        feedback.pushInfo('Fetching FastFuels treelist...')
        # feedback.pushInfo(dataset.id)
        # treelistid=list_treelists('d6f766d28ed34c80aaabf28fbe088694')[0].id
        # treelist=get_treelist(treelistid)
        treelist.wait_until_finished(verbose=True)
        treedata = treelist.get_data()
        treedata = self._transformTreelist(treedata)
        # update treelist
        treelist_utm=treelist.update_data(treedata)
        # save to disc
        treedata.to_csv(self.path+'/'+self.name+"_treelist.csv")

        # Create a fuelgrid from a treelist
        fuelgrid = treelist.create_fuelgrid(name=self.name+" fuelgrid",
                                            description="treelist generated from FastFuels for qgis2fds",
                                            distribution_method="realistic",
                                            horizontal_resolution=self.dx,
                                            vertical_resolution=self.dz,
                                            border_pad=self.pad)

        # Wait for a fuelgrid to finish generating
        feedback.pushInfo('Creating fuelgrid from treelist...')
        fuelgrid.wait_until_finished(verbose=True)
        feedback.pushInfo(str(fuelgrid.horizontal_resolution))

        # Download the Fuelgrid zarr data
        feedback.pushInfo('Downloading fuelgrid as zarr...')
        fuelgrid.download_zarr(self.path+'/'+self.name+'_fuelgrid.zip')

        # Export the Fuelgrid zarr data to FDS inputs
        feedback.pushInfo('Writing binary bulk density files for FDS...')
        zroot = zarr.open(self.path+'/'+self.name+'_fuelgrid.zip', mode='r')
        export_zarr_to_fds(zroot, self.path, self.fds_offset)

    def _transformTreelist(self,treedata):
        locs=gpd.points_from_xy(x=treedata['X_m'],y=treedata['Y_m'])
        locs=gpd.GeoSeries(locs,crs='EPSG:5070').to_crs(self.utm_id)
        treedata['X_m']=locs.x
        treedata['Y_m']=locs.y
        return treedata




