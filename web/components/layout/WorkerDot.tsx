'use client';

import { useWorkerStatus } from '@/hooks/useWorkerStatus';

export default function WorkerDot() {
  const { data, isError } = useWorkerStatus();

  if (isError || !data) {
    return (
      <span className="flex items-center gap-1 text-sm text-red-500">
        <span className="inline-block h-2 w-2 rounded-full bg-red-500" />
        연결 실패
      </span>
    );
  }

  const ok = data.status === 'ok';
  return (
    <span className="flex items-center gap-1 text-sm">
      <span
        className={`inline-block h-2 w-2 rounded-full ${
          ok ? 'bg-green-500' : 'bg-orange-400'
        }`}
      />
      <span className="opacity-70">{ok ? '정상' : '일부 오류'}</span>
    </span>
  );
}
