'use client';

import { useState } from 'react';
import type { WatchRule } from '@/lib/types';

interface StepRulesProps {
  onSave: (rules: WatchRule[], intervalHours: number) => void;
  saving?: boolean;
}

const INTERVAL_OPTIONS = [
  { value: 1, label: '1시간' },
  { value: 3, label: '3시간' },
  { value: 6, label: '6시간 (기본)' },
  { value: 12, label: '12시간' },
  { value: 24, label: '하루' },
];

export default function StepRules({ onSave, saving = false }: StepRulesProps) {
  const [targetPrice, setTargetPrice] = useState('');
  const [useDropPct, setUseDropPct] = useState(true);
  const [dropPct, setDropPct] = useState(20);
  const [useAllTimeLow, setUseAllTimeLow] = useState(true);
  const [useNewBest, setUseNewBest] = useState(false);
  const [intervalHours, setIntervalHours] = useState(6);

  const rulesPerDay = Math.round(24 / intervalHours);

  function buildRules(): WatchRule[] {
    const rules: WatchRule[] = [];
    const tp = parseInt(targetPrice.replace(/,/g, ''), 10);
    if (!isNaN(tp) && tp > 0) {
      rules.push({ id: 'threshold', type: 'threshold', price_krw: tp });
    }
    if (useDropPct) {
      rules.push({ id: 'drop_pct', type: 'drop_pct', pct: dropPct });
    }
    if (useAllTimeLow) {
      rules.push({ id: 'all_time_low', type: 'all_time_low' });
    }
    if (useNewBest) {
      rules.push({ id: 'new_best', type: 'new_best' });
    }
    return rules;
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">알림 규칙 설정</h2>

      {/* 목표가 */}
      <div>
        <label className="text-sm font-medium">
          목표가 (선택) — 이 가격 이하가 되면 알림
        </label>
        <div className="relative mt-1">
          <span className="absolute left-3 top-2 text-sm text-gray-500">₩</span>
          <input
            type="text"
            inputMode="numeric"
            placeholder="250,000"
            value={targetPrice}
            onChange={(e) =>
              setTargetPrice(e.target.value.replace(/[^\d,]/g, ''))
            }
            className="w-full rounded-lg border pl-7 pr-3 py-2 text-sm"
          />
        </div>
      </div>

      {/* 규칙 체크박스들 */}
      <div className="space-y-3">
        <label className="flex items-start gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={useDropPct}
            onChange={(e) => setUseDropPct(e.target.checked)}
            className="mt-0.5"
          />
          <div>
            <span className="text-sm font-medium">
              평소보다{' '}
              <input
                type="number"
                min={5}
                max={50}
                value={dropPct}
                onChange={(e) => setDropPct(+e.target.value)}
                className="w-12 border rounded px-1 py-0.5 text-sm text-center"
              />
              % 이상 떨어지면 알림
            </span>
            <p className="text-xs text-gray-500 mt-0.5">
              14일 중앙값 대비 하락 시 발송
            </p>
          </div>
        </label>

        <label className="flex items-start gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={useAllTimeLow}
            onChange={(e) => setUseAllTimeLow(e.target.checked)}
            className="mt-0.5"
          />
          <div>
            <span className="text-sm font-medium">역대 최저가를 찍으면 알림</span>
            <p className="text-xs text-gray-500 mt-0.5">
              수집 이후 최저 기록 경신 시 발송
            </p>
          </div>
        </label>

        <label className="flex items-start gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={useNewBest}
            onChange={(e) => setUseNewBest(e.target.checked)}
            className="mt-0.5"
          />
          <div>
            <span className="text-sm font-medium">
              최저가가 갱신될 때마다 알림{' '}
              <span className="text-orange-500 text-xs">⚠ 시끄러울 수 있음</span>
            </span>
            <p className="text-xs text-gray-500 mt-0.5">
              매 수집마다 더 싼 가격이 나오면 발송
            </p>
          </div>
        </label>
      </div>

      {/* 확인 주기 */}
      <div>
        <label className="text-sm font-medium">확인 주기</label>
        <select
          value={intervalHours}
          onChange={(e) => setIntervalHours(+e.target.value)}
          className="mt-1 w-full rounded-lg border px-3 py-2 text-sm"
        >
          {INTERVAL_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>

      {/* 미리보기 */}
      <div className="rounded-lg bg-gray-50 dark:bg-gray-900 p-4 text-sm text-gray-600 dark:text-gray-400">
        이 조건이면 하루 약 <strong>{rulesPerDay}회</strong> 조회
      </div>

      <button
        onClick={() => onSave(buildRules(), intervalHours)}
        disabled={saving}
        className="w-full py-3 rounded-xl bg-blue-600 text-white font-semibold disabled:opacity-40"
      >
        {saving ? '감시 등록 중…' : '감시 시작 →'}
      </button>
    </div>
  );
}
