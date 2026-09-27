<p align="center">
  <img src="media/hero.jpg" alt="Mi-Hole" width="900">
</p>

<h1 align="center">Mi-Hole</h1>

<p align="center">
  ESP32-S3 DNS filtering and monitoring appliance built with MicroPython
</p>

<p align="center">
<!--
  <a href="[![Watch it in action](https://img.youtube.com/vi/D5P4xrF4DOM/hqdefault.jpg)](https://youtu.be/D5P4xrF4DOM)">▶ Watch it in action</a> -->
  <a href="https://youtu.be/D5P4xrF4DOM">▶ Watch it in action</a>
  &nbsp;&nbsp;•&nbsp;&nbsp;
  <a href="YOUR_YOUTUBE_SHORT_URL_2">▶ See the dashboard</a>
</p>

<hr>

# Mi-Hole

**A lightweight DNS filtering and monitoring appliance built on the ESP32-S3 and MicroPython.**

Mi-Hole is a small, self-contained DNS appliance inspired by the general concept behind [Pi-hole](https://pi-hole.net/), but designed for cheap SBC running MicroPython**.

It combines DNS filtering, live statistics, system telemetry, and a browser-based monitoring dashboard into a compact network appliance.

---

## What is Mi-Hole?

Mi-Hole turns an ESP32-S3 into a network DNS appliance.

Once connected to Wi-Fi, the device runs a DNS server that can filter DNS requests while simultaneously exposing a lightweight HTTP/JSON monitoring API. A React/TypeScript dashboard consumes that API and provides a live view of DNS activity and the underlying ESP32-S3.

---

## Screenshots

### Dashboard

![Mi-Hole dashboard](media/dashboard.jpg)

### DNS Activity

![Mi-Hole DNS activity](media/activity.jpg)


---

## See It in Action

### YouTube Shorts [TBD]

📺 **Mi-Hole in action**

[▶ Watch on YouTube](YOUR_YOUTUBE_SHORT_URL_1)

📺 **ESP32-S3 DNS monitoring**

[▶ Watch on YouTube](YOUR_YOUTUBE_SHORT_URL_2)

---

## Architecture

Mi-Hole is composed of three major pieces:

    Web Browser
          |
          | HTTP / JSON API
          v
    +--------------------------------------+
    |              ESP32-S3               |
    |                                      |
    |  +----------------+  +------------+  |
    |  |   DNS Server   |  |   DNSAPI   |  |
    |  |                |  |            |  |
    |  | DNS filtering  |  | /api/health|  |
    |  | DNS forwarding |  | /api/stats |  |
    |  | Query tracking |  | /api/activity |
    |  | Client tracking|  | /api/domains |
    |  +-------+--------+  | /api/clients |
    |          |           | /api/config  |
    |          v           | /api/system  |
    |  +----------------+  | /api/sbc     |
    |  | Statistics / DB|  | /api/throughput |
    |  +----------------+  | /api/stats/reset |
    |                      +------------+  |
    |                                      |
    |          MicroPython + uasyncio      |
    +--------------------------------------+
          |
          v
       Network / Wi-Fi

The ESP32-S3 handles the DNS workload and telemetry. The dashboard remains a relatively thin client that periodically polls the device's API.

---

## Features

### DNS Monitoring

The dashboard provides an at-a-glance view of DNS activity including:

- Total DNS queries
- Blocked queries
- Allowed queries
- Block rate
- Forwarded queries
- DNS timeouts
- DNS errors
- Average upstream latency
- Maximum upstream latency
- Active clients

### Live Activity

Recent DNS requests are displayed in a live activity table containing:

| Field | Description |
|---|---|
| Time | Relative time since the request |
| Domain | Requested DNS domain |
| Client | Requesting client |
| Action | Blocked, allowed, timeout, or error |
| Latency | Request latency |
| Match | Matching block-list entry, when available |

The dashboard refreshes recent activity approximately once per second.

### Rankings

Mi-Hole tracks and displays:

- Top blocked domains
- Top clients

The dashboard uses proportional bars to make relative request volume easy to see.

### Hardware Monitoring

Because the monitoring API runs directly on the ESP32-S3, the dashboard can expose hardware-level information without requiring a separate monitoring system.

Current telemetry includes:

- CPU frequency
- Event-loop load estimate
- Free heap
- Allocated heap
- Flash capacity
- Flash usage
- Flash free space
- ESP32 temperature
- Reset cause
- Wi-Fi RSSI
- Wi-Fi transmit power
- Pending DNS requests
- MicroPython version
- Uptime

### Throughput Monitoring

Mi-Hole also tracks request throughput:

- DNS queries/sec
- HTTP requests/sec
- HTTP bytes sent/sec
- Total DNS queries
- Total HTTP requests
- Total HTTP response bytes

The rate calculations are performed on the device rather than requiring a separate metrics stack.

### Statistics Reset

The dashboard includes a **Clear statistics** action for resetting accumulated DNS statistics.

---

## API

The ESP32 exposes a small HTTP/JSON API intended specifically for the dashboard.

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/health` | Health check |
| `GET` | `/api/stats` | DNS statistics |
| `GET` | `/api/activity` | Recent DNS activity |
| `GET` | `/api/domains` | Top blocked domains |
| `GET` | `/api/clients` | Top clients |
| `GET` | `/api/config` | DNS configuration |
| `GET` | `/api/system` | Runtime and Wi-Fi information |
| `GET` | `/api/sbc` | Hardware statistics |
| `GET` | `/api/throughput` | DNS/HTTP throughput |
| `POST` | `/api/stats/reset` | Reset DNS statistics |

Several endpoints accept a `limit` query parameter.

For example:

    GET /api/activity?limit=50
    GET /api/domains?limit=10
    GET /api/clients?limit=10

---

## HTTP API Design

The monitoring API is deliberately implemented without a large web framework.

It uses:

- MicroPython `uasyncio`
- A small HTTP request parser
- JSON responses via `ujson`
- Explicit request and header size limits
- CORS headers
- Connection-per-request HTTP handling
- Lightweight telemetry collection

Basic request protection is built into the server:

- Request-line length is limited.
- Header size is limited.
- Malformed request lines return `400`.
- Oversized request targets return `414`.
- Oversized headers return `431`.
- Unknown endpoints return `404`.
- Unexpected server errors return `500`.

Responses use `Cache-Control: no-store`, which is appropriate for live telemetry.

---

## Event-Loop Load Monitoring

One of the more interesting parts of the project is the CPU/load telemetry.

A conventional desktop operating system provides CPU utilization metrics through the operating system. Bare-metal MicroPython does not provide an equivalent OS-level utilization counter.

Mi-Hole therefore estimates event-loop load by measuring scheduling latency.

The monitor repeatedly schedules a short sleep:

    requested delay
          |
          v
    uasyncio.sleep_ms()
          |
          v
    actual elapsed time
          |
          v
    scheduling lateness
          |
          v
    load estimate

When the event loop is lightly loaded, the task generally wakes close to its requested interval. As other work occupies the event loop, the observed scheduling delay increases.

The resulting value should therefore be treated as an **event-loop load estimate**, rather than an exact hardware CPU-utilization measurement.

---

## Dashboard Refresh Rates

The web dashboard uses different polling intervals depending on the type of information.

| Data | Refresh |
|---|---:|
| DNS statistics | ~2 seconds |
| Recent activity | ~1 second |
| Domain/client rankings | ~5 seconds |
| Configuration/system information | ~5 seconds |
| SBC/throughput telemetry | ~2 seconds |

This keeps the activity view responsive without unnecessarily polling the ESP32 for relatively static information.

---

## Firmware Startup

The application entry point performs the following sequence:

    Start
      |
      v
    Initialize Wi-Fi
      |
      +-- failure --> RuntimeError
      |
      v
    Create DNS server
      |
      v
    Load DNS database
      |
      v
    Initialize DNS monitoring API
      |
      v
    Start HTTP API
      |
      v
    Run DNS server
      |
      v
    Shutdown / cleanup

The firmware uses `uasyncio` to run the HTTP monitoring API alongside the DNS server.

On shutdown, the application attempts to close:

- The HTTP API
- The DNS server
- The DNS database

---

## Hardware

### Target

**ESP32-S3**

The project is designed around running the DNS appliance directly on an ESP32-S3 with Micropython 1.29.

The exact hardware requirements may depend on the particular ESP32-S3 board being used.

---

## Software Stack

### Firmware

- MicroPython
- `uasyncio`
- ESP32-S3 hardware APIs
- Wi-Fi networking
- DNS server
- JSON/HTTP monitoring API

### Dashboard

- React
- TypeScript
- Browser-based HTTP/JSON polling

The two sides communicate over the local network:

    ESP32-S3
       |
       | HTTP / JSON
       v
    Browser
       |
       v
    React Dashboard


---

## Design Philosophy

Mi-Hole is intentionally small.

Rather than treating an ESP32 as a miniature Linux computer, the project works within the constraints of MicroPython and uses those constraints as part of the design.

That means:

- No heavyweight web framework
- No external monitoring daemon
- No database server
- No operating-system dependency
- No requirement for a separate monitoring machine
- Minimal HTTP implementation
- Asynchronous firmware architecture
- Browser-based visualization

The dashboard is primarily a window into what the ESP32 is already doing.

---

## Why an ESP32-S3?

A DNS appliance does not necessarily need a general-purpose computer.

The ESP32-S3 provides:

- Wi-Fi connectivity
- A capable microcontroller
- Sufficient resources for this type of application
- Hardware telemetry
- Low power requirements
- A compact physical footprint
- An inexpensive platform for experimentation

The project is therefore as much an exploration of **how far a microcontroller can be pushed as a practical network appliance** as it is a DNS filtering project.

---

## Current Limitations

This project is intentionally aimed at experimentation, learning, and small-scale deployments.

Potential limitations include:

- MicroPython is not equivalent to a full Linux networking environment.
- The HTTP API is intentionally minimal.
- Event-loop load is an estimate rather than true hardware CPU utilization.
- Telemetry availability can depend on MicroPython firmware and port support.
- Hardware-specific readings such as temperature may not be available on every firmware build.
- The dashboard assumes the ESP32's API is reachable from the browser.
- The monitoring API does not implement authentication.
- CORS is intentionally permissive for local dashboard use.

**Do not expose the management API directly to an untrusted network without adding appropriate access controls.**

---

## Disclaimer

Mi-Hole is an independent experimental project.

It is inspired by the general concept of network-wide DNS filtering and monitoring, but is not a fork of Pi-hole and is not affiliated with or endorsed by the Pi-hole project.

This software is provided for informational and educational purposes. Use of this software does not imply endorsement by the author of any particular use or application. The author assumes no responsibility or liability for any damages or consequences arising from its use.

---

## Copyright

Copyright © 2026 Roger B. Leuthner. All rights reserved.

Unless otherwise specified elsewhere in this repository, the software is provided for informational and educational purposes.

See the repository's license files and individual source-file notices for applicable terms.

---

## Project Status

🚧 **Experimental / hobby project**

Mi-Hole is an exploration of building a useful DNS appliance and monitoring interface on constrained ESP32-S3 hardware using MicroPython.

If you're interested in tiny network appliances, MicroPython, DNS, embedded networking, or squeezing useful telemetry out of microcontrollers, feel free to explore the code.
