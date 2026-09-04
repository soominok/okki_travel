'use client';

import Link from 'next/link';
import { useWatches } from '@/hooks/useWatches';
import { apiFetch } from '@/lib/client';
import { useQueryClient } from '@tanstack/react-query';
import WatchCard from '@/components/dashboard/WatchCard';
import RecentAlerts from '@/components/dashboard/RecentAlerts';

export default function Dashboard() {
  const { data: watches = [], isLoading } = useWatches();
  const qc = useQueryClient();

  async function handleRunNow(watchId: string) {
    try {
      await apiFetch(`/api/watches/${watchId}/run`, { method: 'POST' });
      qc.invalidateQueries({ queryKey: ['watches', watchId] });
      qc.invalidateQueries({ queryKey: ['watches'] });
    } catch {
      // 실패해도 조용히 — 다음 주기에 자동 실행됨
    }
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-lg font-semibold">감시 중 {watches.length}건</h1>
        </div>
        <Link
          href="/watches/new"
          className="text-sm px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
          + 새 감시 만들기
        </Link>
      </div>

      {/* 감시 카드 그리드 */}
      {isLoading ? (
        <div className="text-sm text-gray-500">불러오는 중…</div>
      ) : watches.length === 0 ? (
        <div className="rounded-xl border border-dashed p-12 text-center text-gray-500">
          <p className="text-base font-medium">아직 감시 중인 여행이 없습니다</p>
          <p className="text-sm mt-1 opacity-70">위 버튼으로 첫 번째 감시를 만들어보세요</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
          {watches.map((w) => (
            <WatchCard
              key={w.id}
              watch={w}
              onRunNow={() => handleRunNow(w.id)}
            />
          ))}
        </div>
      )}

      {/* 최근 알림 */}
      <RecentAlerts />
    </div>
  );
}
