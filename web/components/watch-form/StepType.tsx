'use client';

import type { WatchKind } from '@/lib/types';

interface StepTypeProps {
  onSelect: (type: WatchKind) => void;
}

export default function StepType({ onSelect }: StepTypeProps) {
  return (
    <div>
      <h2 className="text-xl font-semibold mb-6">무엇을 감시할까요?</h2>
      <div className="grid grid-cols-2 gap-4">
        <button
          onClick={() => onSelect('flight')}
          className="flex flex-col items-center gap-3 p-8 rounded-xl border-2 hover:border-blue-500 hover:bg-blue-50 dark:hover:bg-blue-950 transition-colors"
        >
          <span className="text-4xl">✈️</span>
          <span className="font-semibold">항공권</span>
        </button>
        <button
          disabled
          className="flex flex-col items-center gap-3 p-8 rounded-xl border-2 opacity-40 cursor-not-allowed"
          title="Phase 2에서 지원 예정"
        >
          <span className="text-4xl">🏨</span>
          <span className="font-semibold">숙소</span>
          <span className="text-xs text-gray-400">준비 중</span>
        </button>
      </div>
    </div>
  );
}
