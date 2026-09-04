'use client';

import { useState } from 'react';
import { useAlerts } from '@/hooks/useAlerts';
import { useWatches } from '@/hooks/useWatches';
import AlertFilter from '@/components/alerts/AlertFilter';
import AlertList from '@/components/alerts/AlertList';

export default function AlertsPage() {
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [watchId, setWatchId] = useState('');

  const { data: alerts = [], isLoading } = useAlerts({
    unread: unreadOnly || undefined,
    watchId: watchId || undefined,
  });
  const { data: watches = [] } = useWatches();

  const watchNames = Object.fromEntries(watches.map((w) => [w.id, w.name]));

  return (
    <div className="mx-auto max-w-3xl px-4 py-6">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-lg font-semibold">알림함</h1>
        <span className="text-sm text-gray-500">
          {alerts.filter((a) => !a.read_at).length}건 미읽음
        </span>
      </div>

      <div className="mb-4">
        <AlertFilter
          unreadOnly={unreadOnly}
          selectedWatchId={watchId}
          watches={watches}
          onUnreadChange={setUnreadOnly}
          onWatchChange={setWatchId}
        />
      </div>

      {isLoading ? (
        <div className="text-sm text-gray-500">불러오는 중…</div>
      ) : (
        <AlertList alerts={alerts} watchNames={watchNames} />
      )}
    </div>
  );
}
