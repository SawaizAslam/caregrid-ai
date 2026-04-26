# CareGrid AI Frontend

This folder is the staging area for the Lovable-generated frontend.
Until you run Lovable, it contains:

- `LOVABLE_PROMPT.md` — paste this into Lovable as your project brief.
- `api/client.ts` — typed TypeScript client for the FastAPI backend.
  Lovable will produce its own client, but you can drop this file in if
  Lovable's stub doesn't match the schema.
- `.env.example` — copy to `.env.local` and set `VITE_API_URL`.
- `vercel.json` — SPA rewrite + security headers, ready for Vercel.

## Workflow

1. **Generate**: paste `LOVABLE_PROMPT.md` into [lovable.dev](https://lovable.dev).
2. **Connect to backend**: in Lovable's env panel set
   `VITE_API_URL=https://<your-hf-space>.hf.space`. Confirm it can hit
   `/health` from a browser preview.
3. **Push to GitHub**: use Lovable's "Connect to GitHub" button.
4. **Deploy on Vercel**: import the GitHub repo, framework is auto-
   detected (Vite). Add `VITE_API_URL` again in Vercel → Settings →
   Environment Variables.
5. **CORS handshake**: copy your Vercel production URL into the
   Hugging Face Space's `CAREGRID_CORS_ORIGINS` setting and redeploy.

## What the frontend talks to

| Endpoint                          | Purpose                                    |
| --------------------------------- | ------------------------------------------ |
| `GET  /health`                    | Header status badge (rows, encoder)        |
| `POST /search`                    | Search tab — main flow                     |
| `GET  /hospitals/{id}`            | Audit tab — facility detail panel          |
| `GET  /stats/overview`            | Top-line counts                            |
| `GET  /stats/deserts`             | Crisis Map choropleth                      |
| `GET  /stats/specialty-gaps`      | Specialty coverage matrix                  |
| `GET  /stats/contradictions`      | Audit tab — flagged-row table              |

Full type definitions live in `api/client.ts`.
