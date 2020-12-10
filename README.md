# RPI.power-monitor

Power Monitor for the INA3221 sensor.

- 3 Channels (Voltage, Current, Power, Energy Wh/Ah)
- Runs headless as service or with tkinter GUI
- Fullscreen mode
- Backlight detection to reduce CPU load
- MQTT support
- Home assistant auto discovery

![GUI](https://raw.githubusercontent.com/sascha432/RPI.power-monitor/master/images/power_monitor1.jpg)

## Requirements

- python3
- matplotlib
- smbus
- paho.mqtt.client
- pigpio

## Running with GUI

Set the DISPLAY environment variable before starting the monitor
