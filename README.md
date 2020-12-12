# RPI.power-monitor

Power Monitor for the INA3221 sensor.

- 3 Channels (Voltage, Current, Power, Energy Wh/Ah)
- Runs headless as service or with tkinter GUI
- Fullscreen mode
- Backlight detection to reduce CPU load
- MQTT support
- Home assistant auto discovery
- Custom GUI config with live preview

![GUI](https://raw.githubusercontent.com/sascha432/RPI.power-monitor/master/images/power_monitor1.jpg)

## Requirements

- python3
- matplotlib
- smbus
- numpy

### Optional python packges

- paho.mqtt.client for MQTT support
- pigpio for GPIO backlight support
- commentjson for reading configuration files with comments

## Launching power monitor

Start the power monitor with `python3 ./power_monitor.py`

## Creating a symlink in /usr/bin

Make sure the first line in `power_monitor.py` points to the correct python interpreter

```
chmod 755 power_monitor.py
ln -s "$(pwd)/power_monitor.py" /usr/bin/power_monitor
```

### Running with GUI

Set the DISPLAY environment variable before starting the monitor or pass the display with `--display=:0`

#### GUI configuration and live preview

The configuration is stored in `gui-<channels>-<geometry>-auto.json`. To modify it, remove `-auto` from the filename.
To reload the configuration while running, press F8.

### Running headless

Pass the argument `--headless` to disable the GUI
### Command line options

```
# power_monitor -h
usage: power_monitor [-h] [-C CONFIG_DIR] [--display DISPLAY] [--headless]
                     [--fullscreen] [--verbose] [--check]

Power Monitor

optional arguments:
  -h, --help            show this help message and exit
  -C CONFIG_DIR, --config-dir CONFIG_DIR
                        location of config.json and energy.json
  --display DISPLAY     override DISPLAY variable
  --headless            start without GUI
  --fullscreen          start in fullscreen mode
  --verbose             enable debug output
  --check               check and display configurastion
```

## Keyboard shortcuts

| Key | Action |
| - | - |
| Escape | Leave fullscreen |
| F3 | Change main plot, cycle through Current, Power and aggregated Power
| F4 | Toggle Ah/Wh |
| F8 | Reload GUI configuration |
| F9 | Reload configuration |
| F11 | Toggle full screen |
