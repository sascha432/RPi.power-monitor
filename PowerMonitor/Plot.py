#
# Author: sascha_lammers@gmx.de
#

from . import Sensor
import matplotlib.ticker as ticker

class Plot(Sensor.Sensor):

    def __init__(self, config):
        global AppConfig
        AppConfig = config
        Sensor.Sensor.__init__(self, config)

        # self.y_limits = []

    def update_y_ticks_primary(self, y, pos):
        yl = self.y_limits[0]
        if 'y_max' in yl and yl['y_max']<2.0:
            diff = yl['y_max'] - yl['y_min']
            if diff<1.0:
                return '%d' % (int(y * 1000))
        return '%.2f' % y

    def update_y_ticks_secondary(self, y, pos):
        return '%.2f' % y


    def add_ticks(self):

        self.ax[0].yaxis.set_major_formatter(ticker.FuncFormatter(self.update_y_ticks_primary))
        self.ax[1].yaxis.set_major_formatter(ticker.FuncFormatter(self.update_y_ticks_secondary))

        self.ax[0].yaxis.set_major_locator(ticker.MaxNLocator(6))

# ymin, ymax = ax.get_ylim()
# ax.set_yticks(np.round(np.linspace(ymin, ymax, N), 2))

    def legend(self):
        self.ax[0].legend(['%u seconds' % self.get_time_scale()], handlelength=0, fontsize='x-small', labelcolor=self.TEXT_COLOR, loc='lower center', frameon=False, borderpad=0.0, borderaxespad=0.2)

    def get_plot_geometry(self, plot_number):
        if plot_number==0:
            if self.plot_visibility_state==0:
                return 121
            elif self.plot_visibility_state==2:
                return 111
        else:
            if self.plot_visibility_state==0:
                return (len(self.channels) * 100) + 20 + (plot_number * 2)
            if self.plot_visibility_state==1:
                return 100 + (len(self.channels) * 10) + (plot_number)
        return None

    def get_time_scale_num(self):
        min_time = self._time_scale_min_time
        r = 5.0
        y = 1.1
        x = AppConfig.plot.max_time < 1000 and 1.5 or 1.9
        for n in range(1, 10):
            factor = pow(x, n * y)
            max_time = int(AppConfig.plot.max_time / factor / r) * r
            if max_time<self._time_scale_min_time:
                return n
            # self.logger.debug('[time scale %d %.2f %d]' %(n, factor, max_time))
        return 10


    def get_time_scale(self, num=0):
        if self._time_scale_cur!=None and num==0:
            return self._time_scale_cur
        min_time = self._time_scale_min_time
        n = self.time_scale_factor
        r = 5.0
        y = 1.1
        x = AppConfig.plot.max_time < 1000 and 1.5 or 1.9
        factor = pow(x, n * y)
        max_time = int(AppConfig.plot.max_time / factor / r) * r
        if factor<1.0:
            factor = 1
        t = min(AppConfig.plot.max_time, max(self._time_scale_min_time, max_time))
        if num:
            self.logger.debug('time scale %d of %d (%u/%u)' % (t, AppConfig.plot.max_time, self.time_scale_factor, num))
        self._time_scale_cur = t
        return t
