'use client';

interface WizardLayoutProps {
  step: 1 | 2 | 3;
  onBack?: () => void;
  children: React.ReactNode;
}

const STEPS = ['유형 선택', '조건 입력', '알림 규칙'];

export default function WizardLayout({ step, onBack, children }: WizardLayoutProps) {
  return (
    <div className="mx-auto max-w-xl px-4 py-8">
      {/* 스텝 인디케이터 */}
      <div className="flex items-center gap-2 mb-8">
        {STEPS.map((label, i) => {
          const n = (i + 1) as 1 | 2 | 3;
          const active = n === step;
          const done = n < step;
          return (
            <div key={n} className="flex items-center gap-2">
              <div
                className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-semibold
                  ${done ? 'bg-blue-600 text-white' : active ? 'bg-blue-600 text-white' : 'bg-gray-200 dark:bg-gray-700 text-gray-500'}`}
              >
                {done ? '✓' : n}
              </div>
              <span
                className={`text-sm ${active ? 'font-semibold' : 'text-gray-400'}`}
              >
                {label}
              </span>
              {i < STEPS.length - 1 && (
                <div className="w-8 h-px bg-gray-200 dark:bg-gray-700" />
              )}
            </div>
          );
        })}
      </div>

      {/* 뒤로 가기 */}
      {onBack && (
        <button
          onClick={onBack}
          className="text-sm text-gray-500 hover:text-gray-800 mb-4"
        >
          ← 이전
        </button>
      )}

      {children}
    </div>
  );
}
