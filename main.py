import time
import os

"""

The files command_input.py, data_output.py, and device_hardware.py are helper files that must be located in the same directory as main.py.
These files integrate sensor libraries and drivers (adafruit_bus_device, adafruit_sps30, compatibility_adapters.py, pms5003.py, thermistor.py) which
must also be included in the same directory. The file main.py contains only the runtime loop and the physical hardware configuration. 

"""

from command_input import read_command
from data_output import CSV_HEADER, print_data
from device_hardware import DeviceHardware
from sd_logger import SDCardLogger


# Hardware pin configuration. 
HEATER_PIN = 25
AMBIENT_I2C_SCL_PIN = 22
AMBIENT_I2C_SDA_PIN = 21
CONDITIONED_I2C_SCL_PIN = 19
CONDITIONED_I2C_SDA_PIN = 18
SPS30_I2C_SCL_PIN = 27
SPS30_I2C_SDA_PIN = 26
THERMISTOR_PIN = 34
PLANTOWER_UART_ID = 2
PLANTOWER_TX_PIN = 17
PLANTOWER_RX_PIN = 16
SD_SCK_PIN = 14
SD_MISO_PIN = 32
SD_MOSI_PIN = 23
SD_CS_PIN = 33

# Experiment settings.
CONDITIONED_HUMIDITY_TRIGGER = 40
THERMISTOR_CUTOFF_C = 60.0
HEATER_ON_MS = 15000
HEATER_COOLDOWN_MS = 30000
READ_INTERVAL_MS = 2000

# Thermistor settings and parameters. 
THERMISTOR_BETA = 3950
THERMISTOR_R0 = 10000.0
THERMISTOR_T0_K = 293.15 # calibrated at 20 C
THERMISTOR_RESISTOR = 10000.0

# Heater modes. 
MODE_AUTOMATIC = "AUTOMATIC"
MODE_MANUAL = "MANUAL"

# Store all of the hardware configurations in an instance of the DeviceHardware class. 
device = DeviceHardware(heater_pin=HEATER_PIN, ambient_i2c_scl_pin=AMBIENT_I2C_SCL_PIN, ambient_i2c_sda_pin=AMBIENT_I2C_SDA_PIN, 
    conditioned_i2c_scl_pin=CONDITIONED_I2C_SCL_PIN, conditioned_i2c_sda_pin=CONDITIONED_I2C_SDA_PIN, sps30_i2c_scl_pin=SPS30_I2C_SCL_PIN,
    sps30_i2c_sda_pin=SPS30_I2C_SDA_PIN, thermistor_pin=THERMISTOR_PIN, plantower_uart_id=PLANTOWER_UART_ID, plantower_tx_pin=PLANTOWER_TX_PIN,
    plantower_rx_pin=PLANTOWER_RX_PIN, thermistor_beta=THERMISTOR_BETA, thermistor_r0=THERMISTOR_R0, thermistor_t0_k=THERMISTOR_T0_K,
    thermistor_resistor=THERMISTOR_RESISTOR)

sd_logger = SDCardLogger(sck_pin=SD_SCK_PIN, miso_pin=SD_MISO_PIN, mosi_pin=SD_MOSI_PIN, cs_pin=SD_CS_PIN, header=CSV_HEADER)

# Global variables. 
mode = MODE_MANUAL
heater_started_at = 0
cooldown_started_at = 0
cooldown_active = False
last_read_at = 0

# Turns the heater on and off and handles timing. 
def set_heater(enabled, now=None):
    global heater_started_at

    if enabled and not device.heater_is_on():
        if now is None:
            heater_started_at = time.ticks_ms()
        else:
            heater_started_at = now

    device.set_heater(enabled)

# Handles manual and automatic modes and SD card commands.
def handle_command(command, now):
    global mode, cooldown_active

    command_key = command.lower()

    if command_key == "auto":
        mode = MODE_AUTOMATIC
    elif command_key == "manual":
        mode = MODE_MANUAL
        cooldown_active = False
        set_heater(False)
    elif command_key == "high" and mode == MODE_MANUAL:
        set_heater(True, now)
    elif command_key == "low" and mode == MODE_MANUAL:
        set_heater(False)
    elif command_key == "sdlist":
        print_sd_files()
    elif command_key == "sdremount":
        if sd_logger.request_remount():
            print("SD_REMOUNT:REQUESTED")
        else:
            print("SD_REMOUNT:FAILED")
    elif command_key.startswith("sdread "):
        print_sd_file(command[7:].strip())


def print_sd_files():
    if not sd_logger.mounted:
        sd_logger.request_remount()
        print("SD_FILES_ERROR:SD card is not mounted; background retry requested")
        return

    try:
        print("SD_FILES_BEGIN")
        print_sd_tree(sd_logger.mount_path, "")
        print("SD_FILES_END")
    except Exception as error:
        print("SD_FILES_ERROR:{}".format(error))


def is_directory(path):
    try:
        return (os.stat(path)[0] & 0x4000) != 0
    except OSError:
        return False


def print_sd_tree(base_path, relative_path, depth=0):
    if depth > 4:
        return

    path = base_path if not relative_path else "{}/{}".format(base_path, relative_path)
    filenames = os.listdir(path)
    filenames.sort()

    for filename in filenames:
        if filename.startswith("."):
            continue

        child_relative = filename if not relative_path else "{}/{}".format(relative_path, filename)
        child_path = "{}/{}".format(base_path, child_relative)
        directory = is_directory(child_path)
        size = 0 if directory else os.stat(child_path)[6]
        kind = "dir" if directory else "file"
        print("SD_FILE_ENTRY:{}|{}|{}".format(kind, child_relative, size))
        if directory:
            print_sd_tree(base_path, child_relative, depth + 1)


def print_sd_file(filename):
    if not sd_logger.mounted:
        sd_logger.request_remount()
        print("SD_FILE_ERROR:SD card is not mounted; background retry requested")
        return

    if not filename or filename.startswith("/") or "\\" in filename or ".." in filename:
        print("SD_FILE_ERROR:Invalid filename")
        return

    try:
        path = "{}/{}".format(sd_logger.mount_path, filename)
        print("SD_FILE_BEGIN:{}".format(filename))
        with open(path, "r") as sd_file:
            for line in sd_file:
                print("SD_FILE_LINE:" + line.rstrip("\r\n"))
        print("SD_FILE_END:{}".format(filename))
    except Exception as error:
        print("SD_FILE_ERROR:{}".format(error))

# Cooldown timing for automatic mode. 
def update_cooldown(now):
    global cooldown_active, cooldown_started_at

    heater_has_run_long_enough = (mode == MODE_AUTOMATIC and device.heater_is_on() and time.ticks_diff(now, heater_started_at) >= HEATER_ON_MS)
    
    if heater_has_run_long_enough:
        set_heater(False)
        cooldown_active = True
        cooldown_started_at = now

    cooldown_has_finished = (cooldown_active and time.ticks_diff(now, cooldown_started_at) >= HEATER_COOLDOWN_MS)
    
    if cooldown_has_finished:
        cooldown_active = False

# Heating conditions for automatic mode, returns a boolean. 
def should_heat(readings):
    if mode == MODE_MANUAL:
        target = device.heater_is_on()
    else:
        target = readings["conditioned_humidity"] != "Err"
        target = target and readings["conditioned_humidity"] > CONDITIONED_HUMIDITY_TRIGGER

    if readings["thermistor_c"] >= THERMISTOR_CUTOFF_C:
        target = False
    if cooldown_active:
        target = False

    return target


def heater_status():
    if cooldown_active:
        return "COOLDOWN"
    if device.heater_is_on():
        return "ON"
    return "OFF"

# Main runtime loop. 
while True:
    now = time.ticks_ms()

    command = read_command()
    if command:
        handle_command(command, now)

    update_cooldown(now)

    ready_to_read = time.ticks_diff(now, last_read_at) >= READ_INTERVAL_MS
    if ready_to_read:
        last_read_at = now

        readings = device.read_all()
        set_heater(should_heat(readings), now)
        data_row = print_data(mode, heater_status(), readings)
        sd_logger.log(now, data_row)

    time.sleep(0.1)
