# Performance UI

The new `PerformanceDashboard` is the default authenticated view. The original
dashboard remains available under **Reporting tools**; Data Hub still manages
the same records and upload endpoints. No backend or authentication behavior was
changed. Existing Render `VITE_API_URL` configuration is preserved.

## Local validation

Run in `frontend`:

```powershell
npm ci
node --test src/components/performance/model.test.js
npm run build
```

For a populated, read-only UI test, run `node tests/preview-api.mjs` in one
terminal. In another, run:

```powershell
$env:VITE_API_URL = 'http://127.0.0.1:8766/api'
$env:VITE_UI_PREVIEW = 'true'
node node_modules/vite/bin/vite.js --host 127.0.0.1
```

The preview banner identifies synthetic data. The fixture server binds only to
loopback, rejects writes, and is not imported or included in production builds.
For a normal preview, omit `VITE_UI_PREVIEW` and use the new CIMB backend URL in
`VITE_API_URL`. Do not use the original dashboard backend.

## Checked interactions

- Desktop overview matches the reference's burgundy/light visual direction.
- Five platform submenus update KPIs, content, formats and reach breakdown.
- Instagram Stories stay separate from executive post totals.
- Content search, format details, date selection and benchmark-mode switching.
- Empty date range (2099 fixture) and API error (2098 fixture) clear old values.
- Follower sheet form and matching-month follower aggregation.
- Phone layout and navigation drawer; no horizontal page overflow at 390px.
- Existing Data Hub remains reachable without changing stored data.
- Print/PDF layout provided via Download report.

## Data limitations

- Campaign IDs/tags are not in the existing post API; the campaign card explains
  that missing source instead of inventing campaign groups.
- Category endpoint supplies title-classified post counts, not category reach or
  ER%. The chart and subtitle explicitly reflect that available measure.
- Followers require the existing Google Sheet endpoint. Totals use only months
  observed across all selected platforms; missing counts are not filled as zero.
- Executive ER uses the existing backend formula (with its FB/IG views fallback).
  Platform/format ER is a post-count-weighted mean of reported post rates.
- Benchmark cards compare a prior equal-length period or same dates last year.
  No industry or campaign benchmark source is available.
- AI failures are shown explicitly; the dashboard never invents generated copy.
- Live backend status on 2026-08-28 reported a Supabase tenant/user connection
  error. This UI change does not modify credentials or repair that connection.

## Release scope

Deployment is limited to DULANAKA98/CIMB-Social-Media-Performance-Dashboard
and the cimb-dashboard-dev Render services. Do not deploy the original dashboard.
The pre-existing frontend-only login remains unsuitable for client production.
