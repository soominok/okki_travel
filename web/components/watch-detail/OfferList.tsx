'use client';

import { useState } from 'react';
import { formatKRW, formatKST, formatRelative } from '@/lib/format';
import type { OfferOut } from '@/lib/types';

const SOURCE_COLORS: Record<string, string> = {
  travelpayouts: 'bg-blue-100 text-blue-800',
  brightdata: 'bg-purple-100 text-purple-800',
};

interface OfferListProps {
  offers: OfferOut[];
}

export default function OfferList({ offers }: OfferListProps) {
  const [sort, setSort] = useState<'price' | 'date'>('price');

  const sorted = [...offers].sort((a, b) => {
    if (sort === 'price') return a.price_krw - b.price_krw;
    if (!a.depart_date || !b.depart_date) return 0;
    return a.depart_date.localeCompare(b.depart_date);
  });

  if (offers.length === 0) {
    return (
      <p className="text-sm text-gray-500">
        아직 데이터를 못 찾았습니다 (0칸)
      </p>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-medium">
          현재 오퍼 ({offers.length}건)
        </span>
        <select
          value={sort}
          onChange={(e) => setSort(e.target.value as 'price' | 'date')}
          className="text-xs border rounded px-2 py-1"
        >
          <option value="price">가격순</option>
          <option value="date">날짜순</option>
        </select>
      </div>

      <div className="divide-y rounded-xl border">
        {sorted.map((offer) => (
          <div key={offer.id} className="px-4 py-3">
            <div className="flex items-start justify-between">
              <div>
                <span className="text-lg font-bold tabular-nums">
                  {formatKRW(offer.price_krw)}
                </span>
                {offer.depart_date && (
                  <span className="ml-2 text-sm text-gray-600">
                    {offer.depart_date}
                    {offer.return_date && ` ~ ${offer.return_date}`}
                  </span>
                )}
                {offer.airline && (
                  <span className="ml-2 text-sm text-gray-500">
                    {offer.airline}
                  </span>
                )}
              </div>
              {offer.deep_link && (
                <a
                  href={offer.deep_link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-blue-600 border border-blue-300 px-2 py-1 rounded hover:bg-blue-50"
                >
                  예약하기
                </a>
              )}
            </div>
            <div className="flex items-center gap-3 mt-1">
              {offer.freshness === 'live' ? (
                <span className="text-xs text-green-600">
                  ● {formatRelative(offer.collected_at)} 실측
                </span>
              ) : (
                <span className="text-xs text-gray-400">
                  ○ 캐시 (최대 7일 전)
                </span>
              )}
              <span
                className={`text-xs px-1.5 py-0.5 rounded ${
                  SOURCE_COLORS[offer.source] ?? 'bg-gray-100 text-gray-600'
                }`}
              >
                {offer.source}
              </span>
            </div>
            {offer.deep_links && (
              <div className="flex flex-wrap gap-2 mt-2">
                {[
                  { key: 'skyscanner', label: '스카이스캐너' },
                  { key: 'google', label: '구글항공' },
                  { key: 'naver', label: '네이버항공' },
                  { key: 'tripdotcom', label: '트립닷컴' },
                ].map(({ key, label }) =>
                  offer.deep_links?.[key] ? (
                    <a
                      key={key}
                      href={offer.deep_links[key]}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs border rounded px-2 py-1 text-gray-600 hover:bg-gray-50"
                    >
                      {label}에서 검색
                    </a>
                  ) : null
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
