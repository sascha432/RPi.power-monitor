#
# Author: sascha_lammers@gmx.de
#

import sys
import time
import matplotlib.ticker as ticker
import numpy as np
from . import FormatFloat, Sensor, Tools, PLOT_VISIBILITY, PLOT_PRIMARY_DISPLAY, ANIMATION, SCHEDULER_PRIO, DISPLAY_ENERGY

class Plot(Sensor.Sensor):

    def __init__(self):
        global AppConfig
        AppConfig = self._app_config

        self._time_scale_num = 0
        self._time_scale_min_time = 5
        self._time_scale_items = self.get_time_scale_list()

    def init_vars(self):
        self.debug(__name__, 'init_vars')
        self._time_scale_num = 0

    def plot_thread(self):
        time.sleep(2)
        self.thread_register(__name__)
        while not self.terminate.is_set():
            # if self.animation_is_running():
            if True:
                self.lock.acquire()
                try:
                    self.plot_values(2, True)
                finally:
                    self.lock.release()
            time.sleep(0.025)
        self.thread_unregister(__name__)

    def update_y_ticks_primary(self, y, pos):
        if 0 in self._y_limits:
            yl = self._y_limits[0]
            diff = yl[0] - yl[1]
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
            if self._gui_config.plot_visibility==PLOT_VISIBILITY.BOTH:
                return 121
            elif self._gui_config.plot_visibility==PLOT_VISIBILITY.PRIMARY:
                return 111
        else:
            if self._gui_config.plot_visibility==PLOT_VISIBILITY.BOTH:
                return (len(self.channels) * 100) + 20 + (plot_number * 2)
            if self._gui_config.plot_visibility==PLOT_VISIBILITY.VOLTAGE:
                return 100 + (len(self.channels) * 10) + (plot_number)

        # fix
        return 111

    def get_time_scale_list(self):
        _max_time = AppConfig.plot.max_time
        l = [_max_time]
        rl = [(60, 30), (120, 60), (900, 300), (3600, 900), (3600 * 4, 3600)]
        rl.reverse()
        for n in range(1, 10):
            factor = pow(1.7, n * 1.00)
            max_time = int(_max_time / factor)
            r = 5
            for i, j in rl:
                if max_time>=i:
                    r = j
                    break
            max_time = int(max_time / r) * r
            if max_time<self._time_scale_min_time:
                break
            l.append(max_time)
        l.append(self._time_scale_min_time)
        l = np.unique(l)
        l = l.tolist()
        # print(l)
        return l

    def get_time_scale(self):
        return self._time_scale_items[int((len(self._time_scale_items) - 1) * self._gui_config.plot_time_scale)]

    def plot_count_fps(self):
        ts = time.monotonic()
        self.plot_updated_times.append(ts - self.plot_updated)
        if len(self.plot_updated_times)>20:
            self.plot_updated_times.pop(0)
        self.plot_updated = ts

    def get_plot_fps(self):
        return 1.0 / max(0.000001, len(self.plot_updated_times)>2 and np.average(self.plot_updated_times[1:]) or 0)

    def get_plot_values(self, axis, channel):
        if axis==0:
            if self._gui_config.plot_primary_display==PLOT_PRIMARY_DISPLAY.CURRENT:
                return (self.values[channel], self.values[channel].current())
            elif self._gui_config.plot_primary_display==PLOT_PRIMARY_DISPLAY.POWER:
                return (self.values[channel], self.values[channel].power())
            elif self._gui_config.plot_primary_display==PLOT_PRIMARY_DISPLAY.AGGREGATED_POWER:
                tidx = self.values.time()
                return (self.values[0], self.power_sum)
        elif axis==1:
            return (self.values[channel], self.values[channel].voltage())
        raise RuntimeError('axis %u channel %u plot_primary_display %u' % (axis, channel, self._gui_config.plot_primary_display))

    def get_plot_line(self, axis, channel):
        if axis==0:
            if self._gui_config.plot_primary_display==PLOT_PRIMARY_DISPLAY.CURRENT or self._gui_config.plot_primary_display==PLOT_PRIMARY_DISPLAY.POWER:
                return self.lines[0][channel]
            elif self._gui_config.plot_primary_display==PLOT_PRIMARY_DISPLAY.AGGREGATED_POWER:
                return self.lines[0][0]
        elif axis==1:
            return self.lines[1][channel]
        raise RuntimeError('axis %u channel %u plot_primary_display %u' % (axis, channel, self._gui_config.plot_primary_display))

    def set_main_plot(self):
        if not self.lock.acquire(True):
            return
        try:
            self.power_sum = []
            self.clear_y_limits(0)
            if self._gui_config.plot_primary_display==PLOT_PRIMARY_DISPLAY.CURRENT:
                values_type = 'I'
                values, items = self.get_plot_values(0, 0)
                self.plot_main_current_rounding = AppConfig.plot.main_current_rounding
                self.ax[0].set_ylabel('Current (A)', color=self.PLOT_TEXT, **self.PLOT_FONT)
            elif self._gui_config.plot_primary_display==PLOT_PRIMARY_DISPLAY.POWER:
                values_type = 'P'
                values, items = self.get_plot_values(0, 1)
                self.plot_main_current_rounding = AppConfig.plot.main_current_rounding
                self.ax[0].set_ylabel('Power (W)', color=self.PLOT_TEXT, **self.PLOT_FONT)
            elif self._gui_config.plot_primary_display==PLOT_PRIMARY_DISPLAY.AGGREGATED_POWER:
                values_type = 'Psum'
                values, items = self.get_plot_values(0, 2)
                self.plot_main_current_rounding = AppConfig.plot.main_power_rounding
                self.ax[0].set_ylabel('Aggregated Power (W)', color=self.PLOT_TEXT, **self.PLOT_FONT)
            else:
                raise RuntimeError('set_main_plot: plot_primary_display %s' % (self._gui_config.plot_primary_display))

            self.lines[0] = []
            for line in self.ax[0].get_lines():
                line.remove()

            for channel in self.channels:
                line, = self.ax[0].plot(self.values.time(), self.values[channel].voltage(), color=channel._color_for(values_type), label=channel.name, linewidth=AppConfig.plot.line_width)
                self.lines[0].append(line)

            self.add_ticks()

        finally:
            self.lock.release()

    def plot_bitblt(self):

        for ax in self.ax:
            background = self.canvas.copy_from_bbox(ax.bbox)
            self.canvas.restore_region(background)
            ax.draw()
            self.canvas.blit(ax.bbox)

    def plot_values(self, i, blt=False):

        if i<=1:
            if self.ani.event_source.interval==ANIMATION.INIT:
                # stop animation after initializing
                # the first sensor data will start it
                self.debug(__name__, 'animation ready...')
                self.ani.event_source.stop()
                self.ani.event_source.interval = ANIMATION.READY
            return

        try:
            self.aggregate_sensor_values(blt)

            fmt = FormatFloat.FormatFloat(4, 5, prefix=FormatFloat.PREFIX.M, strip=FormatFloat.STRIP.NONE)
            fmt.set_precision('m', 1)

            self.plot_count_fps()

            ts = time.monotonic()
            display_idx = 0
            x_range = self.values.time()
            x_max = None
            x_min = -self.get_time_scale()
            y_max = 0
            y_min = sys.maxsize

            if self._gui_config.plot_primary_display==PLOT_PRIMARY_DISPLAY.AGGREGATED_POWER:
                tmp = []
                for channel in self.channels:
                    ch = int(channel)
                    tmp.append(self.values[ch].power())
                self.power_sum = np.array(tmp).sum(axis=0)

            for channel in self.channels:
                ch = int(channel)

                # axis 0
                line = self.get_plot_line(0, ch)
                values, items = self.get_plot_values(0, ch)
                if x_max==None:
                    x_max = self.values.max_time()
                    x_min = x_max - self.get_time_scale()
                    display_idx = self.values.find_time_index(x_min, True)

                # top labels
                self.labels[ch]['U'].configure(text=fmt.format(values.avg_U(), 'V'))
                self.labels[ch]['I'].configure(text=fmt.format(values.avg_I(), 'A'))
                self.labels[ch]['P'].configure(text=fmt.format(values.avg_P(), 'W'))
                tmp = self._gui_config.plot_display_energy==DISPLAY_ENERGY.AH and ('ei', 'Ah') or ('ep', 'Wh')
                self.labels[ch]['e'].configure(text=fmt.format(self.energy[ch][tmp[0]], tmp[1]))

                # axis 1

                # max. for all lines
                y_max = max(y_max, max(items[display_idx:]))
                y_min = min(y_min, min(items[display_idx:]))
                line.set_data(x_range, items)

                values, items = self.get_plot_values(1, ch)
                line = self.get_plot_line(1, ch)
                line.set_data(x_range, items)

                # max. per channel
                y_max1 = max(round(values.max_U(display_idx) * AppConfig.plot.voltage_top_margin, 2), channel.voltage + 0.02)
                y_min1 = min(round(values.min_U(display_idx) * AppConfig.plot.voltage_bottom_margin, 2), channel.voltage - 0.02)
                self.ax[channel.number].set_ylim(top=y_max1, bottom=y_min1)


            # axis 0 y limits
            if y_min==sys.maxsize:
                y_min=0
            if y_max:
                tmp = (y_max, y_min)
                r = self.plot_main_current_rounding * 0.50001
                y_max = max(tmp[0] + 0.02, int(y_max * AppConfig.plot.main_top_margin / self.plot_main_current_rounding + r) * self.plot_main_current_rounding)
                y_min = min(tmp[1] - 0.02, max(0, int(y_min * AppConfig.plot.main_bottom_margin / self.plot_main_current_rounding + r) * self.plot_main_current_rounding))
                if y_max == y_min:
                    y_max += self.plot_main_current_rounding

                # limit y axis scaling to 5 seconds and a min. change of 5% except for increased limits
                yl2 = self._y_limits[0]
                ml = (yl2[1] - yl2[0]) * AppConfig.plot.y_limit_scale_value
                if y_max>yl2[1] or y_min<yl2[0] or (ts>yl2[2] and (y_min>yl2[0]+ml or y_min<yl2[1]-ml)):
                    # self.debug(__name__, 'limits %s' % ([yl2,y_min,y_max,ts,ml,tmp]))
                    yl2[0] = y_min
                    yl2[1] = y_max
                    yl2[2] = ts + AppConfig.plot.y_limit_scale_time
                    self.ax[0].set_ylim(top=y_max, bottom=y_min)

                    # plt.xticks(np.arange(min(x), max(x)+1, 1.0))

            # shared x limits for all axis
            if x_max!=None:
                for ax in self.ax:
                    ax.set_xlim(left=x_max-self.get_time_scale(), right=x_max)

            # for ax in self.ax:
            #     ax.autoscale_view()
            #     ax.relim()


            if self.popup_hide_timeout!=None and ts>self.popup_hide_timeout:
                self.show_popup(None)

            if blt:
                self.plot_bitblt()

            # DEBUG DISPLAY

            if AppConfig._debug:
                data_n = 0
                for channel, values in self.values.items():
                    for type, items in values.items():
                        data_n += len(items)
                    # parts.append('%u:#%u' % (channel, len(values[0])))
                    # for i in range(0, len(values)):
                    #     data_n += len(values[i])

                p = [
                    'fps=%.2f' % self.get_plot_fps(),
                    'data=%u' % data_n
                ]
                for key, val in self.stats.items():
                    if isinstance(val, float):
                        val = '%.4f' % val
                    p.append('%s=%s' % (key, val))

                p.append('comp_rrq=%u' % (self.compressed_min_records<AppConfig.plot.compression.min_records and (AppConfig.plot.compression.min_records - self.compressed_min_records) or 0))

                self.debug_label.configure(text=' '.join(p))

        except ValueError as e:

            self.error(__name__, '%s' % e)

        except Exception as e:
            AppConfig._debug_exception(e)

