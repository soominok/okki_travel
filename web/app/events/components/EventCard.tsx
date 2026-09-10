import type { EventOut } from '@/lib/types';

const SOURCE_LABELS: Record<string, string> = {
  airbusan: '에어부산',
  tway: '티웨이항공',
  jejuair: '제주항공',
  koreanair: '대한항공',
  flightdeal: 'flightdeal.kr',
};

function formatDate(d: string | null) {
  if (!d) return null;
  return d.replace(/-/g, '.').slice(2);  // "26.09.01"
}

export default function EventCard({ event }: { event: EventOut }) {
  const label = SOURCE_LABELS[event.source] ?? event.source;
  const period =
    event.valid_from && event.valid_to
      ? `${formatDate(event.valid_from)} ~ ${formatDate(event.valid_to)}`
      : event.valid_to
      ? `~ ${formatDate(event.valid_to)}`
      : null;

  return (
    <div className="rounded-xl border p-4 space-y-2 hover:shadow-sm transition-shadow">
      <div className="flex items-center gap-2">
        <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-blue-100 text-blue-800">
          {label}
        </span>
        {period && (
          <span className="text-xs text-gray-500">{period}</span>
        )}
      </div>
      <p className="text-sm font-medium leading-snug">{event.title}</p>
      {event.discount_info && (
        <p className="text-xs text-green-700">{event.discount_info}</p>
      )}
      <a
        href={event.url}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-block text-xs text-blue-600 hover:underline"
      >
        자세히 보기 →
      </a>
    </div>
  );
}
