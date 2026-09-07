// 서버 사이드 호출은 lib/api.ts (server-only) 사용.
// 이 파일은 클라이언트 컴포넌트·훅 전용.
// NEXT_PUBLIC_API_TOKEN이 클라이언트 번들에 포함되는 것은 의도된 설계 (개인 도구).

const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
const TOKEN = process.env.NEXT_PUBLIC_API_TOKEN ?? '';

export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${TOKEN}`,
      ...init?.headers,
    },
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}
