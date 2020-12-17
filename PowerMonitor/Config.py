#
# Author: sascha_lammers@gmx.de
#

from Config import (Loader, DictType, RangeType, Param, JsonReader)
from os import path
from PowerMonitor import AppConfig

class Config:

    def __init__(self, config_dir):
        self._config_dir = path.realpath(config_dir)
        if not path.exists(self._config_dir) or not path.isdir(self._config_dir):
            raise IOError('No such file or directory: %s' % (self._config_dir))

    def get_filename(self, file):
        return path.realpath(path.join(self._config_dir, file))

    def load(self, file, target):

        loader = Loader('app', AppConfig.App(DictType({
            'channels': AppConfig.ChannelList(RangeType(range(0, 3), AppConfig.Channel, DictType({
                'name': Param(lambda path: ('Channel %u' % (path.index + 1))),
                'calibration': AppConfig.Calibration()
            }))),
            'plot': AppConfig.Plot(DictType({
                'compression': AppConfig.PlotCompression()
            })),
            'gui': AppConfig.Gui(),
            'mqtt': AppConfig.Mqtt(),
            'backlight': AppConfig.Backlight()
        })))

        reader = JsonReader(loader._root, False, target)
        reader.loads_from(file)
