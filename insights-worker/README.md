# CIMB dashboard insights worker

This Worker belongs only to the new `CIMB-Social-Media-Performance-Dashboard`.
It uses Cloudflare Workers AI and never connects to the dashboard database.
The dashboard backend sends a small aggregate snapshot and receives structured
insight text. The same protected Worker also answers dashboard chat questions
at `/chat`; it never receives database credentials or direct database access.

## Deploy

1. Sign in to the Cloudflare account that should own the service.
2. Run `npm install` in this directory.
3. Create the private route key with `openssl rand -hex 32`.
4. Store it with `npx wrangler secret put CIMB_INSIGHTS_KEY`.
5. Deploy with `npm run deploy`.
6. In the new dashboard backend environment, set:
   - `CIMB_INSIGHTS_URL=https://cimb-dashboard-insights.dulanaka98.workers.dev/insights`
   - `CIMB_INSIGHTS_KEY` to the same private value.

Never put the key in the frontend, source control, chat, or screenshots.

## Routes

- `GET /healthz` — public service health check.
- `POST /insights` — protected Key Insights generation.
- `POST /chat` — protected; superseded by `/sql`, kept for rollback.
- `POST /sql` — protected LLM proxy for the dashboard chat agent. The backend
  sends `{messages, max_tokens}` and receives `{output}`. The Worker holds no
  schema knowledge and no database access; it never sees the query results it
  is not given. Uses a larger model than the other routes, since the backend
  asks it to write SQL.
