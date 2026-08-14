# Note: This file was developed with the assistance of AI code generation tools.

from adafruit_sps30.i2c import SPS30_I2C


class ADC16Adapter:
    """Give ESP32 ADC.read() the read_u16() API used by thermistor.py."""

    def __init__(self, adc):
        self.adc = adc

    def read_u16(self):
        if hasattr(self.adc, "read_u16"):
            return self.adc.read_u16()
        return int(self.adc.read() * 65535 / 4095)


class CircuitPythonI2CAdapter:
    """Give machine.I2C the small CircuitPython API expected by BusDevice."""

    def __init__(self, i2c):
        self.i2c = i2c

    def try_lock(self):
        return True

    def unlock(self):
        pass

    def writeto(self, address, buffer, *, start=0, end=None):
        if end is None:
            end = len(buffer)
        self.i2c.writeto(address, buffer[start:end])

    def readfrom_into(self, address, buffer, *, start=0, end=None):
        if end is None:
            end = len(buffer)

        if start == 0 and end == len(buffer):
            self.i2c.readfrom_into(address, buffer)
            return

        read_buffer = bytearray(end - start)
        self.i2c.readfrom_into(address, read_buffer)
        buffer[start:end] = read_buffer

    def writeto_then_readfrom(
        self,
        address,
        out_buffer,
        in_buffer,
        *,
        out_start=0,
        out_end=None,
        in_start=0,
        in_end=None
    ):
        if out_end is None:
            out_end = len(out_buffer)
        if in_end is None:
            in_end = len(in_buffer)

        self.writeto(address, out_buffer, start=out_start, end=out_end)
        self.readfrom_into(address, in_buffer, start=in_start, end=in_end)


class LenientSPS30_I2C(SPS30_I2C):
    """Skip the nonessential firmware-version read if its CRC check fails."""

    def read_firmware_version(self):
        try:
            return super().read_firmware_version()
        except Exception as error:
            print("SPS30 firmware version unavailable: {}".format(error))
            return None
