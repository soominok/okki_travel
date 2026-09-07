'use client';

import { useState } from 'react';
import {
  ComposedChart,
  Area,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts';
import type { PriceSnapshotOut } from '@/lib/types';
import { formatKRW, formatKST } from '@/lib/format';

interface PriceChartProps {
  snapshots: PriceSnapshotOut[];
  targetPrice?: number;
}

type Period = '30d' | '90d' | 'all';

function filterByPeriod(snaps: PriceSnapshotOut[], period: Period) {
  if (period === 'all') return snaps;
  const days = period === '30d' ? 30 : 90;
  const cutoff = Date.now() - days * 86_400_000;
  return snaps.filter((s) => new Date(s.captured_at).getTime() >= cutoff);
}

export default function PriceChart({ snapshots, targetPrice }: PriceChartProps) {
  const [period, setPeriod] = useState<Period>('30d');

  const filtered = filterByPeriod(snapshots, period);
  const data = filtered.map((s) => ({
    date: formatKST(s.captured_at, 'MM/dd'),
    min: s.min_price_krw,
    median: s.median_price_krw,
    coverage: s.coverage_pct,
  }));

  const allPrices = data
    .flatMap((d) => [d.min, d.median])
    .filter((p): p is number => p !== null);
  const minY = allPrices.length
    ? Math.floor(Math.min(...allPrices) * 0.95 / 10000) * 10000
    : 0;
  const maxY = allPrices.length
    ? Math.ceil(Math.max(...allPrices) * 1.05 / 10000) * 10000
    : 500000;

  return (
    <div>
      <div className="flex gap-2 mb-3">
        {(['30d', '90d', 'all'] as Period[]).map((p) => (
          <button
            key={p}
            onClick={() => setPeriod(p)}
            className={`text-xs px-3 py-1 rounded-full border ${
              period === p
                ? 'bg-blue-600 text-white border-blue-600'
                : 'border-gray-300 hover:border-gray-500'
            }`}
          >
            {p === '30d' ? '30일' : p === '90d' ? '90일' : '전체'}
          </button>
        ))}
      </div>

      <div className="flex gap-4 text-xs text-gray-500 mb-2">
        <span className="flex items-center gap-1">
          <span className="inline-block w-6 h-0.5 bg-green-400" /> 최저가
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-6 border-t border-dashed border-gray-400" /> 중앙값
        </span>
        {targetPrice && (
          <span className="flex items-center gap-1">
            <span className="inline-block w-6 h-0.5 bg-blue-500" /> 목표가
          </span>
        )}
      </div>

      <ResponsiveContainer width="100%" height={220}>
        <ComposedChart data={data} margin={{ top: 4, right: 8, bottom: 4, left: 8 }}>
          <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 11 }}
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fontSize: 11 }}
            tickFormatter={(v) => `₩${(v / 10000).toFixed(0)}만`}
            domain={[minY, maxY]}
            width={60}
          />
          <Tooltip
            formatter={(value, name) => [
              typeof value === 'number' ? formatKRW(value) : String(value ?? ''),
              name === 'min' ? '최저가' : '중앙값',
            ]}
          />
          <Area
            type="monotone"
            dataKey="min"
            stroke="#4ade80"
            fill="#4ade8030"
            strokeWidth={2}
            dot={false}
            connectNulls
          />
          <Line
            type="monotone"
            dataKey="median"
            stroke="#9ca3af"
            strokeWidth={1.5}
            strokeDasharray="4 2"
            dot={false}
            connectNulls
          />
          {targetPrice && (
            <ReferenceLine
              y={targetPrice}
              stroke="#3b82f6"
              strokeWidth={1.5}
              label={{
                value: `목표 ${formatKRW(targetPrice)}`,
                position: 'insideTopLeft',
                fontSize: 11,
                fill: '#3b82f6',
              }}
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
