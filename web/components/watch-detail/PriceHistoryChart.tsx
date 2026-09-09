'use client';

import { formatKRW } from '@/lib/format';
import type { WatchStats } from '@/lib/types';

interface Props {
  stats: WatchStats;
}

export default function PriceHistoryChart({ stats }: Props) {
  if (stats.data_months < 1) {
    return (
      <p className="text-sm text-gray-500">
        최저가 패턴 분석 중 — 데이터가 더 쌓이면 표시됩니다.
      </p>
    );
  }

  const maxPrice = Math.max(...stats.monthly_min.map((m) => m.min_krw));
  const bestMonth = stats.overall_min_month;

  return (
    <div className="space-y-3">
      {stats.overall_min !== null && stats.overall_min_month !== null && (
        <p className="text-sm text-gray-700">
          <span className="font-semibold">
            {stats.overall_min_month.slice(5)}월
          </span>
          이 역대 가장 저렴했어요 ({formatKRW(stats.overall_min)})
        </p>
      )}
      <div className="flex items-end gap-1 h-24">
        {stats.monthly_min.map(({ month, min_krw }) => {
          const heightPct = maxPrice > 0 ? (min_krw / maxPrice) * 100 : 100;
          const isBest = month === bestMonth;
          return (
            <div
              key={month}
              className="flex-1 flex flex-col items-center justify-end gap-1"
              title={`${month}: ${formatKRW(min_krw)}`}
            >
              <div
                className={`w-full rounded-t ${
                  isBest ? 'bg-blue-500' : 'bg-gray-300 dark:bg-gray-600'
                }`}
                style={{ height: `${heightPct}%` }}
              />
              <span className="text-xs text-gray-500">{month.slice(5)}월</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
