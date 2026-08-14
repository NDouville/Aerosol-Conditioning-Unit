# Note: This file was developed with the assistance of AI code generation tools.

"""AI-assisted DATA line formatting helper."""


SPS30_FIELDS = (
    "pm1",
    "pm25",
    "pm4",
    "pm10",
    "count05",
    "count10",
    "count25",
    "count40",
    "count100",
    "typical_particle_size",
)

PLANTOWER_FIELDS = (
    "pm1_standard",
    "pm25_standard",
    "pm10_standard",
    "pm1_env",
    "pm25_env",
    "pm10_env",
    "count03",
    "count05",
    "count10",
    "count25",
    "count50",
    "count100",
)

DATA_FIELDS = (
    "Mode",
    "Heater",
    "Ambient_Temp_C",
    "Ambient_Humidity_Pct",
    "Conditioned_Temp_C",
    "Conditioned_Humidity_Pct",
    "Thermistor_C",
    "SPS30_PM1.0_ug_m3",
    "SPS30_PM2.5_ug_m3",
    "SPS30_PM4.0_ug_m3",
    "SPS30_PM10_ug_m3",
    "SPS30_Count0.5_per_cm3",
    "SPS30_Count1.0_per_cm3",
    "SPS30_Count2.5_per_cm3",
    "SPS30_Count4.0_per_cm3",
    "SPS30_Count10_per_cm3",
    "SPS30_Typical_Particle_Size_um",
    "PMS5003_PM1.0_Standard_ug_m3",
    "PMS5003_PM2.5_Standard_ug_m3",
    "PMS5003_PM10_Standard_ug_m3",
    "PMS5003_PM1.0_Atmospheric_ug_m3",
    "PMS5003_PM2.5_Atmospheric_ug_m3",
    "PMS5003_PM10_Atmospheric_ug_m3",
    "PMS5003_Count0.3_per_0.1L",
    "PMS5003_Count0.5_per_0.1L",
    "PMS5003_Count1.0_per_0.1L",
    "PMS5003_Count2.5_per_0.1L",
    "PMS5003_Count5.0_per_0.1L",
    "PMS5003_Count10_per_0.1L",
)


CSV_HEADER = ("Uptime_ms",) + DATA_FIELDS


def build_data_row(mode, heater_status, readings):
    sensirion_pm = readings["sensirion_pm"]
    plantower_pm = readings["plantower_pm"]
    row = [
        mode,
        heater_status,
        readings["ambient_temp"],
        readings["ambient_humidity"],
        readings["conditioned_temp"],
        readings["conditioned_humidity"],
        round(readings["thermistor_c"], 1),
    ]
    row.extend(sensirion_pm[field] for field in SPS30_FIELDS)
    row.extend(plantower_pm[field] for field in PLANTOWER_FIELDS)
    return row


def print_data(mode, heater_status, readings):
    row = build_data_row(mode, heater_status, readings)

    print("DATA:{}".format(",".join(str(value) for value in row)))
    return row
