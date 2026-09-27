# Copyright © 2026 Roger B. Leuthner. All rights reserved.  This software is provided for informational and educational purposes. Use of this software does not imply endorsement by the author of any particular use or application. The author assumes no responsibility or liability for any damages or consequences arising from its use.

"""Mi-Hole application entry point."""

import gc

import uasyncio
from dns_api import DNSAPI
from dns_server import create_dns_server
from wifi import WiFi


async def run():
    wifi = WiFi()

    if not wifi.connect():
        raise RuntimeError("Wi-Fi connection failed")

    print("Wi-Fi ready:", wifi.ifconfig())

    database, stats, dns_server = create_dns_server()

    print("DNS database loaded:")
    print(database.stats())

    gc.collect()

    api = DNSAPI(
        dns_server,
        stats,
        host="0.0.0.0",
        port=HTTP_PORT,
    )

    await api.start()

    print("Mi-Hole dashboard API ready.")

    gc.collect()

    try:
        await dns_server.serve_forever()

    finally:
        await api.close()
        dns_server.close()
        database.close()


def main():
    try:
        uasyncio.run(run())

    except KeyboardInterrupt:
        print("Shutting down DNS server...")


if __name__ == "__main__":
    main()

