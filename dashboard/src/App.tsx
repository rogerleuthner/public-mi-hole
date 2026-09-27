// Copyright © 2026 Roger B. Leuthner. All rights reserved.  This software is provided for informational and educational purposes. Use of this software does not imply endorsement by the author of any particular use or application. The author assumes no responsibility or liability for any damages or consequences arising from its use.

import {
  useCallback,
  useEffect,
  useMemo,
  useState
} from 'react';

import {
  getActivity,
  getClients,
  getConfig,
  getDomains,
  getSbc,
  getStats,
  getSystem,
  getThroughput,
  resetStats
} from './api';

import type {
  ActivityItem,
  Config,
  RankedItem,
  SbcInfo,
  Stats,
  SystemInfo,
  Throughput
} from './types';

function formatNumber(value: number): string {
  return new Intl.NumberFormat().format(value);
}

function formatBytes(value: number | null): string {
  if (value === null) {
    return '—';
  }

  if (value < 1024) {
    return `${value} B`;
  }

  return `${(value / 1024).toFixed(1)} KB`;
}

function formatRate(value: number | null): string {
  if (value === null) {
    return '—';
  }

  return value < 10
    ? value.toFixed(1)
    : Math.round(value).toString();
}

function formatUptime(milliseconds: number): string {
  const totalSeconds = Math.floor(milliseconds / 1000);

  const days = Math.floor(totalSeconds / 86400);

  const hours = Math.floor(
    (totalSeconds % 86400) / 3600
  );

  const minutes = Math.floor(
    (totalSeconds % 3600) / 60
  );

  const seconds = totalSeconds % 60;

  if (days > 0) {
    return `${days}d ${hours}h ${minutes}m`;
  }

  if (hours > 0) {
    return `${hours}h ${minutes}m ${seconds}s`;
  }

  if (minutes > 0) {
    return `${minutes}m ${seconds}s`;
  }

  return `${seconds}s`;
}

function formatActivityTime(
  uptimeMs: number,
  currentUptimeMs: number | null
): string {
  if (currentUptimeMs === null) {
    return '—';
  }

  const ageMs = Math.max(
    0,
    currentUptimeMs - uptimeMs
  );

  if (ageMs < 5000) {
    return 'just now';
  }

  const seconds = Math.floor(ageMs / 1000);

  if (seconds < 60) {
    return `${seconds}s ago`;
  }

  const minutes = Math.floor(seconds / 60);

  if (minutes < 60) {
    return `${minutes}m ago`;
  }

  return `${Math.floor(minutes / 60)}h ago`;
}

function actionLabel(
  action: ActivityItem['action']
): string {
  switch (action) {
    case 'blocked':
      return 'BLOCKED';

    case 'allowed':
      return 'ALLOWED';

    case 'timeout':
      return 'TIMEOUT';

    case 'error':
      return 'ERROR';

    default:
      return 'UNKNOWN';
  }
}

function StatCard({
  label,
  value,
  detail,
  tone = 'default'
}: {
  label: string;
  value: string;
  detail?: string;
  tone?: 'default' | 'green' | 'red' | 'blue';
}) {
  return (
    <div
      className={`stat-card stat-card-${tone}`}
    >
      <span className="stat-label">
        {label}
      </span>

      <strong className="stat-value">
        {value}
      </strong>

      {detail && (
        <span className="stat-detail">
          {detail}
        </span>
      )}
    </div>
  );
}

function Section({
  title,
  children,
  className = ''
}: {
  title: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`panel ${className}`}
    >
      <div className="panel-header">
        <h2>{title}</h2>
      </div>

      {children}
    </section>
  );
}

function RankedList({
  items,
  emptyLabel
}: {
  items: RankedItem[];
  emptyLabel: string;
}) {
  const maximum = Math.max(
    ...items.map((item) => item.count),
    1
  );

  if (items.length === 0) {
    return (
      <div className="empty-state">
        {emptyLabel}
      </div>
    );
  }

  return (
    <div className="ranked-list">
      {items.map((item, index) => (
        <div
          className="ranked-item"
          key={item.name}
        >
          <div className="rank-number">
            {index + 1}
          </div>

          <div className="rank-content">
            <div className="rank-row">
              <span
                className="rank-name"
                title={item.name}
              >
                {item.name}
              </span>

              <span className="rank-count">
                {formatNumber(item.count)}
              </span>
            </div>

            <div className="rank-bar-track">
              <div
                className="rank-bar"
                style={{
                  width: `${
                    (item.count / maximum) *
                    100
                  }%`
                }}
              />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function ActivityTable({
  items,
  currentUptimeMs
}: {
  items: ActivityItem[];
  currentUptimeMs: number | null;
}) {
  if (items.length === 0) {
    return (
      <div className="empty-state">
        Waiting for DNS activity…
      </div>
    );
  }

  return (
    <div className="activity-table-wrap">
      <table className="activity-table">
        <thead>
          <tr>
            <th>Time</th>
            <th>Domain</th>
            <th>Client</th>
            <th>Action</th>
            <th>Latency</th>
          </tr>
        </thead>

        <tbody>
          {items
            .slice()
            .reverse()
            .map((item, index) => (
              <tr
                key={`${item.uptime_ms}-${index}`}
              >
                <td className="muted">
                  {formatActivityTime(
                    item.uptime_ms,
                    currentUptimeMs
                  )}
                </td>

                <td>
                  <span className="domain-name">
                    {item.domain}
                  </span>

                  {item.match && (
                    <span className="match-label">
                      matched {item.match}
                    </span>
                  )}
                </td>

                <td className="mono">
                  {item.client}
                </td>

                <td>
                  <span
                    className={`action-badge action-${item.action}`}
                  >
                    {actionLabel(
                      item.action
                    )}
                  </span>
                </td>

                <td className="muted">
                  {item.latency_ms > 0
                    ? `${item.latency_ms} ms`
                    : '—'}
                </td>
              </tr>
            ))}
        </tbody>
      </table>
    </div>
  );
}

function TrafficChart({
  stats
}: {
  stats: Stats | null;
}) {
  const allowed = stats?.allowed ?? 0;
  const blocked = stats?.blocked ?? 0;
  const total = allowed + blocked;

  const blockedWidth =
    total > 0
      ? (blocked / total) * 100
      : 0;

  const allowedWidth =
    total > 0
      ? (allowed / total) * 100
      : 0;

  return (
    <div className="traffic-chart">
      <div className="traffic-summary">
        <div>
          <span className="traffic-dot dot-green" />
          Allowed
          <strong>
            {formatNumber(allowed)}
          </strong>
        </div>

        <div>
          <span className="traffic-dot dot-red" />
          Blocked
          <strong>
            {formatNumber(blocked)}
          </strong>
        </div>
      </div>

      <div className="traffic-bar">
        <div
          className="traffic-allowed"
          style={{
            width: `${allowedWidth}%`
          }}
        />

        <div
          className="traffic-blocked"
          style={{
            width: `${blockedWidth}%`
          }}
        />
      </div>

      <div className="traffic-total">
        {formatNumber(total)} queries
      </div>
    </div>
  );
}

export default function App() {
  const [stats, setStats] =
    useState<Stats | null>(null);

  const [activity, setActivity] =
    useState<ActivityItem[]>([]);

  const [domains, setDomains] =
    useState<RankedItem[]>([]);

  const [clients, setClients] =
    useState<RankedItem[]>([]);

  const [config, setConfig] =
    useState<Config | null>(null);

  const [system, setSystem] =
    useState<SystemInfo | null>(null);

  const [sbc, setSbc] =
    useState<SbcInfo | null>(null);

  const [throughput, setThroughput] =
    useState<Throughput | null>(null);

  const [error, setError] =
    useState<string | null>(null);

  const refreshStats = useCallback(
    async () => {
      try {
        const result = await getStats();

        setStats(result);
        setError(null);
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : 'Unable to contact DNS server'
        );
      }
    },
    []
  );

  const refreshActivity = useCallback(
    async () => {
      try {
        const result =
          await getActivity(50);

        setActivity(result.items);
      } catch {
        // The stats polling reports
        // connection errors.
      }
    },
    []
  );

  const refreshRankings = useCallback(
    async () => {
      try {
        const [
          domainResult,
          clientResult
        ] = await Promise.all([
          getDomains(8),
          getClients(8)
        ]);

        setDomains(domainResult.items);
        setClients(clientResult.items);
      } catch {
        // Connection errors are reported
        // by stats polling.
      }
    },
    []
  );

  const refreshSystem = useCallback(
    async () => {
      try {
        const [
          configResult,
          systemResult
        ] = await Promise.all([
          getConfig(),
          getSystem()
        ]);

        setConfig(configResult);
        setSystem(systemResult);
      } catch {
        // Connection errors are reported
        // by stats polling.
      }
    },
    []
  );

  const refreshSbc = useCallback(
    async () => {
      try {
        const [
          sbcResult,
          throughputResult
        ] = await Promise.all([
          getSbc(),
          getThroughput()
        ]);

        setSbc(sbcResult);
        setThroughput(throughputResult);
      } catch {
        // Connection errors are reported
        // by stats polling.
      }
    },
    []
  );

  useEffect(() => {
    void refreshStats();
    void refreshActivity();
    void refreshRankings();
    void refreshSystem();
    void refreshSbc();

    const statsTimer =
      window.setInterval(
        () => {
          void refreshStats();
        },
        2000
      );

    const activityTimer =
      window.setInterval(
        () => {
          void refreshActivity();
        },
        1000
      );

    const rankingTimer =
      window.setInterval(
        () => {
          void refreshRankings();
        },
        5000
      );

    const systemTimer =
      window.setInterval(
        () => {
          void refreshSystem();
        },
        5000
      );

    const sbcTimer =
      window.setInterval(
        () => {
          void refreshSbc();
        },
        2000
      );

    return () => {
      window.clearInterval(
        statsTimer
      );

      window.clearInterval(
        activityTimer
      );

      window.clearInterval(
        rankingTimer
      );

      window.clearInterval(
        systemTimer
      );

      window.clearInterval(
        sbcTimer
      );
    };
  }, [
    refreshStats,
    refreshActivity,
    refreshRankings,
    refreshSystem,
    refreshSbc
  ]);

  const online =
    system?.wifi_connected ?? false;

  const statusText = error
    ? 'OFFLINE'
    : online
      ? 'ONLINE'
      : 'CONNECTING';

  const uptime = useMemo(
    () =>
      stats
        ? formatUptime(stats.uptime_ms)
        : '—',
    [stats]
  );

  const memUsedPct = useMemo(() => {
    const free = system?.free_heap;
    const used = system?.allocated_heap;

    if (free === null || free === undefined) {
      return null;
    }

    if (used === null || used === undefined) {
      return null;
    }

    const total = free + used;

    if (total <= 0) {
      return null;
    }

    return Math.round((used / total) * 100);
  }, [system]);

  async function handleReset() {
    if (
      !window.confirm(
        'Clear all DNS statistics?'
      )
    ) {
      return;
    }

    try {
      await resetStats();

      await Promise.all([
        refreshStats(),
        refreshActivity(),
        refreshRankings()
      ]);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Unable to reset statistics'
      );
    }
  }

  return (
    <div className="app">
      <header className="topbar">
        <div>
          <div className="brand">
            <span className="brand-mark">
              ◈
            </span>

            <span>Mi-Hole</span>
          </div>

          <div className="subtitle">
            ESP32-S3 DNS appliance
            {system?.ip_address && (
              <>
                {' '}
                · {system.ip_address}
              </>
            )}
          </div>
        </div>

        <div className="header-actions">
          <span
            className={`status ${
              error
                ? 'status-offline'
                : online
                  ? 'status-online'
                  : 'status-connecting'
            }`}
          >
            <span className="status-dot" />

            {statusText}
          </span>

          <button
            className="button button-secondary"
            onClick={handleReset}
          >
            Clear statistics
          </button>
        </div>
      </header>

      {error && (
        <div className="error-banner">
          <strong>
            Connection problem:
          </strong>{' '}
          {error}
        </div>
      )}

      <main className="dashboard">
        <div className="stats-grid">
          <StatCard
            label="Queries"
            value={
              stats
                ? formatNumber(
                    stats.queries
                  )
                : '—'
            }
            detail={`${uptime} uptime`}
            tone="blue"
          />

          <StatCard
            label="Blocked"
            value={
              stats
                ? formatNumber(
                    stats.blocked
                  )
                : '—'
            }
            detail={
              stats
                ? `${stats.block_rate}% block rate`
                : undefined
            }
            tone="red"
          />

          <StatCard
            label="Allowed"
            value={
              stats
                ? formatNumber(
                    stats.allowed
                  )
                : '—'
            }
            detail={
              stats
                ? `${formatNumber(
                    stats.forwarded
                  )} forwarded`
                : undefined
            }
            tone="green"
          />

          <StatCard
            label="Upstream latency"
            value={
              stats
                ? `${stats.latency_avg_ms} ms`
                : '—'
            }
            detail={
              stats
                ? `max ${stats.latency_max_ms} ms`
                : undefined
            }
          />

          <StatCard
            label="Clients"
            value={
              stats
                ? formatNumber(
                    stats.active_clients
                  )
                : '—'
            }
            detail="tracked clients"
          />

          <StatCard
            label="CPU"
            value={
              sbc?.cpu_util_pct !== null &&
              sbc?.cpu_util_pct !== undefined
                ? `${sbc.cpu_util_pct}%`
                : '—'
            }
            detail={
              sbc?.cpu_freq_mhz
                ? `${sbc.cpu_freq_mhz} MHz`
                : undefined
            }
            tone="blue"
          />

          <StatCard
            label="Memory"
            value={
              memUsedPct !== null
                ? `${memUsedPct}%`
                : '—'
            }
            detail={
              system?.free_heap !== null &&
              system?.free_heap !== undefined
                ? `${formatBytes(
                    system.free_heap
                  )} free`
                : undefined
            }
          />

          <StatCard
            label="Throughput"
            value={`${formatRate(
              throughput?.dns_queries_per_sec ??
                null
            )}/s`}
            detail={
              throughput
                ? `${formatRate(
                    throughput.http_requests_per_sec
                  )} req/s`
                : undefined
            }
            tone="green"
          />
        </div>

        <div className="two-column">
          <Section title="DNS Traffic">
            <TrafficChart
              stats={stats}
            />
          </Section>

          <Section title="System">
            <div className="system-grid">
              <div>
                <span>Wi-Fi</span>

                <strong>
                  {online
                    ? 'Connected'
                    : 'Disconnected'}
                </strong>
              </div>

              <div>
                <span>RSSI</span>

                <strong>
                  {system?.wifi_rssi !==
                    null &&
                  system?.wifi_rssi !==
                    undefined
                    ? `${system.wifi_rssi} dBm`
                    : '—'}
                </strong>
              </div>

              <div>
                <span>Free heap</span>

                <strong>
                  {formatBytes(
                    system?.free_heap ??
                      null
                  )}
                </strong>
              </div>

              <div>
                <span>Pending DNS</span>

                <strong>
                  {system?.pending_requests ??
                    0}
                </strong>
              </div>

              <div>
                <span>Timeouts</span>

                <strong>
                  {stats?.timeouts ?? 0}
                </strong>
              </div>

              <div>
                <span>Errors</span>

                <strong>
                  {stats?.errors ?? 0}
                </strong>
              </div>

              <div>
                <span>Flash used</span>

                <strong>
                  {sbc?.flash_used_bytes !==
                    null &&
                  sbc?.flash_used_bytes !==
                    undefined
                    ? formatBytes(
                        sbc.flash_used_bytes
                      )
                    : '—'}
                </strong>
              </div>

              <div>
                <span>Temperature</span>

                <strong>
                  {sbc?.temperature_c !==
                    null &&
                  sbc?.temperature_c !==
                    undefined
                    ? `${sbc.temperature_c}°C`
                    : '—'}
                </strong>
              </div>

              <div>
                <span>Reset cause</span>

                <strong>
                  {sbc?.reset_cause ?? '—'}
                </strong>
              </div>

              <div>
                <span>Wi-Fi TX power</span>

                <strong>
                  {sbc?.wifi_tx_power_dbm !==
                    null &&
                  sbc?.wifi_tx_power_dbm !==
                    undefined
                    ? `${sbc.wifi_tx_power_dbm} dBm`
                    : '—'}
                </strong>
              </div>
            </div>
          </Section>
        </div>

        <div className="two-column">
          <Section title="Top Blocked Domains">
            <RankedList
              items={domains}
              emptyLabel="No blocked domains yet."
            />
          </Section>

          <Section title="Top Clients">
            <RankedList
              items={clients}
              emptyLabel="No clients yet."
            />
          </Section>
        </div>

        <Section
          title="Recent Activity"
          className="activity-panel"
        >
          <ActivityTable
            items={activity}
            currentUptimeMs={
              stats?.uptime_ms ?? null
            }
          />
        </Section>

        <Section title="DNS Configuration">
          <div className="config-grid">
            <div>
              <span>Listen address</span>

              <strong>
                {config?.listen_ip ?? '—'}
              </strong>
            </div>

            <div>
              <span>DNS port</span>

              <strong>
                {config?.dns_port ?? '—'}
              </strong>
            </div>

            <div>
              <span>Upstream DNS</span>

              <strong>
                {config
                  ? `${config.upstream_ip}:${config.upstream_port}`
                  : '—'}
              </strong>
            </div>

            <div>
              <span>MicroPython</span>

              <strong>
                {system?.micropython ?? '—'}
              </strong>
            </div>
          </div>
        </Section>
      </main>
    </div>
  );
}
