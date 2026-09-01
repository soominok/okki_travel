/**
 * 백엔드 호출은 반드시 서버 사이드에서만.
 * APP_API_TOKEN 은 절대 클라이언트 번들에 들어가면 안 된다.
 */
const API_BASE = process.env.API_BASE_URL ?? "http://api:8000";
const API_TOKEN = process.env.APP_API_TOKEN ?? "";

export async function serverFetch(path: string, init?: RequestInit) {
  return fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...(init?.headers ?? {}),
      Authorization: `Bearer ${API_TOKEN}`,
      "Content-Type": "application/json",
    },
    cache: "no-store",
  });
}
