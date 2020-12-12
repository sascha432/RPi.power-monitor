# SDL_Pi_INA3221.py Python Driver Code
# SwitchDoc Labs March 4, 2015
# V 1.2


#encoding: utf-8

from datetime import datetime

import smbus

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

    AVG = 0
    AVG_MASK = ~(0b111 << 9)

    AVG_x1 = 0b000 << 9
    AVG_x4 = 0b001 << 9
    AVG_x16 = 0b010 << 9
    AVG_x64 = 0b011 << 9
    AVG_x128 = 0b100 << 9
    AVG_x256 = 0b101 << 9
    AVG_x512 = 0b110 << 9
    AVG_x1024 = 0b111 << 9

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

    VBUS_CT = 0b011 << 6
    VBUS_CT_MASK = ~(0b111 << 6)

    # Bit 5-3

    VSH_CT = 0b100 << 3
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



class SDL_Pi_INA3221():

    ###########################
    # INA3221 Code
    ###########################
    def __init__(self, twi=1, addr=INA3221_ADDRESS, channels=INA3211_CONFIG.ENABLE_ALL_CHANNELS, avg=INA3211_CONFIG.AVG_x16, shunt=SHUNT_RESISTOR_VALUE):
        self._bus = smbus.SMBus(twi)
        self._addr = addr
        self._shunt = shunt
        self._config = channels | INA3211_CONFIG.VBUS_CT | INA3211_CONFIG.VSH_CT | INA3211_CONFIG.MODE | avg
        self._offset = [0, 0, 0]
        self._write_register_little_endian(INA3221_REG_CONFIG, self._config)

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
        value += self._offset[channel]
        return value

    # public functions

    def setOffset(self, channel, offset):
        self._validate(channel)
        self._offset[channel] = offset

    def setChannel(self, channel, enable=True):
        self._validate(channel)
        if channel==0:
            bit = INA3211Config.ENABLE_CHANNEL1
        elif channel==1:
            bit = INA3211Config.ENABLE_CHANNEL1
        elif channel==2:
            bit = INA3211Config.ENABLE_CHANNEL1
        if enable:
            self._config |= bit
        else:
            self._config &= ~bit
        self._write_register_little_endian(INA3221_REG_CONFIG, self._config)

    def getBusVoltage_V(self, channel):
	# Gets the Bus voltage in volts

        value = self._getBusVoltage_raw(channel)
        return value * 0.001


    def getShuntVoltage_mV(self, channel):
	# Gets the shunt voltage in mV (so +-168.3mV)

        value = self._getShuntVoltage_raw(channel)
        return value * 0.005

    def getCurrent_mA(self, channel):
    #Gets the current value in mA, taking into account the config settings and current LSB

        valueDec = self.getShuntVoltage_mV(channel) / self._shunt
        return valueDec;


