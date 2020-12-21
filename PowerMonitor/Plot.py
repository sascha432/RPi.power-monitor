#
# Author: sascha_lammers@gmx.de
#

import sys
import time
import matplotlib.ticker as ticker
import numpy as np
import EventManager
import json
from collections import namedtuple
from . import FormatFloat, Sensor, Tools, PLOT_VISIBILITY, PLOT_PRIMARY_DISPLAY, ANIMATION, SCHEDULER_PRIO, DISPLAY_ENERGY

class Plot(Sensor.Sensor):

    def __init__(self):
        global AppConfig
        AppConfig = self._app_config

        self._time_scale_num = 0
        self._time_scale_min_time = 5
        self._time_scale_items = self.get_time_scale_list()
        self._plot_thread_state = {'quit': False}
        #todo
        self.ani = None
        self.ani_interval = 1000

    def start(self):
        # self._plot_thread_listener = EventManager.Listener('plot', self._event)
        # self.thread_daemonize('plot_thread', self.plot_thread)
        pass

    def init_vars(self):
        self.debug(__name__, 'init_vars')
        self._time_scale_num = 0
        self._ax_data = []

    def ticks_params(self):
        return {
            'labelcolor': self.PLOT_TEXT,
            'axis': 'y',
            'labelsize': self._fonts.plot_font.cget('size'),
            'width': 0,
            'length': 0,
            'pad': 1
        }

    def init_plot(self):

        global Gui, tk, ttk, font, tkinter, animation, Figure, FigureCanvasTkAgg, NavigationToolbar2Tk
        Gui, tk, ttk, font, tkinter, animation, Figure, FigureCanvasTkAgg, NavigationToolbar2Tk = self.import_tkinter()

        # init TK
        self._gui.configure(bg=self.BG_COLOR)

        top = tk.Frame(self._gui)
        top.pack(side=tkinter.TOP)
        top.place(relwidth=1.0, relheight=1.0)

        # plot
        self.fig = Figure(figsize=(3, 3), dpi=self.PLOT_DPI, tight_layout=True, facecolor=self.BG_COLOR)

        # axis
        ax = self.fig.add_subplot(self.get_plot_geometry(0, PLOT_VISIBILITY.BOTH), facecolor=self.PLOT_BG)
        ax.autoscale(False)
        ax.margins(0.01, 0.01)
        self._ax_data.append(namedtuple('AxisData%u' % len(self._ax_data), ('ax', 'background', 'lines', 'legend')))
        self._ax_data[-1].ax = ax
        self._ax_data[-1].lines = []

        for channel in self.channels:
            ax = self.fig.add_subplot(self.get_plot_geometry(channel.number, PLOT_VISIBILITY.BOTH), facecolor=self.PLOT_BG)
            self._ax_data.append(namedtuple('AxisData%u' % len(self._ax_data), ('ax', 'background', 'lines')))
            self._ax_data[-1].ax = ax
            self._ax_data[-1].lines = []

        self.set_plot_geometry()

        for data in self._ax_data:
            data.ax.grid(True, color=self.PLOT_GRID, axis='both')
            data.ax.set_xticks([])
            data.ax.set_xticklabels([])
            ax.tick_params(**self.ticks_params())

        # add before reconfigure_axis
        for channel in self.channels:
            ax = self._ax_data[channel.number].ax
            ax.ticklabel_format(axis='y', style='plain', useOffset=False)

        # lines
        self.reconfigure_axis()

        # top labels

        label_config = {
            'font': self._fonts.label_font,
            'bg': self.BG_COLOR,
            'fg': 'white',
            'anchor': 'center'
        }

        # top frame for enabled channels
        # 1 colum per active channel
        top_frames = [
            { 'relx': 0.0, 'rely': 0.0, 'relwidth': 1.0, 'relheight': 0.12 },
            { 'relx': 0.0, 'rely': 0.0, 'relwidth': 0.5, 'relheight': 0.17 },
            { 'relx': 0.0, 'rely': 0.0, 'relwidth': 0.33, 'relheight': 0.17 }
        ]
        top_frame = top_frames[len(self.channels) - 1]

        # add plot to frame before labels for the z order

        self.canvas = FigureCanvasTkAgg(self.fig, self._gui)
        self.canvas.get_tk_widget().pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=0, padx=0)
        # self.canvas.get_tk_widget().pack()

        gui = {}
        try:
            with open(AppConfig.get_filename(self.get_gui_scheme_config_filename()), 'r') as f:
                gui = json.loads(f.read())
        except Exception as e:
            self.debug(__name__, 'failed to write GUI config: %s', e)
            gui = {}

        gui['geometry'] = self._geometry_info

        padding_y = { 1: 100, 2: 70, 3: 70 }
        pady = -1 / padding_y[len(self.channels)]
        padx = -1 / 50
        y = top_frame['relheight'] + pady
        if 'plot_placement' in gui:
            plot_placement = gui['plot_placement']
        else:
            plot_placement = {
                'relwidth': 1.0-padx,
                'relheight': 1-y-pady*2,
                'rely': y,
                'relx': padx
            }
            gui['plot_placement'] = plot_placement

        self.ani_interval = AppConfig.plot.refresh_interval
        self.canvas.get_tk_widget().place(in_=top, **plot_placement)

        # label placement for the enabled channels
        if 'label_places' in gui:
            places = gui['label_places'].copy()
        else:
            places = []
            pad = 1 / 200
            pad2 = pad * 2
            if len(self.channels)==1:
                # 1 row 4 cols
                w = 1 / 4
                h = 1.0
                for i in range(0, 4):
                    x = i / 4
                    places.append({'relx': x + pad, 'rely': pad, 'relwidth': w - pad2, 'relheight': h - pad2})
            elif len(self.channels)==2:
                # 2x 2 row 2 cols
                w = 1 / 2
                h = 1 / 2
                for i in range(0, 8):
                    x = (i % 2) / 2
                    y = (int(i / 2) % 2) * h
                    places.append({'relx': x + pad, 'rely': y + pad, 'relwidth': w - pad2, 'relheight': h - pad2})
            elif len(self.channels)==3:
                # 3x 2 row 2 cols
                w = 1 / 3
                h = 1 / 2
                for i in range(0, 12):
                    x = (i % 2) / 3
                    y = (int(i / 2) % 2) * h
                    places.append({'relx': x + pad, 'rely': y + pad, 'relwidth': w - pad2, 'relheight': h - pad2})
            gui['label_places'] = places.copy()

        for channel in self.channels:
            ch = int(channel)
            label_config['fg'] = channel.color

            frame = tk.Frame(self._gui, bg=self.BG_COLOR)
            frame.pack()
            frame.place(in_=top, **top_frame)
            top_frame['relx'] += top_frame['relwidth']

            label = tk.Label(self._gui, text="- V", **label_config)
            label.pack(in_=frame)
            label.place(in_=frame, **places.pop(0))
            self.labels[ch]['U'] = label

            label = tk.Label(self._gui, text="- A", **label_config)
            label.pack(in_=frame)
            label.place(in_=frame, **places.pop(0))
            self.labels[ch]['I'] = label

            label = tk.Label(self._gui, text="- W", **label_config)
            label.pack()
            label.place(in_=frame, **places.pop(0))
            self.labels[ch]['P'] = label

            label = tk.Label(self._gui, text="- Wh", **label_config)
            label.pack()
            label.place(in_=frame, **places.pop(0))
            self.labels[ch]['e'] = label

        frame = tk.Frame(self._gui, bg='#999999')
        frame.pack()
        frame.place(in_=top, relx=0.5, rely=2.0, relwidth=0.8, relheight=0.25, anchor='center')
        self.popup_frame = frame
        label = tk.Label(self._gui, text="", font=('Verdana', 26), bg='#999999', fg='#ffffff', anchor='center')
        label.pack(in_=self.popup_frame, fill=tkinter.BOTH, expand=True)
        self.popup_label = label
        self.popup_hide_timeout = None

        if AppConfig._debug:
            label = tk.Label(self._gui, text="", font=('Verdana', 12), bg='#333333', fg=self.TEXT_COLOR, anchor='nw', wraplength=self._gui.winfo_width()) #self._geometry_info[0])
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


    def update_y_ticks_primary(self, y, pos):
        if len(self._y_limits) and self._gui_config.plot_primary_display==PLOT_PRIMARY_DISPLAY.CURRENT:
            yl = self._y_limits[0]
            diff = yl[0] - yl[1]
            if diff<1.0:
                return '%d' % (int(y * 1000))
        return '%.2f' % y

    def update_y_ticks_secondary(self, y, pos):
        return '%.2f' % y

    def add_ticks(self):
        self._ax_data[0].ax.yaxis.set_major_locator(ticker.MaxNLocator(6))
        self._ax_data[0].ax.yaxis.set_major_formatter(ticker.FuncFormatter(self.update_y_ticks_primary))
        self._ax_data[1].ax.yaxis.set_major_formatter(ticker.FuncFormatter(self.update_y_ticks_secondary))
        for data in self._ax_data:
            data.ax.tick_params(**self.ticks_params())

    def legend(self):
        self._ax_data[0].legend = self._ax_data[0].ax.legend(['%u seconds' % self.get_time_scale()], handlelength=0, fontsize=self._fonts.plot_font.cget('size'), labelcolor=self.TEXT_COLOR, loc='lower center', frameon=False, borderpad=0.0, borderaxespad=0.2)

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

    # def get_plot_line(self, axis, channel):
    #     res = self._get_plot_line(axis, channel)
    #     self.debug(__name__, 'get_plot_line=%s axis=%d visibility %s', res, axis, str(self._gui_config.plot_visibility))
    #     return res

    def get_plot_line(self, axis, channel):
        # axis 0 - current(#channels), power(#channels) or aggregated powoer(1)
        if axis==0:
            if self._gui_config.plot_visibility==PLOT_VISIBILITY.VOLTAGE:
                return None
            elif self._gui_config.plot_primary_display==PLOT_PRIMARY_DISPLAY.AGGREGATED_POWER and channel!=0:
                return self._ax_data[0].lines[0]
            elif self._gui_config.plot_primary_display in(PLOT_PRIMARY_DISPLAY.CURRENT, PLOT_PRIMARY_DISPLAY.POWER):
                return self._ax_data[0].lines[channel]
        # axis 1 - voltage((#channels))
        elif axis==1 and self._gui_config.plot_visibility!=PLOT_VISIBILITY.PRIMARY:
            return self._ax_data[1].lines[channel]
        return None

    def reconfigure_axis(self):
        if not self._plot_lock.acquire(True, 5.0):
            self.error(__name__, 'reconfigure_axis could not acquire lock')
            return
        try:
            # update axis
            yfont = {'fontsize': int(self._fonts.plot_font.cget('size') * 1.3)}
            self.power_sum = []
            self.clear_y_limits(0)
            if self._gui_config.plot_primary_display==PLOT_PRIMARY_DISPLAY.CURRENT:
                values_type = 'I'
                values, items = self.get_plot_values(0, 0)
                self._main_plot_limits = (AppConfig.plot.current_top_margin, AppConfig.plot.current_bottom_margin, AppConfig.plot.current_rounding)
                self._ax_data[0].ax.set_ylabel('Current (A)', color=self.PLOT_TEXT, **yfont)
            elif self._gui_config.plot_primary_display==PLOT_PRIMARY_DISPLAY.POWER:
                values_type = 'P'
                values, items = self.get_plot_values(0, 1)
                self._main_plot_limits = (AppConfig.plot.power_top_margin, AppConfig.plot.power_bottom_margin, AppConfig.plot.power_rounding)
                self._ax_data[0].ax.set_ylabel('Power (W)', color=self.PLOT_TEXT, **yfont)
            elif self._gui_config.plot_primary_display==PLOT_PRIMARY_DISPLAY.AGGREGATED_POWER:
                values_type = 'Psum'
                values, items = self.get_plot_values(0, 2)
                self._main_plot_limits = (AppConfig.plot.power_top_margin, AppConfig.plot.power_bottom_margin, AppConfig.plot.power_rounding)
                self._ax_data[0].ax.set_ylabel('Aggregated Power (W)', color=self.PLOT_TEXT, **yfont)
            else:
                raise RuntimeError('reconfigure_axis: plot_primary_display %s' % (self._gui_config.plot_primary_display))

            # remove lines from axis 0
            self._ax_data[0].lines = []
            for line in self._ax_data[0].ax.get_lines():
                line.remove()

            if self._gui_config.plot_visibility in(PLOT_VISIBILITY.PRIMARY, PLOT_VISIBILITY.BOTH):
                # add required onces to axis 0
                for channel in self.channels:
                    line, = self._ax_data[0].ax.plot(self.values.time(), self.values.time(), color=channel._color_for(values_type), label=channel.name, linewidth=AppConfig.plot.line_width)
                    self._ax_data[0].lines.append(line)
                    if self._gui_config.plot_primary_display==PLOT_PRIMARY_DISPLAY.AGGREGATED_POWER:# and len(self._ax_data[0].lines)==1:
                        break

            # remove lines from axis 1
            self._ax_data[1].lines = []
            for line in self._ax_data[1].ax.get_lines():
                line.remove()

            if self._gui_config.plot_visibility in(PLOT_VISIBILITY.VOLTAGE, PLOT_VISIBILITY.BOTH):
                # add required onces to axis 1
                for channel in self.channels:
                    ax = self._ax_data[channel.number].ax
                    line, = ax.plot(self.values.time(), self.values[channel].voltage(), color=channel._color_for('U'), label=channel.name + ' U', linewidth=2)
                    self._ax_data[1].lines.append(line)

            self.legend()
            self.add_ticks()

            # for data in self._ax_data:
            #     for child in data.ax.get_children():
            #         print(type(child), child)

        finally:
            self._plot_lock.release()

    def plot_values(self, i):
        artists = []
        if not self._plot_lock.acquire(True, 0.1): # do not block the tk main thread
            self.error(__name__, 'plot_values could not acquire lock')
            return []
        try:
            update_required = False
            self.aggregate_sensor_values()

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

            # ---------------------------------------------------------------------------------------

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
                if line!=None:
                    values, items = self.get_plot_values(0, ch)
                    if x_max==None:
                        x_max = self.values.max_time()
                        x_min = x_max - self.get_time_scale()
                        display_idx = self.values.find_time_index(x_min, True)

                    # max. for all lines
                    y_max = max(y_max, max(items[display_idx:]))
                    y_min = min(y_min, min(items[display_idx:]))

                    # data
                    line.set_data(x_range, items)
                    artists.append(line)

                # axis 1
                line = self.get_plot_line(1, ch)
                if line!=None:
                    values, items = self.get_plot_values(1, ch)
                    # data
                    line.set_data(x_range, items)
                    artists.append(line)

                    # limits
                    ax = self._ax_data[channel.number].ax
                    # max. per channel
                    y_max1 = max(channel.voltage + 0.02, round(values.max_U(display_idx) * AppConfig.plot.voltage_top_margin / AppConfig.plot.voltage_rounding) * AppConfig.plot.voltage_rounding)
                    y_min1 = min(channel.voltage - 0.02, round((values.min_U(display_idx) * AppConfig.plot.voltage_bottom_margin + AppConfig.plot.voltage_rounding * 0.51) / AppConfig.plot.voltage_rounding) * AppConfig.plot.voltage_rounding)
                    ymi, yma = ax.get_ylim()
                    if y_max1!=yma or y_min1!=ymi:
                        update_required = True
                        ax.set_ylim(top=y_max1, bottom=y_min1)

                # top labels
                self.labels[ch]['U'].configure(text=fmt.format(values.avg_U(), 'V'))
                self.labels[ch]['I'].configure(text=fmt.format(values.avg_I(), 'A'))
                self.labels[ch]['P'].configure(text=fmt.format(values.avg_P(), 'W'))
                tmp = self._gui_config.plot_display_energy==DISPLAY_ENERGY.AH and ('ei', 'Ah') or ('ep', 'Wh')
                self.labels[ch]['e'].configure(text=fmt.format(self.energy[ch][tmp[0]], tmp[1]))

            # ---------------------------------------------------------------------------------------

            # axis 0 y limits
            if y_min!=sys.maxsize:
                tmp = (y_max, y_min)
                y_max = max(tmp[0] + 0.02, round(y_max * self._main_plot_limits[0] / self._main_plot_limits[2]) * self._main_plot_limits[2])
                y_min = min(tmp[1] - 0.02, max(0, round((y_min * self._main_plot_limits[1] - self._main_plot_limits[2] * 0.99) / self._main_plot_limits[2]) * self._main_plot_limits[2]))
                # if y_max == y_min:
                #     y_max += self._main_plot_limits[2]

                ax = self._ax_data[0].ax
                ymi, yma = ax.get_ylim()
                if y_max!=yma or y_min!=ymi:
                    update_required = True
                    ax.set_ylim(top=y_max, bottom=y_min)

                # # limit y axis scaling to 5 seconds and a min. change of 5% except for increased limits
                # yl2 = self._y_limits[0]
                # ml = (yl2[1] - yl2[0]) * AppConfig.plot.y_limit_scale_value
                # if y_max>yl2[1] or y_min<yl2[0] or (ts>yl2[2] and (y_min>yl2[0]+ml or y_min<yl2[1]-ml)):
                #     # self.debug(__name__, 'limits %' % ([yl2,y_min,y_max,ts,ml,tmp]))
                #     yl2[0] = y_min
                #     yl2[1] = y_max
                #     yl2[2] = ts + AppConfig.plot.y_limit_scale_time
                #     self._ax_data[0].ax.set_ylim(top=y_max, bottom=y_min)
                #     update_required = True

                #     # plt.xticks(np.arange(min(x), max(x)+1, 1.0))

            # shared x limits for all axis
            if x_max!=None:
                for data in self._ax_data:
                    data.ax.set_xlim(left=x_max-self.get_time_scale(), right=x_max)

            # for data in self._ax_data:
            #     data.ax.autoscale_view()
            #     data.ax.relim()

            # if self._gui_config.plot_visibility in(PLOT_VISIBILITY.BOTH, PLOT_VISIBILITY.PRIMARY):
            #     for line in self._ax_data[0].ax.lines:
            #         artists.append(line)
            #         # data.ax.draw_artist(line)
            # if self._gui_config.plot_visibility in(PLOT_VISIBILITY.BOTH, PLOT_VISIBILITY.VOLTAGE):
            #     for line in self._ax_data[1].ax.lines:
            #         artists.append(line)
                    # data.ax.draw_artist(line)

            # if blt:
            #     self.canvas.update()
            #     self.canvas.flush_events()


            if self.popup_hide_timeout!=None and ts>self.popup_hide_timeout:
                self.show_popup(None)

            self.power_sum = None

            artists.append(self._ax_data[0].legend)

            if update_required:
                self.info(__name__, 'UPDATE')
                self.canvas.draw()

                # data.ax.autoscale_view()
                # data.ax.relim()
                # for data in self._ax_data:
                #     for child in data.ax.get_children():
                #         artists.append(child)

# <class 'matplotlib.lines.Line2D'> Line2D(Channel 1 (5V))
# <class 'matplotlib.lines.Line2D'> Line2D(Channel 2 (12V))
# <class 'matplotlib.spines.Spine'> Spine
# <class 'matplotlib.spines.Spine'> Spine
# <class 'matplotlib.spines.Spine'> Spine
# <class 'matplotlib.spines.Spine'> Spine
# <class 'matplotlib.axis.XAxis'> XAxis(75.0,65.99999999999999)
# <class 'matplotlib.axis.YAxis'> YAxis(75.0,65.99999999999999)
# <class 'matplotlib.text.Text'> Text(0.5, 1.0, '')
# <class 'matplotlib.text.Text'> Text(0.0, 1.0, '')
# <class 'matplotlib.text.Text'> Text(1.0, 1.0, '')
# <class 'matplotlib.legend.Legend'> Legend
# <class 'matplotlib.patches.Rectangle'> Rectangle(xy=(0, 0), width=1, height=1, angle=0)
# <class 'matplotlib.lines.Line2D'> Line2D(Channel 1 (5V) U)
# <class 'matplotlib.spines.Spine'> Spine
# <class 'matplotlib.spines.Spine'> Spine
# <class 'matplotlib.spines.Spine'> Spine
# <class 'matplotlib.spines.Spine'> Spine
# <class 'matplotlib.axis.XAxis'> XAxis(328.63636363636357,318.0)
# <class 'matplotlib.axis.YAxis'> YAxis(328.63636363636357,318.0)
# <class 'matplotlib.text.Text'> Text(0.5, 1.0, '')
# <class 'matplotlib.text.Text'> Text(0.0, 1.0, '')
# <class 'matplotlib.text.Text'> Text(1.0, 1.0, '')
# <class 'matplotlib.patches.Rectangle'> Rectangle(xy=(0, 0), width=1, height=1, angle=0)
# <class 'matplotlib.lines.Line2D'> Line2D(Channel 2 (12V) U)
# <class 'matplotlib.spines.Spine'> Spine
# <class 'matplotlib.spines.Spine'> Spine
# <class 'matplotlib.spines.Spine'> Spine
# <class 'matplotlib.spines.Spine'> Spine
# <class 'matplotlib.axis.XAxis'> XAxis(328.63636363636357,65.99999999999999)
# <class 'matplotlib.axis.YAxis'> YAxis(328.63636363636357,65.99999999999999)
# <class 'matplotlib.text.Text'> Text(0.5, 1.0, '')
# <class 'matplotlib.text.Text'> Text(0.0, 1.0, '')
# <class 'matplotlib.text.Text'> Text(1.0, 1.0, '')
# <class 'matplotlib.patches.Rectangle'> Rectangle(xy=(0, 0), width=1, height=1, angle=0)


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

        except Exception as e:
            AppConfig._debug_exception(e)
        finally:
            self._plot_lock.release()

        return artists