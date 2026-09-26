# Mi-Hole

**A lightweight DNS filtering and monitoring appliance built on the ESP32-S3 and MicroPython.**

Mi-Hole is a small, self-contained DNS appliance inspired by the general concept behind [Pi-hole](https://pi-hole.net/), but designed specifically around the constraints and capabilities of an **ESP32-S3 running MicroPython**.

It combines DNS filtering, live statistics, system telemetry, and a browser-based monitoring dashboard into a compact network appliance.

> **Note:** Mi-Hole is an independent project and is not affiliated with, endorsed by, or otherwise associated with Pi-hole.

---

## What is Mi-Hole?

Mi-Hole turns an ESP32-S3 into a network DNS appliance.

Once connected to Wi-Fi, the device runs a DNS server that can filter DNS requests while simultaneously exposing a lightweight HTTP/JSON monitoring API. A React/TypeScript dashboard consumes that API and provides a live view of DNS activity and the underlying ESP32-S3.

The result is a small network appliance that can answer questions such as:

- How many DNS queries have been received?
- How many were blocked?
- Which domains are being blocked most frequently?
- Which clients are generating DNS traffic?
- What is the current upstream DNS latency?
- How busy is the MicroPython event loop?
- How much heap and flash storage remain?
- What is the ESP32-S3 temperature?
- What is the Wi-Fi signal strength?
- What DNS configuration is currently active?
- What has the DNS server been doing recently?

---

## Screenshots

> Add your actual screenshots to the repository and update the paths below.

### Dashboard

![Mi-Hole dashboard](docs/images/dashboard.png)

### DNS Activity

![Mi-Hole DNS activity](docs/images/activity.png)

### System Monitoring

![Mi-Hole system monitoring](docs/images/system.png)

---

## See It in Action

### YouTube Shorts

📺 **Mi-Hole in action**

[▶ Watch on YouTube](YOUR_YOUTUBE_SHORT_URL_1)

📺 **ESP32-S3 DNS monitoring**

[▶ Watch on YouTube](YOUR_YOUTUBE_SHORT_URL_2)

> Replace the placeholder URLs above with the actual YouTube Shorts URLs.

---

## Architecture

Mi-Hole is composed of three major pieces:

````text
                         ┌─────────────────────────┐
                         │       Web Browser       │
                         │                         │
                         │   React / TypeScript    │
                         └────────────┬────────────┘
                                      │
                              HTTP / JSON API
                                      │
                                      ▼
┌──────────────────────────────────────────────────────────────┐
│                         ESP32-S3                             │
│                                                              │
│  ┌──────────────────┐        ┌───────────────────────────┐  │
│  │    DNS Server    │        │        DNSAPI             │  │
│  │                  │        │                           │  │
│  │ DNS filtering    │        │ /api/health               │  │
│  │ DNS forwarding   │        │ /api/stats                │  │
│  │ Query tracking   │◄──────►│ /api/activity             │  │
│  │ Client tracking  │        │ /api/domains              │  │
│  └────────┬─────────┘        │ /api/clients              │  │
│           │                  │ /api/config               │  │
│           ▼                  │ /api/system               │  │
│  ┌──────────────────┐        │ /api/sbc                  │  │
│  │ Statistics / DB  │        │ /api/throughput           │  │
│  └──────────────────┘        │ /api/stats/reset          │  │
│                              └───────────────────────────┘  │
│                                                              │
│                    MicroPython + uasyncio                    │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
                         Network / Wi-Fi
