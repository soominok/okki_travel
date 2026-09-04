'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '@/lib/client';
import type { WatchOut, WatchCreate, PriceSnapshotOut } from '@/lib/types';

export function useWatches() {
  return useQuery<WatchOut[]>({
    queryKey: ['watches'],
    queryFn: () => apiFetch<WatchOut[]>('/api/watches'),
  });
}

export function useCreateWatch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: WatchCreate) =>
      apiFetch<WatchOut>('/api/watches', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['watches'] }),
  });
}

export function useRunNow(watchId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiFetch(`/api/watches/${watchId}/run`, { method: 'POST' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['watches', watchId] });
      qc.invalidateQueries({ queryKey: ['watches', watchId, 'snapshots'] });
    },
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

import type { OfferOut, WorkerRunOut } from '@/lib/types';

export function useWatch(id: string) {
  return useQuery<WatchOut>({
    queryKey: ['watches', id],
    queryFn: () => apiFetch<WatchOut>(`/api/watches/${id}`),
  });
}

export function useWatchSnapshots(id: string) {
  return useQuery<PriceSnapshotOut[]>({
    queryKey: ['watches', id, 'snapshots'],
    queryFn: () =>
      apiFetch<PriceSnapshotOut[]>(`/api/watches/${id}/snapshots?order=asc`),
    staleTime: 2 * 60_000,
  });
}

export function useWatchOffers(id: string) {
  return useQuery<OfferOut[]>({
    queryKey: ['watches', id, 'offers'],
    queryFn: () => apiFetch<OfferOut[]>(`/api/watches/${id}/offers`),
    staleTime: 2 * 60_000,
  });
}

export function useWatchRuns(id: string) {
  return useQuery<WorkerRunOut[]>({
    queryKey: ['watches', id, 'runs'],
    queryFn: () => apiFetch<WorkerRunOut[]>(`/api/watches/${id}/runs`),
    staleTime: 60_000,
  });
}
