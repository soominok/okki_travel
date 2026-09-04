'use client';

import Link from 'next/link';
import { useWatchSparkline } from '@/hooks/useWatches';
import Sparkline from './Sparkline';
import { formatKRW, formatPriceDelta, formatRelative } from '@/lib/format';
import type { WatchOut } from '@/lib/types';

interface WatchCardProps {
  watch: WatchOut;
  onRunNow?: () => void;
}

function FreshnessDot({ freshness }: { freshness: 'live' | 'cached' }) {
  if (freshness === 'live') {
    return <span className="text-green-500 text-xs">● 실측</span>;
  }
  return <span className="text-gray-400 text-xs">○ 캐시 (최대 7일 전)</span>;
}

export default function WatchCard({ watch, onRunNow }: WatchCardProps) {
  const { data: snaps = [] } = useWatchSparkline(watch.id);

  const prices = snaps
    .map((s) => s.min_price_krw)
    .filter((p): p is number => p !== null);

  const latestSnap = snaps.at(-1);
  const prevSnap = snaps.at(-2);
  const currPrice = latestSnap?.min_price_krw ?? null;
  const prevPrice = prevSnap?.min_price_krw ?? null;

  const delta =
    currPrice !== null && prevPrice !== null
      ? formatPriceDelta(prevPrice, currPrice)
      : null;

  // 목표가 추출 (threshold 규칙에서)
  const thresholdRule = watch.rules.find((r) => r.type === 'threshold');
  const targetPrice = thresholdRule?.threshold ?? null;

  const isPaused = watch.status === 'paused';
  const hasError = watch.status === 'error';

  return (
    <div
      className={`relative rounded-xl border p-4 flex flex-col gap-3 ${
        isPaused ? 'opacity-60' : ''
      }`}
    >
      {hasError && (
        <div className="absolute top-0 left-0 right-0 h-1 rounded-t-xl bg-orange-400" />
      )}

      {/* 헤더 */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-base font-semibold">{watch.name}</span>
            {isPaused && (
              <span className="text-xs bg-gray-200 dark:bg-gray-700 px-2 py-0.5 rounded">
                일시중지
              </span>
            )}
          </div>
          {latestSnap && (
            <div className="mt-0.5">
              <FreshnessDot freshness={latestSnap.freshness} />
            </div>
          )}
        </div>
      </div>

      {/* 가격 */}
      {currPrice !== null ? (
        <div>
          <div className="text-2xl font-bold tabular-nums">
            {formatKRW(currPrice)}
          </div>
          {delta && (
            <div
              className={`text-sm tabular-nums ${
                delta.direction === 'down'
                  ? 'text-green-600'
                  : delta.direction === 'up'
                    ? 'text-red-500'
                    : 'text-gray-500'
              }`}
            >
              {delta.text}
            </div>
          )}
        </div>
      ) : (
        <div className="text-sm text-gray-500">
          아직 데이터를 못 찾았습니다 (0/{prices.length || 180}칸)
        </div>
      )}

      {/* 스파크라인 */}
      <Sparkline data={prices} className="text-gray-600 dark:text-gray-400" />

      {/* 커버리지 바 */}
      {latestSnap?.coverage_pct !== null && latestSnap?.coverage_pct !== undefined && (
        <div>
          <div className="text-xs text-gray-500 mb-1">
            커버리지 {Math.round(latestSnap.coverage_pct * 100)}%
          </div>
          <div className="h-1.5 rounded-full bg-gray-200 dark:bg-gray-700">
            <div
              className="h-full rounded-full bg-blue-500"
              style={{ width: `${latestSnap.coverage_pct * 100}%` }}
            />
          </div>
        </div>
      )}

      {/* 목표가 상태 */}
      {targetPrice !== null && currPrice !== null && (
        <div className="text-xs text-gray-600 dark:text-gray-400">
          목표 {formatKRW(targetPrice)}{' '}
          {currPrice <= targetPrice ? (
            <span className="text-green-600 font-semibold">✅ 달성</span>
          ) : (
            <span className="text-gray-500">
              ({formatKRW(currPrice - targetPrice)} 초과)
            </span>
          )}
        </div>
      )}

      {/* 마지막 수집 */}
      {latestSnap && (
        <div className="text-xs text-gray-500">
          {formatRelative(latestSnap.captured_at)}
        </div>
      )}

      {/* 액션 버튼 */}
      <div className="flex gap-2 mt-1">
        <Link
          href={`/watches/${watch.id}`}
          className="flex-1 text-center text-xs border rounded-lg py-1.5 hover:bg-gray-50 dark:hover:bg-gray-800"
        >
          상세
        </Link>
        <button
          onClick={onRunNow}
          className="flex-1 text-xs border rounded-lg py-1.5 hover:bg-gray-50 dark:hover:bg-gray-800"
        >
          지금 조회
        </button>
      </div>
    </div>
  );
}
