#
# Author: sascha_lammers@gmx.de
#

import sys
import time
import matplotlib
import numpy as np
import EventManager
import copy
import json
from collections import namedtuple
from . import FormatFloat, Sensor, Tools, PLOT_VISIBILITY, PLOT_PRIMARY_DISPLAY, SCHEDULER_PRIO, DISPLAY_ENERGY

class NamedTuples:
    PlotData = namedtuple('PlotData', ['time', 'P', 'channels'])
    PlotChannel = namedtuple('PlotChannel', ['U', 'I', 'P'])
    PlotMargin = namedtuple('PlotMargin', ('top', 'bottom'))

class Plot(Sensor.Sensor):

    def __init__(self):
        global AppConfig
        AppConfig = self._app_config

        self._time_scale_num = 0
        self._time_scale_min_time = 5
        self._time_scale_items = self.get_time_scale_list()
        self._plot_thread_state = {'quit': False}
        self.ani = None
        self._canvas_update_required = False

    def start(self):
        # self._plot_thread_listener = EventManager.Listener('plot', self._event)
        # self.thread_daemonize('plot_thread', self.plot_thread)
        pass

    def init_vars(self):
        self.debug(__name__, 'init_vars')

        # []*4
        # [0] = axis 0, lines[]*3 current or power channel 1-3
        # [1] = axis 1, lines[]*1 voltage channel 1
        # [2] = axis 2, lines[]*1 voltage channel 2
        # [3] = axis 3, lines[]*1 voltage channel 3
        self._ax_data = []
        self._time_scale_num = 0

    def ticks_params(self):
        return {
            'labelcolor': self.PLOT_TEXT,
            'axis': 'y',
            'labelsize': AppConfig.plot.font_size,
            'width': 0,
            'length': 0,
            'pad': 1
        }

    def init_plot(self):

        globals().update(self.import_tkinter())

        # init TK
        self._gui.configure(bg=self.BG_COLOR)

        top = tk.Frame(self._gui)
        top.pack(side=tkinter.TOP)
        top.place(relwidth=1.0, relheight=1.0)

        # plot
        self.fig = Figure(figsize=(3, 3), dpi=self.geometry.dpi, tight_layout=True, facecolor=self.BG_COLOR)

        # axis 0
        ax = self.fig.add_subplot(self.get_plot_geometry(0, PLOT_VISIBILITY.BOTH), facecolor=self.PLOT_BG)
        self._ax_data.append(namedtuple('AxisData%u' % len(self._ax_data), ('ax', 'background', 'lines', 'legend', 'datax', 'datay')))
        self._ax_data[-1].ax = ax
        self._ax_data[-1].lines = []

        # axis 1-3
        for channel in self.channels:
            ax = self.fig.add_subplot(self.get_plot_geometry(channel.number, PLOT_VISIBILITY.BOTH), facecolor=self.PLOT_BG, sharex=self._ax_data[0].ax)
            self._ax_data.append(namedtuple('AxisData%u' % len(self._ax_data), ('ax', 'background', 'lines', 'datay', 'hline')))
            self._ax_data[-1].ax = ax
            self._ax_data[-1].lines = []

        self.set_plot_geometry()

        for data in self._ax_data:
            data.ax.grid(True, color=self.PLOT_GRID, axis='both', linewidth=AppConfig.plot.grid_line_width)
            # data.ax.set_xticks([])
            # data.ax.set_xticklabels([])
            data.ax.tick_params(**self.ticks_params())
            # data.ax.ticklabel_format(axis='y', style='plain', useOffset=False)
            ax.autoscale(False)
            ax.margins(0, 0)

        # # add before reconfigure_axis
        # idx = 1
        # for channel in enumerate(self.channels):
        #     self._ax_data[idx].ax.ticklabel_format(axis='y', style='plain', useOffset=False)
        #     idx += 1

        # lines
        self.reconfigure_axis()

        # top labels

        label_config = {
            'font': self._fonts.label_font,
            'bg': self.BG_COLOR,
            'fg': 'white',
            'anchor': 'center'
        }

        if len(self.channels)==1:
            top_frame = { 'relx': 0.0, 'rely': 0.0, 'relwidth': 1.0, 'relheight': 0.12 }
        elif len(self.channels)==2:
            top_frame = { 'relx': 0.0, 'rely': 0.0, 'relwidth': 1.0, 'relheight': 0.17 }
        else:
            top_frame = { 'relx': 0.0, 'rely': 0.0, 'relwidth': 1.0, 'relheight': 0.17 }

        # add plot to frame before labels for the z order

        self.canvas = FigureCanvasTkAgg(self.fig, self._gui)
        self.canvas.get_tk_widget().pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=0, padx=0)
        # self.canvas.get_tk_widget().pack()

        gui = {}
        try:
            with open(AppConfig.get_filename(self.get_gui_scheme_config_filename()), 'r') as f:
                gui = json.loads(f.read())
        except Exception as e:
            self.debug(__name__, 'failed to read GUI config: %s', e)
            gui = {}

        gui['geometry'] = dict(self.geometry)

        if not 'plot_placement' in gui:
            gui['plot_placement'] = {
                'relwidth': 1.0,
                'relheight': 1.0,
                'rely': 0,
                'relx': 0,
                'padx': -500,
                'pady': -500
            }

        plot_placement = copy.deepcopy(gui['plot_placement'])
        plot_placement['rely'] += top_frame['relheight'] + (1 / plot_placement['pady'])
        plot_placement['relx'] += 1 / plot_placement['padx']
        plot_placement['relwidth'] -= (2 / plot_placement['padx'])
        plot_placement['relheight'] -= top_frame['relheight'] + (2 / plot_placement['pady'])
        del plot_placement['padx']
        del plot_placement['pady']

        self.canvas.get_tk_widget().place(in_=top, **plot_placement)

        # label placement for the enabled channels
        if not 'label_places' in gui:
            places = []
            padx = 200
            pady = 200
            if len(self.channels)==1:
                # 1x 1 row 4 cols
                cols = 4
                rows = 1
                num = 4
            elif len(self.channels)==2:
                # 2x 2 rows 2 cols
                cols = 2
                rows = 2
                num = 8
            elif len(self.channels)==3:
                # 3x 2 rows 2 cols
                cols = 2
                rows = 2
                num = 12

            w = 1 / cols
            h = 1 / rows
            for i in range(0, num):
                x = (i % cols) / cols
                y = (int(i / rows) % rows) * h
                places.append({'relx': x, 'rely': y, 'relwidth': w, 'relheight': h, 'padx': padx, 'pady': pady})
            gui['label_places'] = places

        places = copy.deepcopy(gui['label_places'])
        for item in places:
            item['relx'] += 1 / item['padx']
            item['rely'] += 1 / item['pady']
            item['relwidth'] += 2 / item['padx']
            item['relheight'] += 2 / item['pady']
            del item['padx']
            del item['pady']

        for idx, channel in enumerate(self.channels):
            label_config['fg'] = channel.color
            # label_config['bg'] = 'yellow'
            label_config['bg'] = self.BG_COLOR

            # frame_bgcolor = 'red'
            frame_bgcolor = self.BG_COLOR
            frame = tk.Frame(self._gui, bg=frame_bgcolor)
            frame.pack()
            tmp = copy.copy(top_frame)
            tmp['relwidth'] /= len(self.channels)
            tmp['relx'] += tmp['relwidth'] * idx
            frame.place(in_=top, **tmp)

            label = tk.Label(self._gui, text="- V", **label_config)
            label.pack(in_=frame)
            label.place(in_=frame, **places.pop(0))
            self.labels[idx]['U'] = label

            label = tk.Label(self._gui, text="- A", **label_config)
            label.pack(in_=frame)
            label.place(in_=frame, **places.pop(0))
            self.labels[idx]['I'] = label

            label = tk.Label(self._gui, text="- W", **label_config)
            label.pack()
            label.place(in_=frame, **places.pop(0))
            self.labels[idx]['P'] = label

            label = tk.Label(self._gui, text="- Wh", **label_config)
            label.pack()
            label.place(in_=frame, **places.pop(0))
            self.labels[idx]['e'] = label

        if not 'info_popup' in gui:
            gui['info_popup'] = {
                'frame': {
                    'relx': 0.15,
                    'rely': 0.26,
                    'relwidth': 0.7,
                    'relheight': 0.6,
                },
                'label': {
                    'bg': self.POPUP_BG_COLOR,
                    'fg': self.POPUP_TEXT,
                    'anchor': 'center',
                },
                'font': ('Verdana', 26)
            }

        info_popup = gui['info_popup']

        self.popup_frame = tk.Frame(self._gui, bg=info_popup['label']['bg'])
        self._popup_placement = info_popup['frame']

        label = tk.Label(self._gui, text="", font=info_popup['font'], **info_popup['label'])
        label.pack(in_=self.popup_frame, fill=tkinter.BOTH, expand=True)
        self.popup_label = label
        self.popup_hide_timeout = None

        if AppConfig._debug:
            label = tk.Label(self._gui, text="", font=('Verdana', 12), bg='#333333', fg=self.TEXT_COLOR, anchor='nw', wraplength=self._gui.winfo_width())
            label.pack()
            label.place(in_=top, relx=0.0, rely=1.0-0.135 + 2.0, relwidth=1.0, relheight=0.13)
            self.debug_label = label
            self.debug_label_state = 2
        try:
            with open(AppConfig.get_filename(self.get_gui_scheme_config_filename(True)), 'w') as f:
                f.write(json.dumps(gui, indent=2))
        except Exception as e:
            self.debug(__name__, 'failed to write GUI config: %s', e)

        self.canvas.get_tk_widget().bind('<Button-1>', self.button_1)
        self.canvas.draw()


    def update_y_ticks_primary(self, y, pos):
        if self._gui_config.plot_primary_display==PLOT_PRIMARY_DISPLAY.CURRENT:
            ymin, ymax = self._ax_data[0].ax.get_ylim()
            diff = ymax - ymin
            if diff<1.0:
                return '%d' % (int(y * 1000))
        return '%.2f' % y

    def update_y_ticks_secondary(self, y, pos):
        return '%.2f' % y

    def add_ticks(self):
        self._ax_data[0].ax.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(6, steps=[1,2,5,10]))
        self._ax_data[0].ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(self.update_y_ticks_primary))

        if self._gui_config.plot_visibility==PLOT_VISIBILITY.VOLTAGE:
            n = 8
        else:
            n = len(self.channels) > 1 and 3 or 6
        for idx, channel in enumerate(self.channels):
            ax = self._ax_data[idx + 1].ax
            ax.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(n))
            ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(self.update_y_ticks_secondary))
            ax.xaxis.set_major_formatter(matplotlib.ticker.NullFormatter())

        steps = (5, 10, 15, 30, 60, 120, 300, 900, 1800, 3600)
        step_size = None
        max_steps = 5
        if self._gui_config.plot_visibility==PLOT_VISIBILITY.PRIMARY:
            max_steps = 8
        for data in self._ax_data:
            for step in steps:
                n = self.get_time_scale() // step
                if n>=1 and n<=max_steps:
                    data.ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(n))
                    step_size = step
                    break
            data.ax.xaxis.set_major_formatter(matplotlib.ticker.NullFormatter())
            data.ax.tick_params(**self.ticks_params())

        if step_size:
            info = '%s / %u seconds' % (self.get_time_scale(), step_size)
        else:
            data.ax.xaxis.set_major_locator(matplotlib.ticker.NullLocator())
            info = '%u seconds' % self.get_time_scale()
        self._ax_data[0].legend = self._ax_data[0].ax.legend([info], handlelength=0, fontsize=AppConfig.plot.font_size, labelcolor=self.TEXT_COLOR, loc='lower center', frameon=False, borderpad=0.0, borderaxespad=0.2)

    def get_plot_geometry(self, plot_number, visibility=None):
        if visibility==None:
            visibility = self._gui_config.plot_visibility
        if plot_number==0:
            if visibility==PLOT_VISIBILITY.BOTH:
                return 121
            elif visibility==PLOT_VISIBILITY.PRIMARY:
                return 111
        else:
            if visibility==PLOT_VISIBILITY.BOTH:
                return (len(self.channels) * 100) + 20 + (plot_number * 2)
            if visibility==PLOT_VISIBILITY.VOLTAGE:
                return 100 + (len(self.channels) * 10) + (plot_number)
        return None

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
            self.plot_updated_times.pop(1)
        self.plot_updated = ts

        if ts>self.plot_updated_times[0]:
            diff = ts - (self.plot_updated_times[0] - 15)
            self.plot_updated_times[0] = ts + 15
            n = self._read_count
            avg = n / diff
            self._read_count = 0
            self.debug(__name__, 'fps %.2f items %u sensor=%.2f/s (%u)', self.get_plot_fps(), len(self.values._t), avg, n)

    def get_plot_fps(self):
        return 1.0 / max(0.001, len(self.plot_updated_times)>2 and np.average(self.plot_updated_times[1:]) or 10000000)

    def get_plot_data(self, axis, channel):
        if axis==0:
            if self._gui_config.plot_visibility!=PLOT_VISIBILITY.VOLTAGE:
                if self._gui_config.plot_primary_display==PLOT_PRIMARY_DISPLAY.AGGREGATED_POWER:
                    if channel!=0:
                        return (None, None, None)
                    return (self._ax_data[0].lines[0], self._data.P, self._ax_data[0].ax)
                if self._gui_config.plot_primary_display==PLOT_PRIMARY_DISPLAY.CURRENT:
                    return (self._ax_data[0].lines[channel], self._data.channels[channel].I, self._ax_data[0].ax)
                if self._gui_config.plot_primary_display==PLOT_PRIMARY_DISPLAY.POWER:
                    return (self._ax_data[0].lines[channel], self._data.channels[channel].P, self._ax_data[0].ax)

        elif axis in (1, 2, 3) and self._gui_config.plot_visibility!=PLOT_VISIBILITY.PRIMARY:
            return (self._ax_data[axis].lines[0], self._data.channels[channel].U, self._ax_data[axis].ax)

        return (None, None, None)

    def set_plot_geometry(self):
        idx = 0
        for data in self._ax_data:
            ax = data.ax
            n = self.get_plot_geometry(idx)
            self.debug(__name__, 'idx=%u visibility=%s get_plot_geometry=%s', idx, str(self._gui_config.plot_visibility), n)
            if n!=None:
                ax.set_visible(True)
                ax.change_geometry(int(n / 100) % 10, int(n / 10) % 10, int(n) % 10)
            elif ax:
                ax.set_visible(False)
            idx += 1

    def reconfigure_axis(self):
        if not self._plot_lock.acquire(False):
            self.error(__name__, 'reconfigure_axis could not acquire lock')
            return
        try:
            # update axis
            yfont = {'fontsize': AppConfig.plot.font_size * 1.3}
            self.y_limit_clear(0)
            if self._gui_config.plot_visibility!=PLOT_VISIBILITY.VOLTAGE:
                if self._gui_config.plot_primary_display==PLOT_PRIMARY_DISPLAY.CURRENT:
                    self._plot_margin = NamedTuples.PlotMargin(top=AppConfig.plot.current_top_margin, bottom=AppConfig.plot.current_bottom_margin)
                    self._ax_data[0].ax.set_ylabel('Current (A)', color=self.PLOT_TEXT, **yfont)
                elif self._gui_config.plot_primary_display==PLOT_PRIMARY_DISPLAY.POWER:
                    self._plot_margin = NamedTuples.PlotMargin(top=AppConfig.plot.power_top_margin, bottom=AppConfig.plot.power_bottom_margin)
                    self._ax_data[0].ax.set_ylabel('Power (W)', color=self.PLOT_TEXT, **yfont)
                elif self._gui_config.plot_primary_display==PLOT_PRIMARY_DISPLAY.AGGREGATED_POWER:
                    self._plot_margin = NamedTuples.PlotMargin(top=AppConfig.plot.power_top_margin, bottom=AppConfig.plot.power_bottom_margin)
                    self._ax_data[0].ax.set_ylabel('Aggregated Power (W)', color=self.PLOT_TEXT, **yfont)
                else:
                    raise RuntimeError('reconfigure_axis: plot_primary_display %s' % (self._gui_config.plot_primary_display))

            # remove all lines from axis 0-3
            idx = 0
            for data in self._ax_data:
                for line in data.ax.get_lines():
                    line.remove()
                self._ax_data[idx].lines = []
                idx += 1

            values = []

            # primary plot current or for power for all channels
            data = self._ax_data[0]
            if self._gui_config.plot_visibility in(PLOT_VISIBILITY.PRIMARY, PLOT_VISIBILITY.BOTH):
                if self._gui_config.plot_primary_display==PLOT_PRIMARY_DISPLAY.AGGREGATED_POWER:
                    line, = data.ax.plot(values, values, color=self.channels[0]._color_for('Psum'), label='Aggregated Power (W)', linewidth=AppConfig.plot.line_width)
                    data.lines.append(line)
                else:
                    for idx, channel in enumerate(self.channels):
                        if self._gui_config.plot_primary_display==PLOT_PRIMARY_DISPLAY.CURRENT:
                            line, = data.ax.plot(values, values, color=channel._color_for('I'), label=channel.name + ' I', linewidth=AppConfig.plot.line_width)
                            data.lines.append(line)
                        elif self._gui_config.plot_primary_display==PLOT_PRIMARY_DISPLAY.POWER:
                            line, = data.ax.plot(values, values, color=channel._color_for('P'), label=channel.name + ' P', linewidth=AppConfig.plot.line_width)
                            data.lines.append(line)

            # secondary plots, voltage per axis
            if self._gui_config.plot_visibility in(PLOT_VISIBILITY.VOLTAGE, PLOT_VISIBILITY.BOTH):
                for idx, channel in enumerate(self.channels):
                    ax = self._ax_data[idx + 1].ax
                    self._ax_data[idx + 1].hline = ax.axhline(channel.voltage, color=channel._color_for('hline'), linewidth=AppConfig.plot.line_width, ls='dotted')
                    line, = ax.plot(values, values, color=channel._color_for('U'), label=channel.name + ' U', linewidth=AppConfig.plot.line_width)
                    self._ax_data[idx + 1].lines = [line]

                    if not self._raw_values:
                        if channel.y_limits.voltage_max!=None:
                            ax.set_ylim(top=channel.y_limits.voltage_max)
                        if channel.y_limits.voltage_min!=None:
                            ax.set_ylim(bottom=channel.y_limits.voltage_min)

            self.add_ticks()

            # for data in self._ax_data:
            #     for child in data.ax.get_children():
            #         print(type(child), child)
            # print(len(self._ax_data))
            # i1 = 0
            # for data in self._ax_data:
            #     i2 = 0
            #     print(i1, data, len(data.ax.lines))
            #     for line in data.ax.lines:
            #         print(i1, i2, data, line)
            #         i2 += 1
            #     i1 += 1

        finally:
            self._plot_lock.release()

    def plot_get_all_artists(self):
        artists = []
        for data in self._ax_data:
            if data.ax.get_visible():
                artists.extend(data.lines)
                for child in data.ax.get_children():
                    if isinstance(child, (matplotlib.legend.Legend, matplotlib.text.Text)):
                        artists.append(child)
        return artists


    def plot_values(self, i):
        artists = []
        if not self._plot_lock.acquire(True, 0.2): # do not block the tk main thread
            self.error(__name__, 'plot_values could not acquire lock')
            return self.plot_get_all_artists()
        try:
            if not self.aggregate_sensor_values():
                return self.plot_get_all_artists()

            fmt = FormatFloat.FormatFloat(4, 5, prefix=FormatFloat.PREFIX.M, strip=FormatFloat.STRIP.NONE)
            fmt.set_precision('m', 1)

            # ---------------------------------------------------------------------------------------
            if not self._data_lock.acquire(True, 0.2):
                return self.plot_get_all_artists()
            try:
                if AppConfig._debug:
                    self._validate_array_len('plot')

                self.plot_count_fps()

                ts = time.monotonic()
                y_max0 = 0
                y_min0 = sys.maxsize

                x_max = self.values.max_time()
                x_min = x_max - self.get_time_scale()

                dtime = np.array(self.values._t)
                display_idx = np.searchsorted(dtime, x_min)

                aggregatedP = None
                channels = []
                tmp = []
                for values in self.values.values():
                    U = np.array(values.U[display_idx:])
                    I = np.array(values.I[display_idx:])
                    P = np.array(values.P[display_idx:])
                    tmp.append(P)
                    channels.append(NamedTuples.PlotChannel(U=U, I=I, P=P))

                if self._gui_config.plot_primary_display==PLOT_PRIMARY_DISPLAY.AGGREGATED_POWER:
                    aggregatedP = np.array(tmp).sum(axis=0)

                # move last to 0 that the grid does not move and the reverse order is preserved
                time_idx = np.subtract(self.values._t[display_idx:], self.values._t[-1])
                x_min = -self.get_time_scale()
                x_max = 0

                self._data = NamedTuples.PlotData(time=time_idx, P=aggregatedP, channels=channels)
                data = self._data

            finally:
                self._data_lock.release()


            # ---------------------------------------------------------------------------------------
            for idx, channel in enumerate(self.channels):

                # axis 0
                line, values, ax = self.get_plot_data(0, idx)
                if line!=None:

                    y_max0 = max(y_max0, np.amax(values))
                    y_min0 = min(y_min0, np.amin(values))

                    line.set_data(data.time, values)
                    artists.append(line)

                # axis 1-3
                line, values, ax = self.get_plot_data(idx + 1, idx)
                if line!=None:

                    line.set_data(data.time, values)
                    artists.append(line)

                    artists.append(self._ax_data[idx + 1].hline)

                    max_val = np.amax(values)
                    min_val = np.amin(values)

                    # limits per channel
                    if self._raw_values or channel.y_limits.voltage_max==None:
                        y_max1 = round(max_val * AppConfig.plot.voltage_top_margin, 2)
                    else:
                        y_max1 = channel.y_limits.voltage_max
                    if self._raw_values or channel.y_limits.voltage_min==None:
                        y_min1 = round(min_val * AppConfig.plot.voltage_bottom_margin, 2)
                    else:
                        y_min1 = channel.y_limits.voltage_min

                    if self.y_limit_has_changed(idx + 1, y_min1, y_max1):
                        self._canvas_update_required = True
                        self.y_limit_update(idx + 1, y_min1, y_max1)
                        ax.set_ylim(top=y_max1, bottom=y_min1)

                # top labels, one per channel

                xpos = x_max - max(1.0, AppConfig.plot.display_top_values_mean_time)
                avg_idx = np.searchsorted(data.time, xpos)

                if self._raw_values:
                    labelU_text = round(np.mean(data.channels[idx].U[avg_idx:]), 1)
                    labelI_text = round(np.mean(data.channels[idx].I[avg_idx:]), 1)
                    labelP_text = '%.2E' % round(np.mean(data.channels[idx].P[avg_idx:]), 1)
                    labelE_text = ''
                else:
                    labelU_text = fmt.format(np.mean(data.channels[idx].U[avg_idx:]), 'V')
                    labelI_text = fmt.format(np.mean(data.channels[idx].I[avg_idx:]), 'A')
                    labelP_text = fmt.format(np.mean(data.channels[idx].P[avg_idx:]), 'W')
                    tmp = self._gui_config.plot_display_energy==DISPLAY_ENERGY.AH and ('ei', 'Ah') or ('ep', 'Wh')
                    labelE_text = fmt.format(self.energy[idx][tmp[0]], tmp[1])

                self.labels[idx]['U'].configure(text=labelU_text)
                self.labels[idx]['I'].configure(text=labelI_text)
                self.labels[idx]['P'].configure(text=labelP_text)
                self.labels[idx]['e'].configure(text=labelE_text)

            # ---------------------------------------------------------------------------------------

            # axis 0 y limits
            if y_min0!=sys.maxsize:
                y_max0 = round(y_max0 * self._plot_margin.top, 2)
                y_min0 = round(y_min0 * self._plot_margin.bottom, 2)

                if self.y_limit_has_changed(0, y_min0, y_max0):
                    self._canvas_update_required = True
                    self.y_limit_update(0, y_min0, y_max0)
                    self._ax_data[0].ax.set_ylim(top=y_max0, bottom=y_min0)

            # x is shared
            if x_max!=x_min:
                self._ax_data[0].ax.set_xlim(left=x_min, right=x_max)
                # self._ax_data[0].ax.set_xlim(left=x_max, right=x_min)
                # for data in self._ax_data:
                #     data.ax.set_xlim(left=x_min, right=x_max)

            if self.popup_hide_timeout!=None and ts>self.popup_hide_timeout:
                self.show_popup(None)

            artists.append(self._ax_data[0].legend)

            # data.ax.autoscale_view()
            # data.ax.relim()
            # for data in self._ax_data:
            #     for child in data.ax.get_children():
            #         artists.append(child)


            # full update required
            if self._canvas_update_required:
                self._canvas_update_required = False
                # artists = []
                # for data in self._ax_data:
                #     if data.ax.get_visible():
                #         for child in data.ax.get_children():
                #             print(type(child))
                #             if isinstance(child, (matplotlib.axis.YAxis, matplotlib.legend.Legend, matplotlib.text.Text)):
                #             # if isinstance(child, (matplotlib.spines.Spine, matplotlib.axis.XAxis, matplotlib.legend.Legend, matplotlib.text.Text)):
                #                 artists.insert(0, child)
                # print(artists)
                self.canvas.draw()
                artists = self.plot_get_all_artists()

        finally:
            self._plot_lock.release()

        self.update_debug_info()

        return artists


    def update_debug_info(self):

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
