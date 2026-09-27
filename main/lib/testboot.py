# Copyright © 2026 Roger B. Leuthner. All rights reserved.  This software is provided for informational and educational purposes. Use of this software does not imply endorsement by the author of any particular use or application. The author assumes no responsibility or liability for any damages or consequences arising from its use.

import time
import network
import config

wlan = network.WLAN(network.WLAN.IF_STA)
wlan.active(True)

wlan.config(
    reconnects=3,
    hostname=config.DEVICE_NAME,
)

wlan.connect(
    config.WIFI_SSID,
    config.WIFI_PASSWORD,
)

start = time.ticks_ms()

while not wlan.isconnected():
    if time.ticks_diff(time.ticks_ms(), start) > 15000:
        print("TIMEOUT")
        print("status:", wlan.status())
        print("ifconfig:", wlan.ifconfig())
        raise RuntimeError("Wi-Fi connection failed")

    time.sleep_ms(250)

print("DHCP CONNECTED")
print("status:", wlan.status())
print("ifconfig:", wlan.ifconfig())

print("Applying static configuration...")

wlan.ifconfig((
    "192.168.1.45",
    "255.255.255.0",
    "192.168.1.1",
    "192.168.1.1",
))

print("AFTER STATIC")
print("status:", wlan.status())
print("ifconfig:", wlan.ifconfig())

while True:
    time.sleep(10)
