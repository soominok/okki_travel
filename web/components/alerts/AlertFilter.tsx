'use client';

import type { WatchOut } from '@/lib/types';

interface AlertFilterProps {
  unreadOnly: boolean;
  selectedWatchId: string;
  watches: WatchOut[];
  onUnreadChange: (v: boolean) => void;
  onWatchChange: (id: string) => void;
}

export default function AlertFilter({
  unreadOnly,
  selectedWatchId,
  watches,
  onUnreadChange,
  onWatchChange,
}: AlertFilterProps) {
  return (
    <div className="flex flex-wrap gap-3">
      <button
        onClick={() => onUnreadChange(!unreadOnly)}
        className={`text-sm px-3 py-1 rounded-full border ${
          unreadOnly
            ? 'bg-blue-600 text-white border-blue-600'
            : 'border-gray-300 hover:border-gray-500'
        }`}
      >
        {unreadOnly ? '미읽음만' : '전체'}
      </button>
      <select
        value={selectedWatchId}
        onChange={(e) => onWatchChange(e.target.value)}
        className="text-sm border rounded-full px-3 py-1"
      >
        <option value="">모든 감시</option>
        {watches.map((w) => (
          <option key={w.id} value={w.id}>
            {w.title}
          </option>
        ))}
      </select>
    </div>
  );
}
