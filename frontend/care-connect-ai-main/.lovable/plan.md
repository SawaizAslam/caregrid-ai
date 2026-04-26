
# CareGrid AI — Implementation Plan

A single-page React + Vite + Tailwind + shadcn/ui dashboard for the Hack-Nation "Agentic Healthcare Maps" challenge. Three tabs, one persistent header, all data fetched from a FastAPI backend at `import.meta.env.VITE_API_URL`.

## 1. Foundations

- **Env wiring**
  - Read `import.meta.env.VITE_API_URL` everywhere through one helper. Never hard-code the URL.
  - Add `.env.example` with `VITE_API_URL=https://your-space.hf.space`.
  - Add type declaration for `VITE_API_URL` in `src/vite-env.d.ts`.
- **Deploy config**
  - `vercel.json` with `{ "framework": "vite", "rewrites": [{ "source": "/(.*)", "destination": "/" }] }` for SPA routing.
  - Confirm `vite.config.ts` works on Vercel (no changes needed beyond the existing setup).
- **Design tokens (light theme)**
  - Tailwind palette: slate-50 card surfaces, slate-200 borders, indigo-600 primary, emerald-500 trust positive, amber-500 trust mid, rose-500 contradictions / trust low.
  - Update `src/index.css` HSL tokens so shadcn primitives inherit the indigo accent and slate surface colors.
  - Typography: Inter for UI, JetBrains Mono (or `font-mono`) for the Chain-of-Thought JSON view.
- **Icons**: lucide-react (`Search`, `AlertTriangle`, `MapPinned`, `Sparkles`, `ChevronDown`, `Activity`).
- **Data layer**: TanStack Query (already installed) for all GET calls; plain `fetch` wrapper for POST.

## 2. Persistent Header

- Left: app name **"CareGrid AI"** with a small `Sparkles` glyph; subtitle **"Agentic Healthcare Intelligence for India"**.
- Right: a small badge fetched from `GET /health` showing `{row_count.toLocaleString()} records · {embedding_model}`. Skeleton while loading; subtle red dot if the call fails.
- Below header: shadcn `Tabs` with three triggers — **Search** (default), **Crisis Map**, **Audit**. Tab state lives in URL hash (`#search`, `#map`, `#audit`) so refresh keeps the user in place.

## 3. API Layer — `src/lib/api.ts`

A typed module exporting:

- `getHealth()` → `{ row_count, embedding_model }`
- `search(query, top_k=10)` → `SearchResponse` (POST)
- `getHospital(id)` → full hospital record
- `getDeserts(top_n=36)` → `StateDesert[]`
- `getSpecialtyGaps()` → matrix payload
- `getContradictions(limit=50)` → `Contradiction[]`

All TypeScript types from the spec live in `src/lib/types.ts`. Each call surfaces errors as thrown `Error` instances so React Query handles retry / error UI.

## 4. Tab 1 — Search (`src/pages/SearchPage.tsx`)

- **Hero search input**
  - Large rounded input with `Search` icon prefix.
  - Placeholder text rotates every 3s through the four example queries from the spec (smooth fade).
  - Submit on Enter or button click.
- **Example pills row** under the input — clicking a pill fills the input and immediately submits.
- **"Try urgent mode" toggle** (shadcn `Switch`) — when on, the submitted query is prefixed with `"nearest "` before POSTing; a small `Activity` icon and helper text appear next to the toggle ("Reweights for proximity").
- **Submission**: POST `${VITE_API_URL}/search` with `{ query, top_k: 10 }`. Loading state shows 5 skeleton cards.
- **`ChainOfThought` inspector** (above results) — collapsed `Card` titled "Chain of thought". Expanded body renders `query_understood` as syntax-highlighted monospaced JSON. Subtle indigo border to signal "judges look here".
- **Result cards** (one per `results[]` item):
  - Row 1: bold hospital name, right-aligned `TrustBadge` (color-coded: ≥80 emerald, 50–79 amber, <50 rose; numeric score).
  - Row 2: `MapPinned` + `district, state` (or just state); if `distance_km != null` append `· {X.X} km away`.
  - Row 3: horizontal stack of matched feature `Badge`s (e.g. `ICU`, `OXYGEN`).
  - Row 4: one-line `explanation` in slate-600.
  - Right rail: `ScoreComponents` — four mini horizontal bars labeled Semantic / Keyword / Trust / Location, each filled to its 0–1 value with a tooltip showing the exact number.
  - Footer: collapsible `"Why this trust score?"` (shadcn `Collapsible`). Each `trust_breakdown` row renders as:
    - Colored pill `[+20]` (emerald for positive deltas, rose for negative).
    - Bold rule text.
    - Italic muted blockquote with the evidence citation.
- **Empty / error states**: friendly empty card with the example pills repeated; error toast via existing `sonner`.

## 5. Tab 2 — Crisis Map (`src/pages/MapPage.tsx`)

- On mount, fire two queries in parallel: `/stats/deserts?top_n=36` and `/stats/specialty-gaps`.
- **Choropleth**
  - Add `react-simple-maps` + `d3-scale` dependencies.
  - Load India admin1 topojson from `https://cdn.jsdelivr.net/gh/datameet/maps/States/Admin2.geojson`.
  - Color states by `desert_score` using a red→amber→green scale (red = worst desert).
  - Hover: shadcn `Tooltip` showing `facility_count`, `avg_trust_score` (1 decimal), `major_specialty_share` (%), `hospital_share` (%).
  - **Fallback**: if topojson fetch fails, render a ranked vertical bar list of the same states with the same color scale — no broken UI.
  - Legend strip below the map explaining the color scale.
- **Specialty Gap Matrix** (below map)
  - Rows: `icu`, `dialysis`, `trauma`, `cardiology`, `neurology`.
  - Columns: top N states from the gaps response.
  - Each cell: facility count, background tint scaled to the row's max (so each specialty has its own intensity ramp). Sticky first column for row labels; horizontal scroll on narrow screens.
- Header strip with two summary stats: "Worst desert: {state}" and "Most underserved specialty: {name}".

## 6. Tab 3 — Audit (`src/pages/AuditPage.tsx`)

- On mount, GET `/stats/contradictions?limit=50`.
- **Filter input** (top): `Input` with `Search` icon — filters rows client-side by `hospital_name` or `state` (case-insensitive substring).
- **Table** (shadcn `Table`):
  - Columns: Hospital · State · Trust (color-coded chip) · Rule (bold) · Evidence (muted italic blockquote, truncated to 2 lines with full text in a tooltip).
  - Row hover highlight; entire row clickable.
- **Slide-over detail panel** (shadcn `Sheet`, right side):
  - Triggered by row click; calls `GET /hospitals/{hospital_id}`.
  - Skeleton while loading.
  - Body:
    - Large `TrustBadge` with the numeric score and a one-line caption.
    - Section "Trust breakdown" — each entry rendered as the same pill + bold rule + italic blockquote pattern from the Search tab (reuses `TrustBreakdown` component).
    - Section "Specialties & equipment" — chips.
    - Section "Raw notes" — `<pre>` block with whitespace preserved, slate-100 background, max-height with scroll.

## 7. Shared components

- `src/components/TrustBadge.tsx` — color-coded chip (emerald / amber / rose by threshold), accepts `score` and optional `size`.
- `src/components/TrustBreakdown.tsx` — renders a `trust_breakdown[]` array with the pill/bold/blockquote pattern.
- `src/components/ScoreComponents.tsx` — four mini bars with labels and tooltips.
- `src/components/ChainOfThought.tsx` — collapsible monospaced JSON viewer for `query_understood`.
- `src/components/AppHeader.tsx` — title, subtitle, health badge, tabs container.

## 8. UX polish

- Responsive down to 360px: result cards stack the right-rail score components below the explanation on small screens; map switches to ranked-list fallback under `md`.
- All async states have skeletons (no spinners-only).
- Smooth tab transitions; persistent scroll position per tab.
- Keyboard: Enter submits search, `/` focuses the search input from anywhere in the Search tab.

## 9. Out of scope

- Authentication, booking, appointments, real-time updates — explicitly skipped per spec.

## 10. New dependencies

- `react-simple-maps`, `d3-scale`, `topojson-client` (peer for react-simple-maps).

The result is a hackathon-ready demo that makes the agent's reasoning, trust scoring, and geographic gaps obvious at a glance — optimized for the judge's first 30 seconds.
