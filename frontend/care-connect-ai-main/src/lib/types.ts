export type ScoreComponentsT = {
  semantic: number;
  keyword: number;
  trust: number;
  location: number;
};

export type TrustBreakdownItem = {
  rule: string;
  delta: number;
  evidence: string;
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
  score_components: ScoreComponentsT;
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

export type StateDesert = {
  state: string;
  facility_count: number;
  hospital_count: number;
  avg_trust_score: number;
  major_specialty_share: number;
  hospital_share: number;
  desert_score: number;
};

export type SpecialtyGapCell = {
  state: string;
  specialty: string;
  facility_count: number;
};

export type SpecialtyGapsResponse = {
  specialties: string[];
  states: string[];
  cells: SpecialtyGapCell[];
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

export type HealthResponse = {
  status: string;
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
  raw?: Record<string, unknown> | null;
};
