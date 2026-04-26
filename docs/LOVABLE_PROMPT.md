# Lovable Prompt — CareGrid AI Frontend

> Archival reference. This is the prompt that produced the app at
> `frontend/care-connect-ai-main/`. Kept here so judges (and future
> contributors) can see the intent the UI was built against.

Paste **everything inside the fenced block below** into Lovable as your
project brief. Lovable will scaffold a React + Vite + Tailwind app that
talks to the FastAPI backend already deployed on Hugging Face Spaces.

After Lovable builds it, set:

```
VITE_API_URL = https://<your-space>.hf.space
```

in Lovable's **Environment Variables** panel, then connect the project
to GitHub and deploy via Vercel.

---

````
Build a single-page React + Vite + Tailwind + shadcn/ui application called
"CareGrid AI" — an Agentic Healthcare Intelligence dashboard for the
Hack-Nation challenge "Serving a Nation: Building Agentic Healthcare Maps
for 1.4 Billion Lives."

The app talks to a FastAPI backend at the URL provided in the env var
`VITE_API_URL`. The backend hosts ~10,000 Indian hospital / clinic /
dentist / pharmacy records from the Virtue Foundation Hackathon dataset.

Read these constants from `import.meta.env.VITE_API_URL` and never
hard-code the backend URL.

## Pages / Layout

A single-page experience with three top-level tabs in this order:

1. **Search** (default) — natural-language search box + ranked results
2. **Crisis Map** — choropleth of medical deserts by state
3. **Audit** — list of contradictions the trust scorer flagged

A persistent header shows the app name "CareGrid AI", a subtitle "Agentic
Healthcare Intelligence for India", and a small badge fetched from
`GET /health` showing `dataset_rows` and `embedding_model`.

## Tab 1 — Search

- A large search input with placeholder text rotating between:
  - "nearest ICU hospital in Bihar with oxygen"
  - "dialysis center within 30 km of 800001"
  - "trauma centre in Maharashtra open 24/7"
  - "rural clinic in Odisha with maternity ward"
- An "example query" pill row underneath the input, clicking a pill fills
  the search box and submits.
- A "Try urgent mode" toggle that, when on, prepends "nearest" to the
  query before sending it (the backend re-weights for proximity).
- POST the query to `${VITE_API_URL}/search` with body
  `{ "query": "<text>", "top_k": 10 }`.

### Result rendering

For each item in `response.results` show a card with:

- Hospital name (large, bold)
- Location line `district, state` (or just `state`)
- A trust score chip with colour-coded background:
  - >= 80 emerald
  - 50–79 amber
  - < 50 rose
- A horizontal stack of "matched feature" tags (e.g. `ICU`, `OXYGEN`).
- A one-line `explanation`.
- A right-side "score components" bar with four mini bars showing
  `score_components.semantic / keyword / trust / location`.
- An expandable section **"Why this trust score?"** that shows the
  `trust_breakdown` array. For each item render:
  ```
  [+20]  Major specialty (ICU / dialysis / trauma / cardio / neuro) present
         "Recently installed a 10-bed ICU with 4 ventilators and oxygen supply"
  ```
  Render the delta as a coloured pill, the rule as bold text, and the
  evidence as a muted italic blockquote.

Above the results, render the parsed `query_understood` block as a
"Chain of thought" inspector — a small monospaced JSON view (collapsed by
default). This is judged-mode visibility into how the agent parsed the
query.

When the response includes `distance_km`, show "{X} km away" next to the
location line.

## Tab 2 — Crisis Map

- On mount, GET `${VITE_API_URL}/stats/deserts?top_n=36` and
  `${VITE_API_URL}/stats/specialty-gaps`.
- Render an Indian states choropleth using react-simple-maps
  ("admin1 India" topojson available at
  https://cdn.jsdelivr.net/gh/datameet/maps/States/Admin2.geojson —
  fall back to a plain ranked list if the topojson load fails).
- Colour each state by its `desert_score` (red = worst, green = best).
- Hovering a state shows a tooltip with facility_count, avg_trust_score,
  major_specialty_share, hospital_share.
- Below the map, a **specialty gap matrix**: one row per major specialty
  (icu, dialysis, trauma, cardiology, neurology), one column per top
  state, cell-coloured by facility count. Use the
  `/stats/specialty-gaps` response.

## Tab 3 — Audit

- On mount, GET `${VITE_API_URL}/stats/contradictions?limit=50`.
- Render a table with columns:
  Hospital | State | Trust | Rule | Evidence (citation)
- Style the Evidence column as a muted blockquote.
- Add a search box to filter rows client-side by hospital_name or state.
- Clicking a row opens a slide-over panel that calls
  `${VITE_API_URL}/hospitals/{hospital_id}` and renders the full record:
  - Trust score (large)
  - Trust breakdown (rule + delta + evidence) as cards
  - `specialty_tags` and `equipment_tags` as chips
  - Raw `notes` in a `<pre>` block

## Visual style

- Tailwind + shadcn/ui components (Card, Badge, Tabs, Sheet, Tooltip).
- Light theme, but readable. Card backgrounds slate-50, borders slate-200.
- Tasteful accent colour: indigo-600 for primary actions, emerald-500 for
  trust badges, rose-500 for contradictions.
- Use lucide-react icons (Search, AlertTriangle, MapPinned, Sparkles).
- Responsive down to 360px wide.

## API contract (TypeScript types)

```ts
type SearchResponse = {
  results: HospitalResult[];
  query_understood: QueryUnderstood;
  total_candidates: number;
};

type HospitalResult = {
  hospital_id: number;
  hospital_name: string;
  score: number;            // 0..1
  trust_score: number;      // 0..100
  explanation: string;
  location: string;
  state: string | null;
  district: string | null;
  pin_code: string | null;
  latitude: number | null;
  longitude: number | null;
  distance_km: number | null;
  matched_features: string[];
  trust_breakdown: { rule: string; delta: number; evidence: string }[];
  score_components: { semantic: number; keyword: number; trust: number; location: number };
};

type QueryUnderstood = {
  state: string | null;
  pin: string | null;
  radius_km: number | null;
  specialties: string[];
  requirements: string[];
  sort: "relevance" | "distance";
  raw_query: string;
};

// /stats/deserts → { states: StateDesert[] }
type StateDesert = {
  state: string;
  facility_count: number;
  hospital_count: number;
  avg_trust_score: number;
  major_specialty_share: number;
  hospital_share: number;
  desert_score: number;
};

// /stats/specialty-gaps → { specialties: string[], states: string[], cells: SpecialtyGapCell[], summary: ... }
type SpecialtyGapCell = {
  specialty: string;
  state: string;
  facility_count: number;
};

// /stats/contradictions → { flagged: Contradiction[] }
type Contradiction = {
  hospital_id: number;
  hospital_name: string;
  state: string | null;
  district: string | null;
  pin_code: string | null;
  trust_score: number;
  rule: string;
  evidence: string;
};
```

## Deliverables

- `src/lib/api.ts` — typed wrappers around `/search`, `/health`,
  `/hospitals/:id`, `/stats/deserts`, `/stats/specialty-gaps`,
  `/stats/contradictions`.
- `src/pages/SearchPage.tsx`, `src/pages/MapPage.tsx`,
  `src/pages/AuditPage.tsx`.
- `src/components/TrustBadge.tsx`, `TrustBreakdown.tsx`,
  `ScoreComponents.tsx`, `ChainOfThought.tsx`.
- `vite.config.ts` configured for Vercel.
- `.env.example` with `VITE_API_URL=https://your-space.hf.space`.
- `vercel.json` setting `framework: "vite"` and the SPA rewrite.

## Out of scope

- Authentication.
- Booking / appointments.
- Real-time updates.

This is a hackathon demo: prioritise legibility, transparent reasoning,
and a great first impression over feature breadth.
````

---

## What you'll have to do after Lovable finishes

1. Click **Publish to GitHub** in Lovable (or download the zip and drop
   it into `frontend/care-connect-ai-main/` like we did).
2. Import the GitHub repo into Vercel.
3. In Vercel → Project → Settings → Environment Variables, add
   `VITE_API_URL` pointing at your Hugging Face Space URL.
4. Take the Vercel domain, paste it into the Hugging Face Space's
   `CAREGRID_CORS_ORIGINS` env var, and re-deploy the Space.
5. Run `/health` from the Vercel page once to warm up the FAISS index.
