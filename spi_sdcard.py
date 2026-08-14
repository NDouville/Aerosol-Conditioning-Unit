"""SPI-mode microSD block device for MicroPython."""

import time


class SPISDCard:
    CMD_TIMEOUT = 100

    def __init__(self, spi, cs, baudrate=100_000):
        self.spi = spi
        self.cs = cs
        self.cs.value(1)
        self.cdv = 1
        self.baudrate = baudrate

        for _ in range(16):
            self.xfer([0xFF])

        cmd0_response = self.cmd(0, 0, 0x95)
        if cmd0_response != 1:
            raise OSError("no SD card response to CMD0: {}".format(cmd0_response))

        response = self.cmd(8, 0x01AA, 0x87, 4)
        if len(response) == 5 and response[0] == 1:
            if response[3] != 0x01 or response[4] != 0xAA:
                raise OSError("unsupported SD card voltage")
            self.init_card_v2()
        else:
            self.init_card_v1()

        if self.cmd(16, 512, 0x15) != 0:
            raise OSError("could not set SD block size")

        self.sectors = self.sector_count()

    def xfer(self, data):
        outgoing = bytes(data)
        incoming = bytearray(len(outgoing))
        self.spi.write_readinto(outgoing, incoming)
        return incoming

    def read_byte(self):
        return self.xfer([0xFF])[0]

    def read_bytes(self, length):
        return self.xfer([0xFF] * length)

    def init_card_v1(self):
        for _ in range(self.CMD_TIMEOUT):
            self.cmd(55, 0, 0x65)
            if self.cmd(41, 0, 0xE5) == 0:
                self.cdv = 512
                return
            time.sleep_ms(50)
        raise OSError("timeout waiting for v1 SD card")

    def init_card_v2(self):
        last_cmd55 = None
        last_acmd41 = None

        for _ in range(self.CMD_TIMEOUT * 4):
            last_cmd55 = self.cmd(55, 0, 0x65)
            last_acmd41 = self.cmd(41, 0x40000000, 0x77)
            if last_acmd41 == 0:
                response = self.cmd(58, 0, 0xFD, 4)
                self.cdv = 1 if (response[1] & 0x40) else 512
                return
            time.sleep_ms(50)

        raise OSError("timeout waiting for v2 SD card cmd55={} acmd41={}".format(last_cmd55, last_acmd41))

    def cmd(self, command, argument, crc, final=0, release=True):
        self.cs.value(0)
        self.xfer([0xFF])
        self.xfer((
            0x40 | command,
            (argument >> 24) & 0xFF,
            (argument >> 16) & 0xFF,
            (argument >> 8) & 0xFF,
            argument & 0xFF,
            crc,
        ))

        for _ in range(100):
            response = self.read_byte()
            if response != 0xFF:
                break
        else:
            response = 0xFF

        if final:
            response = bytes((response,)) + self.read_bytes(final)

        if release:
            self.cs.value(1)
            self.xfer([0xFF])
        return response

    def readinto(self, buffer):
        self.cs.value(0)
        try:
            token = 0xFF
            for _ in range(5000):
                token = self.read_byte()
                if token == 0xFE:
                    break
            else:
                raise OSError("timeout waiting for SD read token last={}".format(token))

            mv = memoryview(buffer)
            self.spi.write_readinto(bytes([0xFF]) * len(mv), mv)
            self.read_bytes(2)
        finally:
            self.cs.value(1)
            self.xfer([0xFF])

    def readblocks(self, block_num, buffer):
        block_count = len(buffer) // 512
        mv = memoryview(buffer)

        if block_count == 1:
            last_error = None
            for _ in range(3):
                if self.cmd(17, block_num * self.cdv, 0xFF, release=False) != 0:
                    self.cs.value(1)
                    self.xfer([0xFF])
                    last_error = OSError("SD single-block read failed")
                    continue
                try:
                    self.readinto(mv)
                    return 0
                except OSError as error:
                    last_error = error
                    self.cs.value(1)
                    self.xfer([0xFF])
                    time.sleep_ms(10)
            raise last_error

        if self.cmd(18, block_num * self.cdv, 0xFF, release=False) != 0:
            self.cs.value(1)
            self.xfer([0xFF])
            raise OSError("SD multi-block read failed")
        for block_index in range(block_count):
            self.readinto(mv[block_index * 512:(block_index + 1) * 512])
        self.cmd(12, 0, 0xFF)
        return 0

    def write_token(self, token, buffer):
        self.cs.value(0)
        try:
            self.spi.write(bytes((token,)))
            self.spi.write(buffer)
            self.spi.write(b"\xff\xff")
            response = self.read_byte()
            if (response & 0x1F) != 0x05:
                raise OSError("SD rejected written block")

            for _ in range(100000):
                if self.read_byte() == 0xFF:
                    return
            raise OSError("timeout waiting for SD write")
        finally:
            self.cs.value(1)
            self.xfer([0xFF])

    def writeblocks(self, block_num, buffer):
        block_count = len(buffer) // 512
        mv = memoryview(buffer)

        if block_count == 1:
            if self.cmd(24, block_num * self.cdv, 0xFF, release=False) != 0:
                self.cs.value(1)
                self.xfer([0xFF])
                raise OSError("SD single-block write failed")
            self.write_token(0xFE, mv)
            return 0

        if self.cmd(25, block_num * self.cdv, 0xFF, release=False) != 0:
            self.cs.value(1)
            self.xfer([0xFF])
            raise OSError("SD multi-block write failed")
        for block_index in range(block_count):
            self.write_token(0xFC, mv[block_index * 512:(block_index + 1) * 512])
        self.write_token(0xFD, b"")
        return 0

    def sector_count(self):
        if self.cmd(9, 0, 0xAF, release=False) != 0:
            self.cs.value(1)
            self.xfer([0xFF])
            return 0

        csd = bytearray(16)
        self.readinto(csd)

        if csd[0] & 0xC0 == 0x40:
            c_size = ((csd[7] & 0x3F) << 16) | (csd[8] << 8) | csd[9]
            return (c_size + 1) * 1024

        read_bl_len = csd[5] & 0x0F
        c_size = ((csd[6] & 0x03) << 10) | (csd[7] << 2) | ((csd[8] & 0xC0) >> 6)
        c_size_mult = ((csd[9] & 0x03) << 1) | ((csd[10] & 0x80) >> 7)
        block_len = 1 << read_bl_len
        mult = 1 << (c_size_mult + 2)
        block_count = (c_size + 1) * mult
        return block_count * block_len // 512

    def ioctl(self, operation, argument):
        if operation == 4:
            return self.sectors
        if operation == 5:
            return 512
        return 0

    def deinit(self):
        self.cs.value(1)
        self.xfer([0xFF])
