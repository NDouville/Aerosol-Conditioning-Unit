# -------- Important Copyright Information --------- #

# FROM: GitHub
# AUTHOR: Stewart Russel (https://github.com/scruss)
# URL: https://github.com/scruss/micropython-simple-thermistor/blob/main/simple_thermistor.py
# LICENSE: The following code is used under the MIT License.
# FULL LICENSE TEXT: https://github.com/scruss/micropython-simple-thermistor/blob/main/LICENCE

# Copyright (c) 2024 Stewart Russell - scruss

# -------------------------------------------------- #


import machine
from math import log


class Thermistor:
    def __init__(
        self,
        adc,
        beta: float,
        r0: float,
        t0: float,  # Kelvin
        resistor: float,
    ) -> None:
        # pylint: disable=too-many-arguments
        self.adc = adc
        self.beta = beta
        self.r0 = r0
        self.t0 = t0
        self.resistor = resistor

    def toC(x: float) -> float:
        # K → °C
        return x - 273.15

    def fromC(x: float) -> float:
        # °C → K
        return x + 273.15

    # removed toF, fromF: let's not enable barbarianism ...

    def resistance(self) -> float:
        return self.resistor / (65535 / self.adc.read_u16() - 1)

    def temperature(self) -> float:
        return 1.0 / (
            (1.0 / self.beta) * log(self.resistance() / self.resistor)
            + (1.0 / self.t0)
        )