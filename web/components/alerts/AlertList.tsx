'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useMarkRead } from '@/hooks/useAlerts';
import { formatKST, formatRelative } from '@/lib/format';
import type { AlertOut } from '@/lib/types';

const SEVERITY_BAR: Record<string, string> = {
  info: 'bg-gray-400',
  good: 'bg-blue-500',
  great: 'bg-orange-400',
};

const SEVERITY_LABEL: Record<string, string> = {
  info: 'ℹ️',
  good: '✅',
  great: '🔥',
};

interface AlertListProps {
  alerts: AlertOut[];
  watchNames?: Record<string, string>;
}

export default function AlertList({ alerts, watchNames = {} }: AlertListProps) {
  const router = useRouter();
  const markRead = useMarkRead();

  if (alerts.length === 0) {
    return (
      <div className="text-center py-16 text-gray-500">알림이 없습니다</div>
    );
  }

  return (
    <div className="divide-y rounded-xl border">
      {alerts.map((alert) => {
        const isUnread = alert.read_at === null;
        return (
          <div
            key={alert.id}
            className="flex items-stretch cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-900"
            onClick={() => {
              if (isUnread) markRead.mutate(alert.id);
              router.push(`/watches/${alert.watch_id}`);
            }}
          >
            {/* 심각도 색 바 */}
            <div
              className={`w-1 shrink-0 rounded-l-xl ${SEVERITY_BAR[alert.severity]}`}
            />

            <div className="flex-1 px-4 py-3">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <span className="mr-2">{SEVERITY_LABEL[alert.severity]}</span>
                  <span className={isUnread ? 'font-bold' : 'font-normal'}>
                    {alert.title}
                  </span>
                </div>
                <span className="text-xs text-gray-400 shrink-0" title={formatKST(alert.created_at)}>
                  {formatRelative(alert.created_at)}
                </span>
              </div>
              <p className="text-sm text-gray-600 dark:text-gray-400 mt-0.5 line-clamp-2">
                {alert.body}
              </p>
              {watchNames[alert.watch_id] && (
                <Link
                  href={`/watches/${alert.watch_id}`}
                  onClick={(e) => e.stopPropagation()}
                  className="text-xs text-blue-500 hover:underline mt-1 inline-block"
                >
                  {watchNames[alert.watch_id]}
                </Link>
              )}
            </div>

            {/* 읽음 버튼 */}
            {isUnread && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  markRead.mutate(alert.id);
                }}
                className="px-3 text-xs text-gray-400 hover:text-gray-700 self-center"
              >
                읽음
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}
