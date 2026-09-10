'use client';

import { use } from 'react';
import Link from 'next/link';
import {
  useWatch,
  useWatchSnapshots,
  useWatchOffers,
  useWatchRuns,
  useRunNow,
  useWatchStats,
} from '@/hooks/useWatches';
import PriceChart from '@/components/watch-detail/PriceChart';
import PriceHistoryChart from '@/components/watch-detail/PriceHistoryChart';
import OfferList from '@/components/watch-detail/OfferList';
import CoverageHeatmap from '@/components/watch-detail/CoverageHeatmap';
import RunLog from '@/components/watch-detail/RunLog';
import { formatKRW, formatKST } from '@/lib/format';

export default function WatchDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { data: watch, isLoading } = useWatch(id);
  const { data: snapshots = [] } = useWatchSnapshots(id);
  const { data: offers = [] } = useWatchOffers(id);
  const { data: runs = [] } = useWatchRuns(id);
  const { data: stats } = useWatchStats(id);
  const runNow = useRunNow(id);

  if (isLoading) {
    return <div className="p-8 text-sm text-gray-500">불러오는 중…</div>;
  }
  if (!watch) {
    return (
      <div className="p-8">
        <p className="text-red-500">감시를 찾을 수 없습니다.</p>
        <Link href="/" className="text-sm text-blue-600 mt-2 inline-block">
          ← 대시보드로
        </Link>
      </div>
    );
  }

  const latestSnap = snapshots.at(-1);
  const thresholdRule = watch.rules.find((r) => r.type === 'threshold');
  const targetPrice = thresholdRule?.type === 'threshold' ? thresholdRule.price_krw : undefined;

  const watchParams = watch.params;

  return (
    <div className="mx-auto max-w-3xl px-4 py-6 space-y-8">
      {/* 헤더 */}
      <div className="flex items-start justify-between">
        <div>
          <Link href="/" className="text-sm text-gray-500 hover:text-gray-800">
            ← 대시보드
          </Link>
          <h1 className="text-xl font-bold mt-1">{watch.title}</h1>
          <p className="text-sm text-gray-500">
            {watchParams.kind === 'flight' && `${watchParams.origin} → ${watchParams.destination}`} · {Math.round(watch.interval_min / 60)}시간마다
          </p>
        </div>
        <button
          onClick={() => runNow.mutate()}
          disabled={runNow.isPending}
          className="text-sm px-4 py-2 border rounded-lg hover:bg-gray-50 disabled:opacity-40"
        >
          {runNow.isPending ? '조회 중…' : '지금 조회'}
        </button>
      </div>

      {/* 요약 */}
      {latestSnap && latestSnap.min_price_krw !== null && (
        <div className="grid grid-cols-3 gap-4 rounded-xl border p-4">
          <div>
            <div className="text-xs text-gray-500">현재 최저</div>
            <div className="text-xl font-bold tabular-nums">
              {formatKRW(latestSnap.min_price_krw)}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500">오퍼 수</div>
            <div className="text-xl font-bold">{latestSnap.offer_count}</div>
          </div>
          <div>
            <div className="text-xs text-gray-500">마지막 수집</div>
            <div className="text-sm">{formatKST(latestSnap.captured_at)}</div>
          </div>
        </div>
      )}

      {/* 가격 차트 */}
      <section>
        <h2 className="text-sm font-semibold mb-3">가격 히스토리</h2>
        {snapshots.length < 2 ? (
          <p className="text-sm text-gray-500">
            데이터가 쌓이면 차트가 표시됩니다 (현재 {snapshots.length}건)
          </p>
        ) : (
          <PriceChart snapshots={snapshots} targetPrice={targetPrice} />
        )}
      </section>

      {/* 월별 최저가 히스토리 */}
      {stats && (
        <section>
          <h2 className="text-sm font-semibold mb-3">월별 최저가 패턴</h2>
          <PriceHistoryChart stats={stats} />
        </section>
      )}

      {/* 오퍼 목록 */}
      <section>
        <OfferList offers={offers} />
      </section>

      {/* 커버리지 히트맵 */}
      {watchParams.kind === 'flight' && watchParams.depart_from && watchParams.depart_to && (
        <section>
          <h2 className="text-sm font-semibold mb-3">커버리지</h2>
          <CoverageHeatmap
            offers={offers}
            dateFrom={watchParams.depart_from}
            dateTo={watchParams.depart_to}
          />
        </section>
      )}

      {/* 실행 로그 */}
      <section>
        <RunLog runs={runs} />
      </section>
    </div>
  );
}
