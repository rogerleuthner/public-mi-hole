# Copyright © 2026 Roger B. Leuthner. All rights reserved.  This software is provided for informational and educational purposes. Use of this software does not imply endorsement by the author of any particular use or application. The author assumes no responsibility or liability for any damages or consequences arising from its use.



class StaticIP:
    def __init__(
        self,
        ip: str,
        netmask: str,
        gateway: str,
        dns: str,
    ) -> None:
        self.ip = ip
        self.netmask = netmask
        self.gateway = gateway
        self.dns = dns

DEVICE_NAME = "MI-HOLE"

WIFI_SSID = "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
WIFI_PASSWORD = "XXXXXXXXXXXXXXXXXXXXXXXXXXXX"

STATIC_IP: StaticIP | None = None

STATIC_IP = StaticIP(
    ip="192.168.1.45",
    netmask="255.255.255.0",
    gateway="192.168.1.1",
    dns="192.168.1.1",
)
assert STATIC_IP is not None

DNS_PORT = 53

DATABASE = "dns_database/dns.db"
DATABASE_CACHE_SIZE = 1024