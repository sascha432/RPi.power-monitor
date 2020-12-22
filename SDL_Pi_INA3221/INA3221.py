# based on
# SDL_Pi_INA3221.py Python Driver Code
# SwitchDoc Labs March 4, 2015
# V 1.2


#encoding: utf-8

from .Calibration import Calibration
from datetime import datetime
from enum import Enum
import sys
try:
    import smbus
except:
    if 'win' in sys.platform:
        # dummy class
        class smbus:
            class SMBus:
                def __init__(self, twi):
                    pass
                def write_word_data(self, addr, register, switchdata):
                    pass
                def read_word_data(self, addr, register):
                    return 0

# constants

#/*=========================================================================
#    I2C ADDRESS/BITS
#    -----------------------------------------------------------------------*/
INA3221_ADDRESS =                         (0x40)    # 1000000 (A0+A1=GND)
INA3221_READ    =                         (0x01)
#/*=========================================================================*/

#/*=========================================================================
#    CONFIG REGISTER (R/W)
#    -----------------------------------------------------------------------*/
INA3221_REG_CONFIG            =          (0x00)
#    /*---------------------------------------------------------------------*/

# 16 bit configuration register
class INA3211_CONFIG:

    # Bit 15
    RESET = 1 << 15

    # Bit 14
    ENABLE_CHANNEL1 = 1 << 14
    # Bit 13
    ENABLE_CHANNEL2 = 1 << 13
    # Bit 12
    ENABLE_CHANNEL3 = 1 << 12

    ENABLE_ALL_CHANNELS = ENABLE_CHANNEL1 | ENABLE_CHANNEL2 | ENABLE_CHANNEL3

    CHANNEL_MASK = ~(0b111 << 12)

    # Bit 11 - 9
    # Averaging mode. These bits set the number of samples that are
    # collected and averaged together.
    # 000 = 1 (default)
    # 001 = 4
    # 010 = 16
    # 011 = 64
    # 100 = 128
    # 101 = 256
    # 110 = 512
    # 111 = 1024

    class AVERAGING_MODE(Enum):
        x1 = 0b000 << 9
        x4 = 0b001 << 9
        x16 = 0b010 << 9
        x64 = 0b011 << 9
        x128 = 0b100 << 9
        x256 = 0b101 << 9
        x512 = 0b110 << 9
        x1024 = 0b111 << 9
        DEFAULT = 0b101 << 9

    AVG = AVERAGING_MODE.x16._value_
    AVG_MASK = ~(0b111 << 9)

    # Bit 8-6

    # Bus-voltage conversion time. These bits set the conversion time
    # for the bus-voltage measurement.
    # 000 = 140 μs
    # 001 = 204 μs
    # 010 = 332 μs
    # 011 = 588 μs
    # 100 = 1.1 ms (default)
    # 101 = 2.116 ms
    # 110 = 4.156 ms
    # 111 = 8.244 ms

    class VBUS_CONVERSION_TIME(Enum):
        time_140_us = 0b000 << 6
        time_204_us = 0b001 << 6
        time_332_us = 0b010 << 6
        time_588_us = 0b011 << 6
        time_1100_us = 0b100 << 6
        time_2116_us = 0b101 << 6
        time_4156_us = 0b110 << 6
        time_8244_us = 0b111 << 6
        DEFAULT = 0b100 << 6

    VBUS_CT = VBUS_CONVERSION_TIME.time_588_us._value_
    VBUS_CT_MASK = ~(0b111 << 6)

    # Bit 5-3

    class VSHUNT_CONVERSION_TIME(Enum):
        time_140_us = 0b000 << 3
        time_204_us = 0b001 << 3
        time_332_us = 0b010 << 3
        time_588_us = 0b011 << 3
        time_1100_us = 0b100 << 3
        time_2116_us = 0b101 << 3
        time_4156_us = 0b110 << 3
        time_8244_us = 0b111 << 3
        DEFAULT = 0b100 << 3

    VSH_CT = VSHUNT_CONVERSION_TIME.DEFAULT._value_
    VSH_CT_MASK = ~(0b111 << 3)

    # Bit 2-0
    # Operating mode. These bits select continuous, single-shot
    # (triggered), or power-down mode of operation. These bits default
    # to continuous shunt and bus mode.
    # 000 = Power-down
    # 001 = Shunt voltage, single-shot (triggered)
    # 010 = Bus voltage, single-shot (triggered)
    # 011 = Shunt and bus, single-shot (triggered)
    # 100 = Power-down
    # 101 = Shunt voltage, continuous
    # 110 = Bus voltage, continuous
    # 111 = Shunt and bus, continuous (default)

    MODE_POWER_DOWN = 0b000
    MODE = 0b111
    MODE_MASK = ~0b111

#/*=========================================================================*/

#/*=========================================================================
#    SHUNT VOLTAGE REGISTER (R)
#    -----------------------------------------------------------------------*/
INA3221_REG_SHUNTVOLTAGE_1   =             (0x01)
#/*=========================================================================*/

#/*=========================================================================
#    BUS VOLTAGE REGISTER (R)
#    -----------------------------------------------------------------------*/
INA3221_REG_BUSVOLTAGE_1     =             (0x02)
#/*=========================================================================*/

SHUNT_RESISTOR_VALUE         = (0.1)   # default shunt resistor value of 0.1 Ohm



class INA3221Base():

    ###########################
    # INA3221 Code
    ###########################
    def __init__(self, twi=1, addr=INA3221_ADDRESS, channels=INA3211_CONFIG.ENABLE_ALL_CHANNELS, avg=INA3211_CONFIG.AVERAGING_MODE.DEFAULT, vbus_ct=INA3211_CONFIG.VBUS_CONVERSION_TIME, vshunt_ct=INA3211_CONFIG.VSHUNT_CONVERSION_TIME.DEFAULT, shunt=SHUNT_RESISTOR_VALUE):
        self._bus = smbus.SMBus(twi)
        self._addr = addr
        self._shunt = shunt
        self.settings(channels, avg, vbus_ct, vshunt_ct)

        # for i in [10000,100,20,10,5,2,0.5,0.1,0.5,0.01,0.001]:
        #     g=self.get_interval_params(1/i)
        #     print(i,g,1/i,1/g[3])
        # sys.exit(0)

    def settings(self, channels, avg, vbus_ct, vshunt_ct):
        self._config = channels | vbus_ct._value_ | vshunt_ct._value_ | INA3211_CONFIG.MODE | avg._value_
        self._calibration = {}
        self._write_register_little_endian(INA3221_REG_CONFIG, self._config)
        self._channel_read_time = INA3221.get_interval(avg, vbus_ct, vshunt_ct)
        # (int(str(avg).split('.')[-1][1:]) * (int(str(vbus_ct).split('.')[-1].split('_')[1]) + int(str(vshunt_ct).split('.')[-1].split('_')[1]))) / 1000000.0
        # self._channel_read_time *= 0.95

    def get_interval(avg, vbus_ct, vshunt_ct):
        return ((int(str(avg).split('.')[-1][1:]) * (int(str(vbus_ct).split('.')[-1].split('_')[1]) + int(str(vshunt_ct).split('.')[-1].split('_')[1]))) / 1000000.0) * 0.95

    # get parameters for given interval
    # from  0.000266s (0.266ms) 3760/sec
    # to    16.04s 3.734/min
    #
    # mode, vbus_ct, vshunt_ct, interval, all_combinations_ordered = INA3221.get_interval_params(time)
    #
    # time          time is seconds
    # lowest_ct     True to get the lowest value for vbus/vshunt
    def get_interval_params(time, lowest_ct=False):

        items = []

        from_list = list(INA3211_CONFIG.VBUS_CONVERSION_TIME)
        if lowest_ct:
            from_list.reverse()

        for mode in INA3211_CONFIG.AVERAGING_MODE:
            last = None
            for voltage in from_list:
                items.append((mode, voltage, INA3211_CONFIG.VSHUNT_CONVERSION_TIME(voltage._value_ >> 3), INA3221.get_interval(mode, voltage, voltage)))

        items = sorted(items, key=lambda item: item[3])
        result = items[0]
        for item in items:
            if time>=item[3]:
                result = item

        return (*result, items)

    def _write(self, register, data):
        #print "addr =0x%x register = 0x%x data = 0x%x " % (self._addr, register, data)
        self._bus.write_byte_data(self._addr, register, data)


    def _read(self, data):

        returndata = self._bus.read_byte_data(self._addr, data)
        #print "addr = 0x%x data = 0x%x %i returndata = 0x%x " % (self._addr, data, data, returndata)
        return returndata


    def _read_register_little_endian(self, register):

        result = self._bus.read_word_data(self._addr,register) & 0xFFFF
        lowbyte = (result & 0xFF00)>>8
        highbyte = (result & 0x00FF) << 8
        switchresult = lowbyte + highbyte
        #print "Read 16 bit Word addr =0x%x register = 0x%x switchresult = 0x%x " % (self._addr, register, switchresult)
        return switchresult


    def _write_register_little_endian(self, register, data):

        data = data & 0xFFFF
        # reverse configure byte for little endian
        lowbyte = data>>8
        highbyte = (data & 0x00FF)<<8
        switchdata = lowbyte + highbyte
        self._bus.write_word_data(self._addr, register, switchdata)
        #print "Write  16 bit Word addr =0x%x register = 0x%x data = 0x%x " % (self._addr, register, data)

    def _validate(self, channel):
        if isinstance(channel, int) and channel>=0 and channel<3:
            return True
        raise TypeError('invalid channel: %s: %s' % (channel, type(channel)))


    def _getBusVoltage_raw(self, channel):
        self._validate(channel)
	#Gets the raw bus voltage (16-bit signed integer, so +-32767)

        value = self._read_register_little_endian(INA3221_REG_BUSVOLTAGE_1 + channel * 2)
        if value > 32767:
            value -= 65536
        return value

    def _getShuntVoltage_raw(self, channel):
        self._validate(channel)
	#Gets the raw shunt voltage (16-bit signed integer, so +-32767)

        value = self._read_register_little_endian(INA3221_REG_SHUNTVOLTAGE_1 + channel * 2)
        if value > 32767:
            value -= 65536
        return value

    # public functions

    def setCalibration(self, channel, obj):
        self._validate(channel)
        self._calibration[channel] = obj

    def setChannel(self, channel, enable=True):
        self._validate(channel)
        if channel==0:
            bit = INA3211Config.ENABLE_CHANNEL1
        elif channel==1:
            bit = INA3211Config.ENABLE_CHANNEL2
        elif channel==2:
            bit = INA3211Config.ENABLE_CHANNEL3
        if enable:
            self._config |= bit
        else:
            self._config &= ~bit
        self._write_register_little_endian(INA3221_REG_CONFIG, self._config)

	# Gets the Bus voltage in volts
    def getBusVoltage_V(self, channel):
        return self._calibration[channel].get_vbus_voltage(self._getBusVoltage_raw(channel))

	# Gets the shunt voltage in mV (so +-168.3mV)
    def getShuntVoltage_mV(self, channel):
        return self._getShuntVoltage_raw(channel) * Calibration.RAW_VSHUNT_TO_MILLIVOLT

    def getShuntVoltage_V(self, channel):
        return self._getShuntVoltage_raw(channel) * Calibration.RAW_VSHUNT_TO_VOLT

    # Gets the current value in mA, taking into account the config settings and current LSB
    def getCurrent_mA(self, channel):
        return self._calibration[channel].get_current_from_shunt(self._getShuntVoltage_raw(channel), 'mA')

    # Gets the current value in A, taking into account the config settings and current LSB
    def getCurrent(self, channel):
        return self._calibration[channel].get_current_from_shunt(self._getShuntVoltage_raw(channel), 'A')


if 'win' in sys.platform:

    import random

    class INA3221(INA3221Base):

        def __init__(self, twi=1, addr=INA3221_ADDRESS, channels=INA3211_CONFIG.ENABLE_ALL_CHANNELS, avg=INA3211_CONFIG.AVERAGING_MODE.DEFAULT, vbus_ct=INA3211_CONFIG.VBUS_CONVERSION_TIME, vshunt_ct=INA3211_CONFIG.VSHUNT_CONVERSION_TIME.DEFAULT, shunt=SHUNT_RESISTOR_VALUE):
            INA3221Base.__init__(self, twi, addr, channels, avg, vbus_ct, vshunt_ct, shunt)

        def _getBusVoltage_raw(self, channel):
            return random.randint(4000, 5000)

        def _getShuntVoltage_raw(self, channel):
            return random.randint(8000, 12000)

else:

    class INA3221(INA3221Base):
        pass
