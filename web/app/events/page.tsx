'use client';

import { useState } from 'react';
import EventCard from './components/EventCard';
import { useEvents } from '@/hooks/useEvents';

const SOURCES = [
  { key: undefined,       label: '전체' },
  { key: 'airbusan',     label: '에어부산' },
  { key: 'tway',         label: '티웨이항공' },
  { key: 'jejuair',      label: '제주항공' },
  { key: 'koreanair',    label: '대한항공' },
  { key: 'flightdeal',   label: 'flightdeal.kr' },
] as const;

export default function EventsPage() {
  const [activeSource, setActiveSource] = useState<string | undefined>(undefined);
  const { data: events = [], isLoading } = useEvents(activeSource);

  return (
    <div className="mx-auto max-w-3xl px-4 py-6 space-y-6">
      <div>
        <h1 className="text-xl font-bold">항공사 특가 이벤트</h1>
        <p className="text-sm text-gray-500 mt-1">
          항공사 공식 이벤트 페이지에서 수집한 특가 정보입니다.
        </p>
      </div>

      {/* 필터 탭 */}
      <div className="flex flex-wrap gap-2">
        {SOURCES.map(({ key, label }) => (
          <button
            key={key ?? 'all'}
            onClick={() => setActiveSource(key)}
            className={`text-sm px-3 py-1 rounded-full border transition-colors ${
              activeSource === key
                ? 'bg-gray-900 text-white border-gray-900 dark:bg-white dark:text-gray-900'
                : 'border-gray-300 text-gray-600 hover:border-gray-500'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* 이벤트 목록 */}
      {isLoading ? (
        <p className="text-sm text-gray-500">불러오는 중…</p>
      ) : events.length === 0 ? (
        <p className="text-sm text-gray-500">
          이벤트가 없습니다. Worker가 6시간마다 수집합니다.
        </p>
      ) : (
        <div className="grid gap-4">
          {events.map((event) => (
            <EventCard key={event.id} event={event} />
          ))}
        </div>
      )}
    </div>
  );
}
