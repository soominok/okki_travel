'use client';

import { useState } from 'react';
import { formatKST } from '@/lib/format';
import type { WorkerRunOut } from '@/lib/types';

interface RunLogProps {
  runs: WorkerRunOut[];
}

const STATUS_STYLE: Record<string, string> = {
  ok: 'text-green-600',
  partial: 'text-orange-500',
  failed: 'text-red-500',
};

export default function RunLog({ runs }: RunLogProps) {
  const [open, setOpen] = useState(false);

  const ok = runs.filter((r) => r.status === 'ok').length;
  const partial = runs.filter((r) => r.status === 'partial').length;
  const failed = runs.filter((r) => r.status === 'failed').length;

  return (
    <div>
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900"
      >
        <span>{open ? '▾' : '▸'} 실행 로그</span>
        <span className="text-xs">
          ok {ok} · partial {partial} · failed {failed}
        </span>
      </button>

      {open && (
        <div className="mt-3 divide-y rounded-xl border text-sm max-h-64 overflow-y-auto">
          {runs.slice(0, 50).map((run) => (
            <div key={run.id} className="flex items-start gap-3 px-4 py-2">
              <span className={`font-semibold shrink-0 ${STATUS_STYLE[run.status]}`}>
                {run.status}
              </span>
              <span className="text-gray-500 shrink-0 text-xs">
                {formatKST(run.started_at)}
              </span>
              <span className="text-gray-500 text-xs">
                {run.duration_ms != null
                  ? `${(run.duration_ms / 1000).toFixed(1)}s`
                  : '—'}
              </span>
              {run.error && (
                <span className="text-red-500 text-xs truncate">{run.error}</span>
              )}
            </div>
          ))}
          {runs.length === 0 && (
            <div className="px-4 py-3 text-gray-500">아직 실행 기록이 없습니다</div>
          )}
        </div>
      )}
    </div>
  );
}
