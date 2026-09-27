// Copyright © 2026 Roger B. Leuthner. All rights reserved.  This software is provided for informational and educational purposes. Use of this software does not imply endorsement by the author of any particular use or application. The author assumes no responsibility or liability for any damages or consequences arising from its use.

import type {
  ActivityResponse,
  Config,
  RankedResponse,
  SbcInfo,
  Stats,
  SystemInfo,
  Throughput
} from './types';

async function get<T>(
  path: string
): Promise<T> {
  const response = await fetch(path, {
    cache: 'no-store'
  });

  if (!response.ok) {
    throw new Error(
      `API request failed: ${response.status}`
    );
  }

  return response.json() as Promise<T>;
}

export function getStats(): Promise<Stats> {
  return get<Stats>('/api/stats');
}

export function getActivity(
  limit = 50
): Promise<ActivityResponse> {
  return get<ActivityResponse>(
    `/api/activity?limit=${limit}`
  );
}

export function getDomains(
  limit = 8
): Promise<RankedResponse> {
  return get<RankedResponse>(
    `/api/domains?limit=${limit}`
  );
}

export function getClients(
  limit = 8
): Promise<RankedResponse> {
  return get<RankedResponse>(
    `/api/clients?limit=${limit}`
  );
}

export function getConfig(): Promise<Config> {
  return get<Config>('/api/config');
}

export function getSystem(): Promise<SystemInfo> {
  return get<SystemInfo>('/api/system');
}

export function getSbc(): Promise<SbcInfo> {
  return get<SbcInfo>('/api/sbc');
}

export function getThroughput(): Promise<Throughput> {
  return get<Throughput>('/api/throughput');
}

export async function resetStats(): Promise<void> {
  const response = await fetch(
    '/api/stats/reset',
    {
      method: 'POST'
    }
  );

  if (!response.ok) {
    throw new Error(
      `Reset failed: ${response.status}`
    );
  }
}
