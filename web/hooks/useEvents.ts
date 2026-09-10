'use client';

import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '@/lib/client';
import type { EventOut } from '@/lib/types';

export function useEvents(source?: string) {
  return useQuery<EventOut[]>({
    queryKey: ['events', source ?? 'all'],
    queryFn: () => {
      const params = new URLSearchParams({ active_only: 'true' });
      if (source) params.set('source', source);
      return apiFetch<EventOut[]>(`/api/events?${params}`);
    },
    staleTime: 30 * 60_000,  // 30분 캐시
  });
}
