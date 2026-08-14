"""Cold-boot setup for the ESP32 particulate matter monitor."""

import machine
import network
import time
import webrepl


AP_SSID = "PM Monitor"
AP_PASSWORD = "humidity_conditioning"
HEATER_PIN = 25
AP_START_ATTEMPTS = 3
AP_START_TIMEOUT_MS = 5000


# Keep the heater off from the first moment Python starts. On a cold power-up,
# this runs several seconds before main.py would otherwise configure the pin.
machine.Pin(HEATER_PIN, machine.Pin.OUT, value=0)


def start_access_point():
    """Start the local access point, retrying cold-start failures."""
    wlan_sta = network.WLAN(network.STA_IF)
    wlan_sta.active(False)

    wlan_ap = network.WLAN(network.AP_IF)

    for attempt in range(1, AP_START_ATTEMPTS + 1):
        try:
            # Configure while inactive so a cold boot never starts with the
            # firmware's default SSID and then tries to rename a live AP.
            wlan_ap.active(False)
            time.sleep_ms(500)
            wlan_ap.config(essid=AP_SSID, password=AP_PASSWORD)
            wlan_ap.active(True)

            deadline = time.ticks_add(time.ticks_ms(), AP_START_TIMEOUT_MS)
            while time.ticks_diff(deadline, time.ticks_ms()) > 0:
                if wlan_ap.active():
                    ip_address = wlan_ap.ifconfig()[0]
                    if ip_address and ip_address != "0.0.0.0":
                        print("Network '{}' is broadcasting".format(AP_SSID))
                        print("Board IP Address:", ip_address)
                        return wlan_ap
                time.sleep_ms(100)

            print("Wi-Fi start attempt {} timed out".format(attempt))
        except Exception as error:
            print("Wi-Fi start attempt {} failed: {}".format(attempt, error))

        time.sleep_ms(1000)

    return None


print("Reset cause:", machine.reset_cause())
print("Initializing local Wi-Fi network...")

# Give the 5 V rail and attached peripherals a moment to settle after power-on.
time.sleep_ms(2000)
wlan_ap = start_access_point()

if wlan_ap is not None:
    try:
        webrepl.start()
        print("WebREPL started")
    except Exception as error:
        print("WebREPL unavailable:", repr(error))
else:
    print("Wi-Fi unavailable after {} attempts".format(AP_START_ATTEMPTS))

print("Boot complete; MicroPython will now start main.py")

# Do not import main here. MicroPython automatically executes main.py after
# boot.py returns, which keeps boot and application failures distinguishable.
