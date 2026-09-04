'use client';

import { useWorkerStatus } from '@/hooks/useWorkerStatus';

const KNOWN_SOURCES = [
  'travelpayouts',
  'brightdata',
  'hotellook',
  'tourapi',
] as const;

export default function SourceStatus() {
  const { data: health, isLoading } = useWorkerStatus();

  return (
    <section className="rounded-xl border p-5 space-y-3">
      <h2 className="font-semibold">소스 상태</h2>

      {isLoading && (
        <p className="text-sm text-gray-500">불러오는 중…</p>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-xs text-gray-500 border-b">
              <th className="text-left py-2 pr-4">소스</th>
              <th className="text-left py-2 pr-4">상태</th>
              <th className="text-left py-2">비고</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {KNOWN_SOURCES.map((src) => (
              <tr key={src}>
                <td className="py-2 pr-4 font-mono text-xs">{src}</td>
                <td className="py-2 pr-4">
                  <span className="flex items-center gap-1">
                    <span className="inline-block w-2 h-2 rounded-full bg-gray-400" />
                    <span className="text-gray-500">확인 중</span>
                  </span>
                </td>
                <td className="py-2 text-gray-400 text-xs">—</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-xs text-gray-400">
        소스별 상세 상태는 백엔드 소스 헬스 엔드포인트 구현 후 표시됩니다.
        현재 백엔드 전체 상태: {health?.status ?? '—'} · DB: {health?.db ?? '—'}
      </p>
    </section>
  );
}
