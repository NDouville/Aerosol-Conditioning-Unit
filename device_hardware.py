# Note: This file was developed with the assistance of AI code generation tools.

"""AI-assisted hardware setup and sensor reading helpers."""

import machine

from adafruit_sht4x import Mode, SHT4x
from compatibility_adapters import (
    ADC16Adapter,
    CircuitPythonI2CAdapter,
    LenientSPS30_I2C,
)
from pms5003 import PMS5003
from thermistor import Thermistor


EMPTY_SPS30_PM = {
    "pm1": 0,
    "pm25": 0,
    "pm4": 0,
    "pm10": 0,
    "count05": 0,
    "count10": 0,
    "count25": 0,
    "count40": 0,
    "count100": 0,
    "typical_particle_size": 0,
}

EMPTY_PLANTOWER_PM = {
    "pm1_standard": 0,
    "pm25_standard": 0,
    "pm10_standard": 0,
    "pm1_env": 0,
    "pm25_env": 0,
    "pm10_env": 0,
    "count03": 0,
    "count05": 0,
    "count10": 0,
    "count25": 0,
    "count50": 0,
    "count100": 0,
}


class DeviceHardware:
    def __init__(
        self,
        *,
        heater_pin,
        ambient_i2c_scl_pin,
        ambient_i2c_sda_pin,
        conditioned_i2c_scl_pin,
        conditioned_i2c_sda_pin,
        sps30_i2c_scl_pin,
        sps30_i2c_sda_pin,
        thermistor_pin,
        plantower_uart_id,
        plantower_tx_pin,
        plantower_rx_pin,
        thermistor_beta,
        thermistor_r0,
        thermistor_t0_k,
        thermistor_resistor,
    ):
        ambient_i2c = machine.I2C(
            0,
            scl=machine.Pin(ambient_i2c_scl_pin),
            sda=machine.Pin(ambient_i2c_sda_pin),
        )
        conditioned_i2c = machine.I2C(
            1,
            scl=machine.Pin(conditioned_i2c_scl_pin),
            sda=machine.Pin(conditioned_i2c_sda_pin),
        )
        sps30_i2c = machine.SoftI2C(
            scl=machine.Pin(sps30_i2c_scl_pin),
            sda=machine.Pin(sps30_i2c_sda_pin),
            freq=50_000,
        )

        self.ambient_sht = self._init_sht41(ambient_i2c, "Ambient")
        self.conditioned_sht = self._init_sht41(conditioned_i2c, "Conditioned")
        self.sps30_sensor = self._init_sps30(sps30_i2c)

        self.heater = machine.Pin(heater_pin, machine.Pin.OUT)
        self.set_heater(False)

        plantower_uart = machine.UART(
            plantower_uart_id,
            9600,
            tx=plantower_tx_pin,
            rx=plantower_rx_pin,
            timeout=1000,
        )
        self.plantower_sensor = PMS5003(
            plantower_uart,
            pin_reset=None,
            pin_enable=None,
            mode="active",
            retries=3,
        )

        thermistor_adc = machine.ADC(machine.Pin(thermistor_pin))
        thermistor_adc.atten(machine.ADC.ATTN_11DB)
        self.thermistor = Thermistor(
            ADC16Adapter(thermistor_adc),
            thermistor_beta,
            thermistor_r0,
            thermistor_t0_k,
            thermistor_resistor,
        )

        self.last_sensirion_pm = dict(EMPTY_SPS30_PM)
        self.last_plantower_pm = dict(EMPTY_PLANTOWER_PM)
        self.last_thermistor_c = 0.0
        self.sps30_error_count = 0

    def set_heater(self, enabled):
        self.heater.value(1 if enabled else 0)

    def heater_is_on(self):
        return self.heater.value() == 1

    def read_all(self):
        ambient_temp, ambient_humidity = self._read_sht41(self.ambient_sht)
        conditioned_temp, conditioned_humidity = self._read_sht41(self.conditioned_sht)

        return {
            "ambient_temp": ambient_temp,
            "ambient_humidity": ambient_humidity,
            "conditioned_temp": conditioned_temp,
            "conditioned_humidity": conditioned_humidity,
            "thermistor_c": self._read_thermistor_c(),
            "sensirion_pm": self._read_sensirion_pm(),
            "plantower_pm": self._read_plantower_pm(),
        }

    def _init_sht41(self, i2c, name):
        try:
            sensor = SHT4x(CircuitPythonI2CAdapter(i2c))
            sensor.mode = Mode.NOHEAT_HIGHPRECISION
            print("{} SHT41 ready".format(name))
            return sensor
        except Exception as error:
            print("{} SHT41 unavailable: {}".format(name, error))
            return None

    def _init_sps30(self, i2c):
        try:
            sensor = LenientSPS30_I2C(CircuitPythonI2CAdapter(i2c), mode_change_delay=2.0)
            print("SPS30 ready")
            return sensor
        except Exception as error:
            print("SPS30 unavailable: {}".format(error))
            return None

    def _read_sht41(self, sensor):
        if sensor is None:
            return "Err", "Err"

        try:
            return sensor.measurements
        except Exception:
            return "Err", "Err"

    def _read_thermistor_c(self):
        try:
            self.last_thermistor_c = Thermistor.toC(self.thermistor.temperature())
        except Exception:
            pass

        return self.last_thermistor_c

    def _read_sensirion_pm(self):
        if self.sps30_sensor is None:
            return self.last_sensirion_pm

        try:
            reading = self.sps30_sensor.read()
            self.sps30_error_count = 0
            self.last_sensirion_pm = {
                "pm1": reading["pm10 standard"],
                "pm25": reading["pm25 standard"],
                "pm4": reading["pm40 standard"],
                "pm10": reading["pm100 standard"],
                "count05": reading["particles 05um"],
                "count10": reading["particles 10um"],
                "count25": reading["particles 25um"],
                "count40": reading["particles 40um"],
                "count100": reading["particles 100um"],
                "typical_particle_size": reading["tps"],
            }
        except Exception as error:
            self.sps30_error_count += 1
            if self.sps30_error_count in (1, 5, 15):
                print("SPS30 read unavailable: {}".format(error))

        return self.last_sensirion_pm

    def _read_plantower_pm(self):
        try:
            if not self.plantower_sensor.data_available():
                return self.last_plantower_pm

            reading = self.plantower_sensor.read()
            self.last_plantower_pm = {
                "pm1_standard": reading.pm_ug_per_m3(1.0),
                "pm25_standard": reading.pm_ug_per_m3(2.5),
                "pm10_standard": reading.pm_ug_per_m3(10),
                "pm1_env": reading.pm_ug_per_m3(1.0, atmospheric_environment=True),
                "pm25_env": reading.pm_ug_per_m3(2.5, atmospheric_environment=True),
                "pm10_env": reading.pm_ug_per_m3(10, atmospheric_environment=True),
                "count03": reading.pm_per_1l_air(0.3),
                "count05": reading.pm_per_1l_air(0.5),
                "count10": reading.pm_per_1l_air(1.0),
                "count25": reading.pm_per_1l_air(2.5),
                "count50": reading.pm_per_1l_air(5),
                "count100": reading.pm_per_1l_air(10),
            }
        except Exception:
            pass

        return self.last_plantower_pm
