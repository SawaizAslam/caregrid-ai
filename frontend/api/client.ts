/**
 * CareGrid AI - typed client for the FastAPI backend on Hugging Face Spaces.
 *
 * Consumed by the Lovable-generated frontend. Drop this file at
 * `src/lib/api.ts` (or wherever your project keeps shared utilities) and
 * import the helpers from there. Each helper throws on non-2xx so you can
 * catch in the calling component.
 *
 * The base URL is read from `import.meta.env.VITE_API_URL`. If that env var
 * isn't set, calls fall back to `http://localhost:8000` so `npm run dev`
 * just works while you're iterating with the local backend.
 */

const RAW_BASE = (import.meta as any).env?.VITE_API_URL ?? "http://localhost:8000";
const API_BASE = String(RAW_BASE).replace(/\/+$/, "");

// ---------------------------------------------------------------------------
// Types — keep in sync with backend/app/schemas.py + stats.py.
// ---------------------------------------------------------------------------

export type TrustBreakdownItem = {
  rule: string;
  delta: number;
  evidence: string;
};

export type ScoreComponents = {
  semantic: number;
  keyword: number;
  trust: number;
  location: number;
};

export type HospitalResult = {
  hospital_id: number;
  hospital_name: string;
  score: number;
  trust_score: number;
  explanation: string;
  location: string;
  state: string | null;
  district: string | null;
  pin_code: string | null;
  latitude: number | null;
  longitude: number | null;
  distance_km: number | null;
  matched_features: string[];
  trust_breakdown: TrustBreakdownItem[];
  score_components: ScoreComponents;
};

export type QueryUnderstood = {
  state: string | null;
  pin: string | null;
  radius_km: number | null;
  specialties: string[];
  requirements: string[];
  sort: "relevance" | "distance";
  raw_query: string;
};

export type SearchResponse = {
  results: HospitalResult[];
  query_understood: QueryUnderstood;
  total_candidates: number;
};

export type HealthResponse = {
  status: "ok" | "degraded";
  dataset_rows: number;
  faiss_loaded: boolean;
  embedding_model: string;
  index_path: string;
  pincodes_loaded: number;
};

export type HospitalDetail = {
  hospital_id: number;
  hospital_name: string;
  state: string | null;
  district: string | null;
  pin_code: string | null;
  address: string | null;
  specialties: string | null;
  equipment: string | null;
  notes: string | null;
  staff: string | null;
  phone: string | null;
  latitude: number | null;
  longitude: number | null;
  trust_score: number;
  trust_breakdown: TrustBreakdownItem[];
  specialty_tags: string[];
  equipment_tags: string[];
};

export type StateDesert = {
  state: string;
  facility_count: number;
  hospital_count: number;
  avg_trust_score: number;
  major_specialty_share: number;
  hospital_share: number;
  desert_score: number;
};

export type SpecialtyGap = {
  specialty: string;
  total_facilities: number;
  states_covered: number;
  top_states: [string, number][];
};

export type Contradiction = {
  hospital_id: number;
  hospital_name: string;
  state: string | null;
  district: string | null;
  pin_code: string | null;
  trust_score: number;
  rule: string;
  evidence: string;
};

export type Overview = {
  total: number;
  facility_types?: Record<string, number>;
  avg_trust_score?: number;
  states_represented?: number;
};

// ---------------------------------------------------------------------------
// Fetch helpers
// ---------------------------------------------------------------------------

async function request<T>(
  path: string,
  init: RequestInit = {},
  signal?: AbortSignal,
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    signal,
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...(init.headers ?? {}),
    },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`CareGrid API ${res.status} ${res.statusText}: ${text || path}`);
  }
  return (await res.json()) as T;
}

// ---------------------------------------------------------------------------
// Endpoint wrappers
// ---------------------------------------------------------------------------

export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return request("/health", {}, signal);
}

export function search(
  query: string,
  topK: number = 10,
  signal?: AbortSignal,
): Promise<SearchResponse> {
  return request(
    "/search",
    {
      method: "POST",
      body: JSON.stringify({ query, top_k: topK }),
    },
    signal,
  );
}

export function getHospital(id: number, signal?: AbortSignal): Promise<HospitalDetail> {
  return request(`/hospitals/${id}`, {}, signal);
}

export function getOverview(signal?: AbortSignal): Promise<Overview> {
  return request("/stats/overview", {}, signal);
}

export function getStateDeserts(
  topN: number = 36,
  signal?: AbortSignal,
): Promise<{ states: StateDesert[] }> {
  return request(`/stats/deserts?top_n=${topN}`, {}, signal);
}

export function getSpecialtyGaps(signal?: AbortSignal): Promise<{ specialties: SpecialtyGap[] }> {
  return request("/stats/specialty-gaps", {}, signal);
}

export function getContradictions(
  limit: number = 50,
  signal?: AbortSignal,
): Promise<{ flagged: Contradiction[] }> {
  return request(`/stats/contradictions?limit=${limit}`, {}, signal);
}

export const apiBaseUrl = API_BASE;
