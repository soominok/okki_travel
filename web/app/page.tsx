import { serverFetch } from "@/lib/api";

async function getHealth() {
  try {
    const res = await serverFetch("/healthz");
    return await res.json();
  } catch {
    return { status: "unreachable", db: "unknown" };
  }
}

export default async function Home() {
  const health = await getHealth();
  const ok = health.status === "ok";

  return (
    <main className="min-h-dvh flex items-center justify-center p-8">
      <div className="w-full max-w-md rounded-xl border p-6">
        <h1 className="text-xl font-semibold">TripPick</h1>
        <p className="mt-1 text-sm opacity-70">개인용 여행 가격 감시</p>

        <div className="mt-6 flex items-center gap-2">
          <span
            className={`inline-block h-2.5 w-2.5 rounded-full ${
              ok ? "bg-green-500" : "bg-red-500"
            }`}
          />
          <span className="text-sm">
            백엔드 {ok ? "연결됨" : "연결 실패"} · DB {health.db}
          </span>
        </div>

        <p className="mt-6 text-xs opacity-60">
          Plan 1(기반) 완료. 다음은 Plan 2(소스 계층).
        </p>
      </div>
    </main>
  );
}
