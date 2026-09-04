'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import WorkerDot from './WorkerDot';

const links = [
  { href: '/', label: '대시보드' },
  { href: '/alerts', label: '알림함' },
  { href: '/settings', label: '설정' },
] as const;

export default function Nav() {
  const pathname = usePathname();
  return (
    <nav className="flex items-center justify-between border-b px-4 py-3 text-sm">
      <span className="font-semibold tracking-tight">TripPick</span>
      <div className="flex gap-6">
        {links.map((l) => (
          <Link
            key={l.href}
            href={l.href}
            className={
              pathname === l.href
                ? 'font-semibold'
                : 'opacity-50 hover:opacity-80 transition-opacity'
            }
          >
            {l.label}
          </Link>
        ))}
      </div>
      <WorkerDot />
    </nav>
  );
}
