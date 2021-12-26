# -*- coding: utf-8 -*-

"""qgis2fds"""

__author__ = "Emanuele Gissi"
__date__ = "2020-05-04"
__copyright__ = "(C) 2020 by Emanuele Gissi"
__revision__ = "$Format:%H$"  # replaced with git SHA1

import csv, os

from qgis.core import QgsProcessingException


class Wind:
    def __init__(self, feedback, project_path, filepath) -> None:
        self.filepath = filepath and os.path.join(project_path, filepath) or str()
        self._ws, self._wd = list(), list()
        if not filepath:
            return
        feedback.pushInfo(f"Import wind *.csv file: <{self.filepath}>")
        try:
            with open(self.filepath) as csv_file:
                # wind csv file has an header line and three columns:
                # time in seconds, wind speed in m/s, and direction in degrees
                csv_reader = csv.reader(csv_file, delimiter=",")
                next(csv_reader)  # skip header line
                for r in csv_reader:
                    self._ws.append(
                        f"&RAMP ID='ws', T={float(r[0]):.1f}, F={float(r[1]):.1f} /"
                    )
                    self._wd.append(
                        f"&RAMP ID='wd', T={float(r[0]):.1f}, F={float(r[2]):.1f} /"
                    )
        except Exception as err:
            raise QgsProcessingException(
                f"Error importing wind *.csv file from <{self.filepath}>:\n{err}"
            )

    def get_comment(self) -> str:
        filepath_str = (
            len(self.filepath) > 60
            and "..." + self.filepath[-57:]
            or self.filepath
            or "none"
        )
        return f"! Wind file: <{filepath_str}>"

    def get_fds(self) -> str:
        wind_str = f"""
! Wind
&WIND SPEED=1., RAMP_SPEED='ws', RAMP_DIRECTION='wd' /\n"""
        if self._ws:
            wind_str += "\n".join(("\n".join(self._ws), "\n".join(self._wd)))
        else:
            wind_str += f"""! Example ramps for wind speed and direction
&RAMP ID='ws', T=   0, F= 10. /
&RAMP ID='ws', T= 600, F= 10. /
&RAMP ID='ws', T=1200, F= 20. /
&RAMP ID='wd', T=   0, F=315. /
&RAMP ID='wd', T= 600, F=270. /
&RAMP ID='wd', T=1200, F=360. /"""
        return wind_str
