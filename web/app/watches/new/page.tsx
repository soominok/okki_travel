'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import WizardLayout from '@/components/watch-form/WizardLayout';
import StepType from '@/components/watch-form/StepType';
import StepCondition, {
  type FlightCondition,
} from '@/components/watch-form/StepCondition';
import StepRules from '@/components/watch-form/StepRules';
import { useCreateWatch } from '@/hooks/useWatches';
import { apiFetch } from '@/lib/client';
import type { WatchKind, WatchRule } from '@/lib/types';

export default function NewWatchPage() {
  const router = useRouter();
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [watchType, setWatchType] = useState<WatchKind | null>(null);
  const [condition, setCondition] = useState<FlightCondition | null>(null);

  const createWatch = useCreateWatch();
  const [isRedirecting, setIsRedirecting] = useState(false);

  async function handleSave(rules: WatchRule[], intervalHours: number) {
    if (!condition || !watchType) return;

    const watch = await createWatch.mutateAsync({
      kind: watchType,
      title: condition.name,
      params: {
        kind: 'flight' as const,
        origin: condition.origin,
        destination: condition.destination,
        depart_from: condition.date_from,
        depart_to: condition.date_to,
        nights_min: condition.nights_from ?? null,
        nights_max: condition.nights_to ?? null,
        weekday_preference: condition.weekdays.map(String),
        adults: condition.adults,
        direct_only: condition.direct_only,
      },
      rules,
      interval_min: intervalHours * 60,
    });

    setIsRedirecting(true);
    // 즉시 1회 수집 (React 상태 업데이트 비동기성 우회 — apiFetch 직접 호출)
    await apiFetch(`/api/watches/${watch.id}/run`, { method: 'POST' }).catch(() => {});
    router.push(`/watches/${watch.id}`);
  }

  return (
    <WizardLayout
      step={step}
      onBack={step > 1 ? () => setStep((s) => (s - 1) as 1 | 2 | 3) : undefined}
    >
      {step === 1 && (
        <StepType
          onSelect={(type) => {
            setWatchType(type);
            setStep(2);
          }}
        />
      )}
      {step === 2 && (
        <StepCondition
          initial={condition ?? undefined}
          onNext={(cond) => {
            setCondition(cond);
            setStep(3);
          }}
        />
      )}
      {step === 3 && (
        <StepRules
          onSave={handleSave}
          saving={createWatch.isPending || isRedirecting}
        />
      )}
    </WizardLayout>
  );
}
