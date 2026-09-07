'use client';

export default function BudgetBar() {
  // Bright Data 예산 API 구현 전 — 플레이스홀더 UI
  return (
    <section className="rounded-xl border p-5 space-y-3">
      <h2 className="font-semibold">Bright Data 크레딧</h2>
      <p className="text-sm text-gray-500">
        예산 정보 API가 구현되면 이곳에 크레딧 진행 바가 표시됩니다.
      </p>
      <div className="h-2 rounded-full bg-gray-200 dark:bg-gray-700">
        <div className="h-full w-1/3 rounded-full bg-blue-500" />
      </div>
      <p className="text-xs text-gray-400">
        현재 사용량을 확인하려면 Bright Data 대시보드를 방문하세요.
      </p>
    </section>
  );
}
