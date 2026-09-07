'use client';

import { useMutation, useQuery } from '@tanstack/react-query';
import { apiFetch } from '@/lib/client';

interface SlackTestResult {
  status: 'sent' | 'deferred' | 'error';
  message?: string;
}

export function useSlackTest() {
  return useMutation<SlackTestResult>({
    mutationFn: () =>
      apiFetch<SlackTestResult>('/api/notify/test', { method: 'POST' }),
  });
}

interface AppSettings {
  sampling_policy?: {
    boundary_price_ratio?: number;
    cold_after_probes?: number;
    cold_retry_days?: number;
    per_run_sample_budget?: number;
    sample_cap_ratio?: number;
    coverage_drop_gate?: number;
  };
}

export function useAppSettings() {
  return useQuery<AppSettings>({
    queryKey: ['settings'],
    queryFn: () => apiFetch<AppSettings>('/api/settings').catch(() => ({})),
    staleTime: 60_000,
  });
}
