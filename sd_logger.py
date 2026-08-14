# Note: This file was developed with the assistance of AI code generation tools.

"""SD card CSV logging helper for the particulate matter station."""

import machine
import os
import time

try:
    import _thread
except ImportError:
    _thread = None

from spi_sdcard import SPISDCard


class SDCardLogger:
    def __init__(
        self,
        *,
        sck_pin,
        miso_pin,
        mosi_pin,
        cs_pin,
        header,
        mount_path="/sd",
        filename_prefix="telemetry",
        spi_slot=2,
        frequency=100000,
        queue_size=15,
        retry_interval_ms=30000,
    ):
        self.enabled = False
        self.mounted = False
        self.file_path = None
        self.mount_path = mount_path
        self.header = header
        self.filename_prefix = filename_prefix
        self.spi_slot = spi_slot
        self.frequency = frequency
        self.sck_pin = sck_pin
        self.miso_pin = miso_pin
        self.mosi_pin = mosi_pin
        self.cs_pin = cs_pin
        self.queue_size = queue_size
        self.retry_interval_ms = retry_interval_ms
        self._pending_rows = []
        self._remount_requested = True
        self._worker_started = False

        if _thread is None:
            print("SD logging disabled: this firmware does not provide _thread")
            return

        self._queue_lock = _thread.allocate_lock()
        try:
            _thread.start_new_thread(self._worker, ())
            self._worker_started = True
            print("SD logger starting in background")
        except Exception as error:
            print("SD logging disabled: could not start background worker: {}".format(error))

    def request_remount(self):
        """Ask the background worker to retry without blocking the main loop."""
        if not self._worker_started:
            return False
        self._remount_requested = True
        return True

    def remount(self):
        """Compatibility wrapper: remount requests are always asynchronous."""
        return self.request_remount()

    def _mount_and_open(self):
        self.enabled = False
        self.mounted = False
        self.file_path = None
        sd_card = None
        last_error = None

        for attempt in range(3):
            try:
                spi = machine.SPI(
                    self.spi_slot,
                    baudrate=self.frequency,
                    polarity=0,
                    phase=0,
                    sck=machine.Pin(self.sck_pin),
                    miso=machine.Pin(self.miso_pin),
                    mosi=machine.Pin(self.mosi_pin),
                )
                cs = machine.Pin(self.cs_pin, machine.Pin.OUT, value=1)
                sd_card = SPISDCard(spi, cs, baudrate=self.frequency)
                self._mount(sd_card)
                self.file_path = self._next_file_path(self.filename_prefix)
                self._append_row(self.header)
                self.mounted = True
                self.enabled = True
                print("SD card logging to {}".format(self.file_path))
                return True
            except Exception as error:
                last_error = error
                if sd_card is not None and hasattr(sd_card, "deinit"):
                    try:
                        sd_card.deinit()
                    except Exception:
                        pass
                sd_card = None
                time.sleep_ms(750 * (attempt + 1))

        print("SD card logging unavailable: {}".format(last_error))
        return False

    def _worker(self):
        """Own all automatic SD access so a bad card cannot stop main.py."""
        next_retry_at = time.ticks_ms()

        while True:
            now = time.ticks_ms()
            retry_due = time.ticks_diff(now, next_retry_at) >= 0

            if not self.enabled and (self._remount_requested or retry_due):
                self._remount_requested = False
                if self._mount_and_open():
                    next_retry_at = time.ticks_add(time.ticks_ms(), self.retry_interval_ms)
                else:
                    next_retry_at = time.ticks_add(time.ticks_ms(), self.retry_interval_ms)

            row = self._take_pending_row() if self.enabled else None
            if row is not None:
                try:
                    self._append_row(row)
                except Exception as error:
                    self.enabled = False
                    self.mounted = False
                    print("SD card logging stopped: {}".format(error))
                    next_retry_at = time.ticks_add(time.ticks_ms(), self.retry_interval_ms)

            time.sleep_ms(100)

    def _mount(self, sd_card):
        try:
            os.umount(self.mount_path)
        except OSError:
            pass

        try:
            os.mount(sd_card, self.mount_path)
        except OSError:
            raise

    def _next_file_path(self, filename_prefix):
        existing_files = set(os.listdir(self.mount_path))
        for index in range(1000):
            filename = "{}_{:03d}.csv".format(filename_prefix, index)
            if filename not in existing_files:
                return "{}/{}".format(self.mount_path, filename)

        return "{}/{}_overflow.csv".format(self.mount_path, filename_prefix)

    def _append_row(self, row):
        with open(self.file_path, "a") as log_file:
            log_file.write(",".join(self._csv_cell(value) for value in row))
            log_file.write("\n")

    def log(self, uptime_ms, row):
        if not self._worker_started:
            return

        queued_row = [uptime_ms] + list(row)
        with self._queue_lock:
            if len(self._pending_rows) >= self.queue_size:
                self._pending_rows.pop(0)
            self._pending_rows.append(queued_row)

    def _take_pending_row(self):
        with self._queue_lock:
            if not self._pending_rows:
                return None
            return self._pending_rows.pop(0)

    def _csv_cell(self, value):
        text = str(value)
        if "," not in text and '"' not in text and "\n" not in text and "\r" not in text:
            return text
        return '"{}"'.format(text.replace('"', '""'))
