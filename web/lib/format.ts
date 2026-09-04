import { formatInTimeZone } from 'date-fns-tz';
import { formatDistanceToNow } from 'date-fns';
import { ko } from 'date-fns/locale';

const KST = 'Asia/Seoul';

export function formatKRW(amount: number): string {
  return `₩${amount.toLocaleString('ko-KR')}`;
}

export function formatKST(iso: string, fmt = 'yyyy-MM-dd HH:mm'): string {
  return formatInTimeZone(new Date(iso), KST, fmt);
}

export function formatRelative(iso: string): string {
  return formatDistanceToNow(new Date(iso), { addSuffix: true, locale: ko });
}

export function formatPriceDelta(prev: number, curr: number): {
  text: string;
  direction: 'up' | 'down' | 'flat';
} {
  const delta = curr - prev;
  if (delta === 0) return { text: '변동 없음', direction: 'flat' };
  const pct = Math.abs((delta / prev) * 100).toFixed(1);
  const sign = delta < 0 ? '▼' : '▲';
  return {
    text: `${sign} ${formatKRW(Math.abs(delta))} (${pct}%)`,
    direction: delta < 0 ? 'down' : 'up',
  };
}
