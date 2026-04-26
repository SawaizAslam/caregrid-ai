import type {
  Contradiction,
  HealthResponse,
  HospitalDetail,
  SearchResponse,
  SpecialtyGapsResponse,
  StateDesert,
} from "./types";

const API_URL = (import.meta.env.VITE_API_URL || "").replace(/\/+$/, "");

if (!API_URL) {
  // eslint-disable-next-line no-console
  console.warn(
    "[CareGrid AI] VITE_API_URL is not set. Set it in your .env file (see .env.example).",
  );
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  if (!API_URL) {
    throw new Error("VITE_API_URL is not configured");
  }
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}${text ? ` — ${text}` : ""}`);
  }
  return res.json() as Promise<T>;
}

export function getHealth() {
  return request<HealthResponse>("/health");
}

export function search(query: string, top_k = 10) {
  return request<SearchResponse>("/search", {
    method: "POST",
    body: JSON.stringify({ query, top_k }),
  });
}

export function getHospital(id: number) {
  return request<HospitalDetail>(`/hospitals/${id}`);
}

export async function getDeserts(top_n = 36) {
  const res = await request<{ states: StateDesert[] }>(
    `/stats/deserts?top_n=${top_n}`,
  );
  return res.states ?? [];
}

export function getSpecialtyGaps() {
  return request<SpecialtyGapsResponse>("/stats/specialty-gaps");
}

export async function getContradictions(limit = 50) {
  const res = await request<{ flagged: Contradiction[] }>(
    `/stats/contradictions?limit=${limit}`,
  );
  return res.flagged ?? [];
}

export { API_URL };
