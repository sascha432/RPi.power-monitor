# RPI.power-monitor

Power Monitor for the INA3221 sensor.

- 3 Channels (Voltage, Current, Power, Energy Wh/Ah)
- MQTT support
- Home assistant auto discovery
- Runs headless as service or with tkinter GUI
- Fullscreen mode
- Idle detection to reduce CPU load
- Custom GUI config with live preview

![GUI](https://raw.githubusercontent.com/sascha432/RPI.power-monitor/master/images/power_monitor1.jpg)

## Requirements

- python3
- smbus
- numpy

Tested with Python 3.7.8 on windows and Python 3.7.3 on debian (armv7l)
### Optional python packges

- paho.mqtt.client for MQTT support
- commentjson for reading configuration files with comments
- matplotlib and tkinter for the GUI
- colorlog

## Launching power monitor

Start the power monitor with `python3 ./power_monitor.py`

### Creating a symlink in /usr/bin

Make sure the first line in `power_monitor.py` points to the correct python interpreter

```
chmod 755 power_monitor.py
ln -s "$(pwd)/power_monitor.py" /usr/bin/power_monitor
```

### Configuration

The configuration is loaded from `$HOME/.power_monitor/config.json` by default.

Display the configuration using config.json inside the current working directory with

`power_monitor --config . --check --print=json`

or

`power_monitor --config . --check --print=yaml`

### Running with GUI

Set the DISPLAY environment variable before starting the monitor or pass the display with `--display=:0`



#### GUI configuration and live preview

The configuration is stored in `gui-<channels>-<geometry>-auto.json`. To modify it, remove `-auto` from the filename.
To reload the configuration while running, press Alt-F5.

### Running headless

Pass the argument `--headless` to disable the GUI
### Command line options

```
usage: power_monitor.py [-h] [-C CONFIG_DIR] [--display DISPLAY] [--headless]
                        [--fullscreen] [--daemon] [--verbose] [--check]
                        [--print {json,yaml}] [--debug]

Power Monitor

optional arguments:
  -h, --help            show this help message and exit
  -C CONFIG_DIR, --config-dir CONFIG_DIR
                        location of config.json and energy.json
  --display DISPLAY     override DISPLAY variable
  --headless            start without GUI
  --fullscreen          start in fullscreen mode
  --daemon              run as daemon
  --verbose             enable debug output
  --check               check configuration
  --print {json,yaml}   check and display configuration
  --debug               enable debug mode
```

## GUI control

### Touch events

- Left center to bottom: Toggle displayed plots (Main plot, voltage)
- Right center to bottom: Toggle main plot from (Current, power and aggregated power)
- Top right and left corner: Increase/decrease displayed timeframe

### Default keyboard shortcuts

The keyboard bindings can be configured in the section `gui.key_bindings` in `config.json`

| Key | Action |
| - | - |
| F1 | Menu |
| Escape | Leave fullscreen |
| F11 | Toggle full screen |
| F2 | Change plot visibility |
| F3 | Cycle through current, power and aggregated power |
| F4 | Toggle energy Ah/Wh |
| Alt-F5 | Reload GUI configuration |
| Control-F5 | Reload GUI configuration |
| Control-F10 | Reset plot and clear all data |
| Alt-F4 | Quit |

For more bindings, check `power_monitor --check --print=yaml --section=app.gui.keybindings`
