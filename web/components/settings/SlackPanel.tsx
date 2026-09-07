'use client';

import { useSlackTest } from '@/hooks/useSettings';

export default function SlackPanel() {
  const slackTest = useSlackTest();

  return (
    <section className="rounded-xl border p-5 space-y-4">
      <h2 className="font-semibold">슬랙 알림 채널</h2>

      <div>
        <p className="text-sm text-gray-600 dark:text-gray-400">
          Webhook URL은 백엔드 환경변수 <code className="text-xs bg-gray-100 dark:bg-gray-800 px-1 py-0.5 rounded">SLACK_WEBHOOK_URL</code> 에서 관리됩니다.
        </p>
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={() => slackTest.mutate()}
          disabled={slackTest.isPending}
          className="text-sm px-4 py-2 border rounded-lg hover:bg-gray-50 disabled:opacity-40"
        >
          {slackTest.isPending ? '발송 중…' : '테스트 발송'}
        </button>

        {slackTest.data && (
          <span
            className={`text-sm ${
              slackTest.data.status === 'sent'
                ? 'text-green-600'
                : slackTest.data.status === 'deferred'
                  ? 'text-orange-500'
                  : 'text-red-500'
            }`}
          >
            {slackTest.data.status === 'sent'
              ? '✅ 발송 성공'
              : slackTest.data.status === 'deferred'
                ? '⏸ 방해금지 시간 (큐 대기)'
                : '❌ 발송 실패'}
          </span>
        )}

        {slackTest.isError && (
          <span className="text-sm text-red-500">
            ❌ {(slackTest.error as Error).message}
          </span>
        )}
      </div>
    </section>
  );
}
