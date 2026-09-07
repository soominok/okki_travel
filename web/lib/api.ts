/**
 * 백엔드 호출은 반드시 서버 사이드에서만.
 * APP_API_TOKEN 은 절대 클라이언트 번들에 들어가면 안 된다.
 */
// ★ 이 import 가 안전망이다. 클라이언트 컴포넌트가 이 파일을 import 하면
//   빌드 타임에 에러가 난다. 없으면 실수로 import 한 순간 APP_API_TOKEN 이
//   조용히 번들에 박힌다 — 로컬에선 아무 증상이 없다.
import "server-only";

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
