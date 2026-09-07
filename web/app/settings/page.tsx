'use client';

import SlackPanel from '@/components/settings/SlackPanel';
import SourceStatus from '@/components/settings/SourceStatus';
import BudgetBar from '@/components/settings/BudgetBar';
import SamplingPolicy from '@/components/settings/SamplingPolicy';

export default function SettingsPage() {
  return (
    <div className="mx-auto max-w-2xl px-4 py-6 space-y-6">
      <h1 className="text-lg font-semibold">설정</h1>
      <SlackPanel />
      <SourceStatus />
      <BudgetBar />
      <SamplingPolicy />
    </div>
  );
}
