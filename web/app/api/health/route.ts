import { NextResponse } from "next/server";

const API_BASE = process.env.API_BASE_URL ?? "http://api:8000";

export async function GET() {
  try {
    // /healthz 는 무인증이므로 토큰이 필요 없다
    const res = await fetch(`${API_BASE}/healthz`, { cache: "no-store" });
    return NextResponse.json(await res.json(), { status: res.status });
  } catch (e) {
    return NextResponse.json(
      { status: "unreachable", db: "unknown", error: String(e) },
      { status: 503 },
    );
  }
}
