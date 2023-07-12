# -*- coding: utf-8 -*-

"""qgis2fds"""

__author__ = "Eric Mueller"
__date__ = "2023-07-10"
__revision__ = "$Format:%H$"  # replaced with git SHA1

import zarr
import json
from fastfuels_sdk import create_dataset, export_zarr_to_quicfire



from qgis.core import QgsProcessingException, QgsMapSettings, QgsMapRendererParallelJob
from qgis.utils import iface
from qgis.PyQt.QtCore import QSize, QCoreApplication


class FastFuels:

    def __init__(
        self,
        feedback,
        path,
        dx,
        dz,
        utm_extent,
        utm_crs,
        pad=0
    ) -> None:
        self.feedback = feedback
        self.path = path
        self.utm_crs = utm_crs  # destination_crs
        self.extent = utm_extent

        self._save()

    def _generateFuel(self):
        # Create a dataset
        bbox={
            "bbox": {
                "west": -113.94717919590558,
                "east": -113.94615426856866,
                "north": 46.826770523885266,
                "south": 46.82586367573463
            },
            "epsg": 4326
        }

        dataset = create_dataset(name="dataset",
                                 description="My dataset description",
                                 spatial_data=bbox)

        # Create a treelist from a dataset
        treelist = dataset.create_treelist(name=CHID+" treelist",
                                           description="treelist generated from FastFuels")

        # Wait for a treelist to finish generating
        treelist.wait_until_finished(verbose=True)

        # Create a fuelgrid from a treelist
        fuelgrid = treelist.create_fuelgrid(name="my-fuelgrid",
                                            description="My fuelgrid description",
                                            distribution_method="realistic",
                                            horizontal_resolution=dx,
                                            vertical_resolution=dz,
                                            border_pad=pad)

        # Wait for a fuelgrid to finish generating
        fuelgrid.wait_until_finished(verbose=True)

        # Download the Fuelgrid zarr data
        fuelgrid.download_zarr(self.path+'/fuelgrid.zip')

        # Export the Fuelgrid zarr data to FDS inputs
        zroot = zarr.open(self.path+'/fuelgrid.zip', mode='r')
        export_zarr_to_fds(zroot, self.path)

        self.feedback.pushInfo(f"Save terrain texture file: <{self.filepath}>")
        # Calc tex_extent size in meters (it is in utm)
        tex_extent_xm = self.tex_extent.xMaximum() - self.tex_extent.xMinimum()
        tex_extent_ym = self.tex_extent.yMaximum() - self.tex_extent.yMinimum()
        # Calc tex_extent size in pixels
        tex_extent_xpix = int(tex_extent_xm / self.pixel_size)
        tex_extent_ypix = int(tex_extent_ym / self.pixel_size)
        # Choose exporting layers
        if self.tex_layer:  # use user tex layer
            layers = (self.tex_layer,)
        elif iface:  # no user tex layer, use map canvas
            canvas = iface.mapCanvas()
            layers = canvas.layers()
        else:
            self.feedback.pushInfo(f"No texture requested.")
            return
        # Image settings and texture layer choice
        settings = QgsMapSettings()  # build settings
        settings.setDestinationCrs(self.utm_crs)  # set output crs
        settings.setExtent(self.tex_extent)  # in utm_crs
        settings.setOutputSize(QSize(tex_extent_xpix, tex_extent_ypix))
        settings.setLayers(layers)
        # Render and save image
        render = QgsMapRendererParallelJob(settings)
        render.start()
        t0 = time.time()
        dt = 0.
        while render.isActive():
            dt = time.time() - t0
            QCoreApplication.processEvents()
            if self.feedback.isCanceled():
                render.cancelWithoutBlocking()
                return
            if dt >= self.timeout:
                render.cancelWithoutBlocking()
                self.feedback.reportError("Texture render timed out, no texture saved.")
                return
        image = render.renderedImage()
        try:
            os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
            image.save(self.filepath, self.image_type)
        except Exception as err:
            raise QgsProcessingException(
                f"Texture file not writable to <{self.filepath}>.\n{err}"
            )
        self.feedback.pushInfo(f"Texture saved in {dt:.2f} s")

    def get_fds(self):
        return f"TERRAIN_IMAGE='{self.filename}'"
