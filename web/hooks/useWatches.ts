'use client';

import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '@/lib/client';
import type { WatchOut, PriceSnapshotOut } from '@/lib/types';

export function useWatches() {
  return useQuery<WatchOut[]>({
    queryKey: ['watches'],
    queryFn: () => apiFetch<WatchOut[]>('/api/watches'),
  });
}

export function useWatchSparkline(watchId: string, enabled = true) {
  return useQuery<PriceSnapshotOut[]>({
    queryKey: ['watches', watchId, 'sparkline'],
    queryFn: () =>
      apiFetch<PriceSnapshotOut[]>(
        `/api/watches/${watchId}/snapshots?limit=30&order=asc`,
      ),
    enabled,
    staleTime: 5 * 60_000,
  });
}
