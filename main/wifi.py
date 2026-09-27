# Copyright © 2026 Roger B. Leuthner. All rights reserved.  This software is provided for informational and educational purposes. Use of this software does not imply endorsement by the author of any particular use or application. The author assumes no responsibility or liability for any damages or consequences arising from its use.

import time

import config
import network
from config import DEVICE_NAME, STATIC_IP

assert STATIC_IP is not None

class WiFi:
    def __init__(self):
        self.wlan = network.WLAN(network.WLAN.IF_STA)
        self.wlan.active(True)

    def connect(self, timeout_ms=15000):
        if self.wlan.isconnected():
            print("Wi-Fi: already connected")
            print("Wi-Fi config:", self.wlan.ifconfig())
            return True

        print("Wi-Fi: configuring")

        self.wlan.config(reconnects=3)
        self.wlan.config(hostname=DEVICE_NAME)

        # Set static network configuration BEFORE connecting.
        self.wlan.ifconfig((
            STATIC_IP.ip,
            STATIC_IP.netmask,
            STATIC_IP.gateway,
            STATIC_IP.dns
        ))

        print("Wi-Fi config before connect:", self.wlan.ifconfig())

        print("Wi-Fi: connecting to", config.WIFI_SSID)

        self.wlan.connect(
            config.WIFI_SSID,
            config.WIFI_PASSWORD
        )

        start = time.ticks_ms()

        while not self.wlan.isconnected():
            if time.ticks_diff(time.ticks_ms(), start) >= timeout_ms:
                print("Wi-Fi: connection timeout")
                print("Wi-Fi config:", self.wlan.ifconfig())
                return False

            time.sleep_ms(100)

        print("Wi-Fi: connected")
        print("Wi-Fi config:", self.wlan.ifconfig())

        return True

    def connected(self):
        return self.wlan.isconnected()

    def reconnect(self):
        print("Wi-Fi: reconnecting")

        try:
            self.wlan.disconnect()
        except:
            pass

        time.sleep_ms(250)

        return self.connect()

    def ifconfig(self):
        return self.wlan.ifconfig()
