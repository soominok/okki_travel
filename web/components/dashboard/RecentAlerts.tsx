'use client';

import Link from 'next/link';
import { useAlerts } from '@/hooks/useAlerts';
import { formatRelative } from '@/lib/format';
import type { Severity } from '@/lib/types';

const SEVERITY_COLOR: Record<Severity, string> = {
  info: 'text-gray-500',
  good: 'text-blue-600',
  great: 'text-orange-500',
};

const SEVERITY_ICON: Record<Severity, string> = {
  info: 'ℹ️',
  good: '✅',
  great: '🔥',
};

export default function RecentAlerts() {
  const { data: alerts = [], isLoading } = useAlerts({ limit: 3 });

  if (isLoading) return <div className="text-sm text-gray-500">불러오는 중…</div>;
  if (alerts.length === 0) return null;

  return (
    <section>
      <h2 className="text-sm font-semibold mb-2 text-gray-700 dark:text-gray-300">
        최근 알림
      </h2>
      <div className="divide-y rounded-xl border">
        {alerts.map((a) => (
          <Link
            key={a.id}
            href={`/watches/${a.watch_id}`}
            className="flex items-start gap-3 px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-900"
          >
            <span className={`${SEVERITY_COLOR[a.severity]} font-semibold text-sm shrink-0`}>
              {SEVERITY_ICON[a.severity]} {a.severity}
            </span>
            <span className="text-sm flex-1 line-clamp-1">{a.title}</span>
            <span className="text-xs text-gray-400 shrink-0">
              {formatRelative(a.created_at)}
            </span>
          </Link>
        ))}
      </div>
    </section>
  );
}
