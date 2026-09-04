'use client';

import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '@/lib/client';
import type { AlertOut } from '@/lib/types';

interface AlertFilters {
  unread?: boolean;
  watchId?: string;
  limit?: number;
}

export function useAlerts(filters: AlertFilters = {}) {
  const params = new URLSearchParams();
  if (filters.unread) params.set('unread', '1');
  if (filters.watchId) params.set('watch_id', filters.watchId);
  if (filters.limit) params.set('limit', String(filters.limit));
  const qs = params.toString();

  return useQuery<AlertOut[]>({
    queryKey: ['alerts', filters],
    queryFn: () => apiFetch<AlertOut[]>(`/api/alerts${qs ? `?${qs}` : ''}`),
  });
}
