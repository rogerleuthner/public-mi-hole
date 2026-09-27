// Copyright © 2026 Roger B. Leuthner. All rights reserved.  This software is provided for informational and educational purposes. Use of this software does not imply endorsement by the author of any particular use or application. The author assumes no responsibility or liability for any damages or consequences arising from its use.

export interface Stats {
  active_clients: number;
  uptime_ms: number;
  queries: number;
  blocked: number;
  allowed: number;
  forwarded: number;
  responses: number;
  timeouts: number;
  errors: number;
  block_rate: number;
  latency_avg_ms: number;
  latency_max_ms: number;
  tracked_domains: number;
}

export interface ActivityItem {
  id: number;
  uptime_ms: number;
  domain: string;
  client: string;
  action:
  | 'blocked'
  | 'forwarded'
  | 'allowed'
  | 'timeout'
  | 'error';
  latency_ms: number;
  match: string | null;
}

export interface ActivityResponse {
  items: ActivityItem[];
}

export interface RankedItem {
  name: string;
  count: number;
}

export interface RankedResponse {
  items: RankedItem[];
}

export interface Config {
  listen_ip: string;
  dns_port: number;
  upstream_ip: string;
  upstream_port: number;
}

export interface SystemInfo {
  uptime_ms: number;
  free_heap: number | null;
  allocated_heap: number | null;
  wifi_connected: boolean;
  wifi_rssi: number | null;
  ip_address: string | null;
  micropython: string;
  pending_requests: number;
}

export interface SbcInfo {
  cpu_freq_mhz: number | null;
  cpu_util_pct: number | null;
  flash_total_bytes: number | null;
  flash_used_bytes: number | null;
  flash_free_bytes: number | null;
  temperature_c: number | null;
  reset_cause: string | null;
  wifi_tx_power_dbm: number | null;
}

export interface Throughput {
  dns_queries_total: number | null;
  dns_queries_per_sec: number | null;
  http_requests_total: number;
  http_requests_per_sec: number | null;
  http_bytes_sent_total: number;
  http_bytes_sent_per_sec: number | null;
}
