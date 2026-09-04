'use client';

import { useQuery } from '@tanstack/react-query';
import type { HealthOut } from '@/lib/types';

export function useWorkerStatus() {
  return useQuery<HealthOut>({
    queryKey: ['worker-status'],
    queryFn: async () => {
      // Next.js 프록시 라우트 사용 (토큰 불필요 — /healthz는 공개 엔드포인트)
      const res = await fetch('/api/health');
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json();
    },
    refetchInterval: 15_000,
    retry: false,
  });
}
