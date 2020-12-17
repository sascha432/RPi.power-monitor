#
# Author: sascha_lammers@gmx.de
#

# per channel calibration
class Calibration(object):

    RAW_VSHUNT_TO_MILLIVOLT = 0.005       # Shunt Voltage to mV
    RAW_VBUS_TO_VOLT = 0.001        # Bus Voltage to V

    def __init__(self, shunt=0.1, raw_offset=0, vshunt_mul=1.0, vbus_mul=1.0, disabled=False):
        if not disabled:
            self.setCalibration(shunt, raw_offset, vshunt_mul, vbus_mul)
        self._disabled = disabled

    def set_calibration(self, shunt=None, raw_offset=None, vshunt_mul=None, vbus_mul=None, disabled=None):

        if disabled!=None:
            self._disabled = disabled
        if raw_offset!=None:
            self.raw_offset = raw_offset
        if vshunt_mul!=None:
            self.vshunt_multiplier = vshunt_mul
        if vbus_mul!=None:
            self.vbus_multiplier = vbus_mul * Calibration.RAW_VBUS_TO_VOLT

        shunt = shunt==None and self.shunt['shunt'] or shunt
        self.shunt = {
            'A': (Calibration.RAW_VSHUNT_TO_MILLIVOLT / (shunt / self.vshunt_multiplier)),
            'mA': (Calibration.RAW_VSHUNT_TO_MILLIVOLT / (shunt / (self.vshunt_multiplier * 1000.0))),
            'shunt': shunt
        }

    # unit = 'A' or 'mA', multily with shunt voltage in mV
    def get_current_from_shunt(self, raw_value, unit='A'):
        if self._disabled:
            raise ZeroDivisionError('calibration disabled')
        # dividing the shunt equals multiplying the shunt voltage or dividing the current
        # V = I * (R / Cvbus) == R = (Cvbus * V) / I
        return self.shunt[unit] * (raw_value + self.raw_offset)

    def get_vbus_voltage(self, raw_value):
        if self._disabled:
            raise ZeroDivisionError('calibration disabled')
        return raw_value * self.vbus_multiplier


