"""Standalone pure-SPI microSD mount test for the ESP32 logger."""

import machine
import os
import time

from spi_sdcard import SPISDCard


SCK_PIN = 14
MISO_PIN = 32
MOSI_PIN = 23
CS_PIN = 33
SPI_SLOT = 2
FREQUENCIES = (50000, 100000, 400000, 1000000)
MOUNT_PATH = "/spisd"


def make_spi(frequency):
    return machine.SPI(
        SPI_SLOT,
        baudrate=frequency,
        polarity=0,
        phase=0,
        sck=machine.Pin(SCK_PIN),
        miso=machine.Pin(MISO_PIN),
        mosi=machine.Pin(MOSI_PIN),
    )


def make_cs():
    return machine.Pin(CS_PIN, machine.Pin.OUT, value=1)


def xfer(spi, data):
    outgoing = bytes(data)
    incoming = bytearray(len(outgoing))
    spi.write_readinto(outgoing, incoming)
    return incoming


def read_response(spi, tries=100):
    for _ in range(tries):
        response = xfer(spi, [0xFF])[0]
        if response != 0xFF:
            return response
    return 0xFF


def send_cmd(spi, cs, command, argument, crc, tail=0):
    cs.value(0)
    xfer(spi, [0xFF])
    xfer(
        spi,
        [
            0x40 | command,
            (argument >> 24) & 0xFF,
            (argument >> 16) & 0xFF,
            (argument >> 8) & 0xFF,
            argument & 0xFF,
            crc,
        ],
    )
    response = read_response(spi)
    extra = list(xfer(spi, [0xFF] * tail)) if tail else []
    cs.value(1)
    xfer(spi, [0xFF])
    return response, extra


def wake_card(spi, cs):
    cs.value(1)
    time.sleep_ms(50)
    for _ in range(32):
        xfer(spi, [0xFF])
    time.sleep_ms(50)


def probe_frequency(frequency):
    print("")
    print("Probe frequency:", frequency)
    spi = make_spi(frequency)
    cs = make_cs()
    wake_card(spi, cs)

    idle = list(xfer(spi, [0xFF] * 16))
    print("Idle MISO samples:", idle)

    cmd0 = 0xFF
    for attempt in range(1, 11):
        cmd0, _ = send_cmd(spi, cs, 0, 0, 0x95)
        print("CMD0 attempt {}: {}".format(attempt, hex(cmd0)))
        if cmd0 == 0x01:
            break
        time.sleep_ms(100)

    cmd8, cmd8_tail = send_cmd(spi, cs, 8, 0x01AA, 0x87, 4)
    print("CMD8 response:", hex(cmd8), "tail:", [hex(byte) for byte in cmd8_tail])
    return cmd0 == 0x01


def ensure_mount_path():
    try:
        os.mkdir(MOUNT_PATH)
    except OSError:
        pass


def unmount_if_needed():
    try:
        os.umount(MOUNT_PATH)
    except OSError:
        pass


def print_block_info(block):
    print("Block 0 signature: {:02x} {:02x}".format(block[510], block[511]))
    print("Block 0 first 32:", " ".join("{:02x}".format(byte) for byte in block[:32]))


def run_probe():
    print("Pure SPI SD mount test")
    print("Expected wiring: CLK=GPIO{}, D0/SO=GPIO{}, CMD/SI=GPIO{}, D3/CS=GPIO{}".format(
        SCK_PIN, MISO_PIN, MOSI_PIN, CS_PIN
    ))

    card_answered = False
    for frequency in FREQUENCIES:
        if probe_frequency(frequency):
            card_answered = True
            break

    if not card_answered:
        raise OSError("no SD card response to CMD0 at any test frequency")

    time.sleep_ms(250)
    spi = make_spi(100000)
    cs = make_cs()
    ensure_mount_path()
    unmount_if_needed()

    sd_card = SPISDCard(spi, cs, baudrate=100000)
    print("SPI SD driver initialized, sectors:", sd_card.sectors, "cdv:", sd_card.cdv)

    print("Reading block 0...")
    block = bytearray(512)
    sd_card.readblocks(0, block)
    print_block_info(block)

    os.mount(sd_card, MOUNT_PATH)
    print("Mounted at", MOUNT_PATH)

    print("Initial files:", os.listdir(MOUNT_PATH))
    test_path = MOUNT_PATH + "/spi_driver_test.txt"
    with open(test_path, "w") as test_file:
        test_file.write("pure SPI driver OK\n")
    print("Wrote", test_path)

    with open(test_path, "r") as test_file:
        print("Read back:", test_file.read().strip())

    print("Final files:", os.listdir(MOUNT_PATH))
    print("Pure SPI SD mount test passed")


try:
    run_probe()
except Exception as error:
    print("Pure SPI SD mount test failed:", repr(error))
