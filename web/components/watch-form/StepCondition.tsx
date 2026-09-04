'use client';

import { useState } from 'react';

// 상위 50 공항 하드코딩 (GET /api/meta/airports 미구현 fallback)
const TOP_AIRPORTS = [
  { code: 'ICN', name: '인천국제공항' },
  { code: 'GMP', name: '김포공항' },
  { code: 'NRT', name: '도쿄 나리타' },
  { code: 'HND', name: '도쿄 하네다' },
  { code: 'FUK', name: '후쿠오카' },
  { code: 'OKA', name: '오키나와 나하' },
  { code: 'CTS', name: '삿포로 치토세' },
  { code: 'KIX', name: '오사카 간사이' },
  { code: 'BKK', name: '방콕 수완나품' },
  { code: 'DMK', name: '방콕 돈므앙' },
  { code: 'SIN', name: '싱가포르 창이' },
  { code: 'HKG', name: '홍콩' },
  { code: 'TPE', name: '타이베이 타오위안' },
  { code: 'MNL', name: '마닐라' },
  { code: 'CEB', name: '세부' },
  { code: 'DPS', name: '발리 덴파사르' },
  { code: 'CGK', name: '자카르타 수카르노' },
  { code: 'PVG', name: '상하이 푸동' },
  { code: 'PEK', name: '베이징 수도' },
  { code: 'CAN', name: '광저우' },
  { code: 'LAX', name: '로스앤젤레스' },
  { code: 'JFK', name: '뉴욕 JFK' },
  { code: 'LHR', name: '런던 히스로' },
  { code: 'CDG', name: '파리 샤를드골' },
  { code: 'FRA', name: '프랑크푸르트' },
];

const WEEKDAYS = ['월', '화', '수', '목', '금', '토', '일'];

export interface FlightCondition {
  name: string;
  origin: string;
  destination: string;
  date_from: string;
  date_to: string;
  nights_from: number;
  nights_to: number;
  weekdays: number[];
  adults: number;
  direct_only: boolean;
}

interface StepConditionProps {
  initial?: Partial<FlightCondition>;
  onNext: (cond: FlightCondition) => void;
}

function AirportSelect({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  const [q, setQ] = useState('');
  const filtered = q
    ? TOP_AIRPORTS.filter(
        (a) =>
          a.code.toLowerCase().includes(q.toLowerCase()) ||
          a.name.includes(q),
      )
    : TOP_AIRPORTS.slice(0, 8);

  return (
    <div>
      <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
        {label}
      </label>
      <input
        type="text"
        placeholder={value || '공항 검색 (예: 후쿠, FUK)'}
        value={q}
        onChange={(e) => setQ(e.target.value)}
        className="mt-1 w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
      />
      {q && (
        <div className="mt-1 rounded-lg border bg-white dark:bg-gray-900 shadow-lg max-h-48 overflow-y-auto">
          {filtered.map((a) => (
            <button
              key={a.code}
              type="button"
              onClick={() => {
                onChange(a.code);
                setQ('');
              }}
              className="w-full text-left px-3 py-2 text-sm hover:bg-gray-50 dark:hover:bg-gray-800"
            >
              <span className="font-mono font-semibold">{a.code}</span>{' '}
              {a.name}
            </button>
          ))}
        </div>
      )}
      {value && !q && (
        <div className="mt-1 text-sm text-blue-600 font-medium">{value}</div>
      )}
    </div>
  );
}

export default function StepCondition({ initial = {}, onNext }: StepConditionProps) {
  const [form, setForm] = useState<FlightCondition>({
    name: initial.name ?? '',
    origin: initial.origin ?? 'ICN',
    destination: initial.destination ?? '',
    date_from: initial.date_from ?? '',
    date_to: initial.date_to ?? '',
    nights_from: initial.nights_from ?? 2,
    nights_to: initial.nights_to ?? 3,
    weekdays: initial.weekdays ?? [],
    adults: initial.adults ?? 1,
    direct_only: initial.direct_only ?? false,
  });

  function toggle(field: keyof FlightCondition, value: unknown) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  function toggleWeekday(d: number) {
    setForm((f) => ({
      ...f,
      weekdays: f.weekdays.includes(d)
        ? f.weekdays.filter((x) => x !== d)
        : [...f.weekdays, d],
    }));
  }

  const canNext =
    form.name.trim() &&
    form.origin &&
    form.destination &&
    form.date_from &&
    form.date_to;

  return (
    <div className="space-y-5">
      <h2 className="text-xl font-semibold">항공권 조건 입력</h2>

      <div>
        <label className="text-sm font-medium">감시 이름</label>
        <input
          type="text"
          placeholder="예: 가을 후쿠오카"
          value={form.name}
          onChange={(e) => toggle('name', e.target.value)}
          className="mt-1 w-full rounded-lg border px-3 py-2 text-sm"
        />
      </div>

      <AirportSelect
        label="출발지"
        value={form.origin}
        onChange={(v) => toggle('origin', v)}
      />
      <AirportSelect
        label="도착지"
        value={form.destination}
        onChange={(v) => toggle('destination', v)}
      />

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="text-sm font-medium">여행 시작 날짜</label>
          <input
            type="date"
            value={form.date_from}
            onChange={(e) => toggle('date_from', e.target.value)}
            className="mt-1 w-full rounded-lg border px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="text-sm font-medium">여행 종료 날짜</label>
          <input
            type="date"
            value={form.date_to}
            onChange={(e) => toggle('date_to', e.target.value)}
            className="mt-1 w-full rounded-lg border px-3 py-2 text-sm"
          />
        </div>
      </div>

      <div>
        <label className="text-sm font-medium">
          체류 기간: {form.nights_from}~{form.nights_to}박
        </label>
        <div className="flex gap-4 mt-2">
          <div className="flex-1">
            <span className="text-xs text-gray-500">최소</span>
            <input
              type="range"
              min={1}
              max={14}
              value={form.nights_from}
              onChange={(e) =>
                toggle('nights_from', Math.min(+e.target.value, form.nights_to))
              }
              className="w-full"
            />
          </div>
          <div className="flex-1">
            <span className="text-xs text-gray-500">최대</span>
            <input
              type="range"
              min={1}
              max={14}
              value={form.nights_to}
              onChange={(e) =>
                toggle('nights_to', Math.max(+e.target.value, form.nights_from))
              }
              className="w-full"
            />
          </div>
        </div>
      </div>

      <div>
        <label className="text-sm font-medium">출발 요일 선호 (미선택 = 무관)</label>
        <div className="flex gap-2 mt-2 flex-wrap">
          {WEEKDAYS.map((label, i) => (
            <button
              key={i}
              type="button"
              onClick={() => toggleWeekday(i)}
              className={`px-3 py-1 rounded-full text-sm border ${
                form.weekdays.includes(i)
                  ? 'bg-blue-600 text-white border-blue-600'
                  : 'border-gray-300 hover:border-gray-500'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">성인</span>
          <button
            type="button"
            onClick={() => toggle('adults', Math.max(1, form.adults - 1))}
            className="w-7 h-7 rounded-full border text-center"
          >
            −
          </button>
          <span className="text-sm w-4 text-center">{form.adults}</span>
          <button
            type="button"
            onClick={() => toggle('adults', Math.min(9, form.adults + 1))}
            className="w-7 h-7 rounded-full border text-center"
          >
            +
          </button>
        </div>
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input
            type="checkbox"
            checked={form.direct_only}
            onChange={(e) => toggle('direct_only', e.target.checked)}
          />
          직항만
        </label>
      </div>

      <button
        onClick={() => canNext && onNext(form)}
        disabled={!canNext}
        className="w-full py-3 rounded-xl bg-blue-600 text-white font-semibold disabled:opacity-40"
      >
        다음 →
      </button>
    </div>
  );
}
