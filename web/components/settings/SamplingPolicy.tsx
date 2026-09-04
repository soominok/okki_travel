'use client';

import { useAppSettings } from '@/hooks/useSettings';

interface PolicyRow {
  key: string;
  label: string;
  default: number;
  description: string;
}

const POLICY_ROWS: PolicyRow[] = [
  {
    key: 'boundary_price_ratio',
    label: 'boundary_price_ratio',
    default: 1.30,
    description: '인접 가격이 목표가의 몇 배까지 경계 탐색할지',
  },
  {
    key: 'cold_after_probes',
    label: 'cold_after_probes',
    default: 3,
    description: '몇 번 헛치면 포기할지',
  },
  {
    key: 'cold_retry_days',
    label: 'cold_retry_days',
    default: 7,
    description: 'cold 셀 재시도 주기 (일)',
  },
  {
    key: 'per_run_sample_budget',
    label: 'per_run_sample_budget',
    default: 5,
    description: '실행당 샘플링 호출 수',
  },
  {
    key: 'sample_cap_ratio',
    label: 'sample_cap_ratio',
    default: 0.70,
    description: '월 예산 중 SAMPLE 상한 비율',
  },
  {
    key: 'coverage_drop_gate',
    label: 'coverage_drop_gate',
    default: 0.5,
    description: '커버리지가 이 배수 이하로 떨어지면 알림 보류',
  },
];

export default function SamplingPolicy() {
  const { data: settings } = useAppSettings();
  const policy = settings?.sampling_policy ?? {};

  return (
    <section className="rounded-xl border p-5 space-y-3">
      <div className="flex items-start justify-between">
        <h2 className="font-semibold">샘플링 정책</h2>
        <span className="text-xs text-gray-400 bg-gray-100 dark:bg-gray-800 px-2 py-0.5 rounded">
          읽기 전용 (DB 직접 수정)
        </span>
      </div>
      <p className="text-xs text-gray-500">
        이 값들은 추측 기반 초기값입니다. probe_log 적중률을 보고 실데이터로 조정하세요.
      </p>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-xs text-gray-500 border-b">
              <th className="text-left py-2 pr-4">항목</th>
              <th className="text-right py-2 pr-4">기본값</th>
              <th className="text-right py-2 pr-4">현재값</th>
              <th className="text-left py-2">설명</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {POLICY_ROWS.map((row) => {
              const current = policy[row.key as keyof typeof policy];
              return (
                <tr key={row.key}>
                  <td className="py-2 pr-4 font-mono text-xs">{row.label}</td>
                  <td className="py-2 pr-4 text-right tabular-nums text-gray-400">
                    {row.default}
                  </td>
                  <td className="py-2 pr-4 text-right tabular-nums font-semibold">
                    {current ?? '—'}
                  </td>
                  <td className="py-2 text-xs text-gray-500">{row.description}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
