'use client';

import type { OfferOut } from '@/lib/types';

interface CoverageHeatmapProps {
  offers: OfferOut[];
  dateFrom: string;   // ISO date "2024-09-01"
  dateTo: string;     // ISO date "2025-03-01"
}

function datesToSlots(from: string, to: string) {
  const slots: string[] = [];
  const start = new Date(from);
  const end = new Date(to);
  for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
    slots.push(d.toISOString().slice(0, 10));
  }
  return slots.slice(0, 180); // 최대 180칸
}

export default function CoverageHeatmap({
  offers,
  dateFrom,
  dateTo,
}: CoverageHeatmapProps) {
  const slots = datesToSlots(dateFrom, dateTo);
  const coveredDates = new Set(
    offers.map((o) => o.depart_date).filter(Boolean),
  );

  const filled = slots.filter((d) => coveredDates.has(d)).length;

  return (
    <div>
      <div className="text-sm font-medium mb-2">
        커버리지 {slots.length}칸 중 {filled}칸 ({Math.round((filled / (slots.length || 1)) * 100)}%)
      </div>

      <div className="flex flex-wrap gap-0.5">
        {slots.map((date) => {
          const has = coveredDates.has(date);
          return (
            <div
              key={date}
              title={date}
              className={`w-3 h-3 rounded-sm ${
                has
                  ? 'bg-green-500'
                  : 'bg-gray-200 dark:bg-gray-700'
              }`}
            />
          );
        })}
      </div>

      <div className="flex gap-4 mt-2 text-xs text-gray-500">
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-3 rounded-sm bg-green-500" /> 데이터 있음
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-3 rounded-sm bg-gray-200 dark:bg-gray-700" /> 빈칸
        </span>
      </div>
    </div>
  );
}
