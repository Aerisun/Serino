# Admin Performance Audit

Date: 2026-04-09

## Baseline

Commands used:

```bash
corepack pnpm -C admin build
node scripts/analyze-admin-bundle.mjs
```

Build summary from the current tree:

- Entry assets referenced by `dist/index.html`:
  - `index-DdAM9CCa.js` = 273.78 kB raw / 84.93 kB gzip
  - `createLucideIcon-DOvLu073.js` = 142.12 kB raw / 44.69 kB gzip
  - `index-v-S1x69N.css` = 126.13 kB raw / 20.26 kB gzip
  - `admin-CjdQnjaV.js` = 91.36 kB raw / 21.00 kB gzip
  - `useMutation-Cy7MqMGC.js` = 27.00 kB raw / 8.16 kB gzip
- Large shared chunks:
  - `workflow-editor-types-Dq3TS310.js` = 197.38 kB raw / 64.62 kB gzip
  - `lib-Z6e769C5.js` = 149.68 kB raw / 44.13 kB gzip
  - `WorkflowVisualEditorDialog-quJ6KldY.js` = 101.57 kB raw / 28.38 kB gzip
  - `Select-CRh9WxQO.js` = 45.13 kB raw / 15.95 kB gzip

Observed totals from `admin/dist/assets`:

- JS total: 1.52 MB raw / 500.23 kB gzip
- CSS total: 141.17 kB raw / 22.73 kB gzip

## Current Snapshot

Build summary after the optimization batches currently in the tree:

- Entry assets referenced by `dist/index.html`:
  - `index-BAU0LYDz.js` = 280.03 kB raw / 88.76 kB gzip
  - `index-_wLgSKRr.css` = 126.20 kB raw / 20.27 kB gzip
  - `query-CYM5C3GU.js` = 13.11 kB raw / 4.42 kB gzip
  - `react-DYpzXrK8.js` = 7.34 kB raw / 2.81 kB gzip
  - `react-dom-DW2zlwse.js` = 3.48 kB raw / 1.32 kB gzip
  - `adminApi-jvESYrZg.js` = 1.54 kB raw / 825 B gzip
  - `preload-helper-cFabezPi.js` = 1.17 kB raw / 686 B gzip
  - `chunk-DECur_0Z.js` = 685 B raw / 417 B gzip
  - `storage-IPPZiHNV.js` = 653 B raw / 336 B gzip
  - `jsx-runtime-D2guwa18.js` = 424 B raw / 296 B gzip
- Large lazy chunks:
  - `esm-BNR4EvMn.js` = 170.17 kB raw / 54.43 kB gzip
  - `lib-pcjQG2iq.js` = 149.74 kB raw / 44.15 kB gzip
  - `WorkflowInspector-B8RKY9Eu.js` = 73.45 kB raw / 20.90 kB gzip
  - `WorkflowVisualEditorDialog-Dbekoais.js` = 50.06 kB raw / 16.34 kB gzip
  - `Select-DCVbfCEb.js` = 45.26 kB raw / 15.99 kB gzip
  - `admin-instance-DZeMbbZB.js` = 36.17 kB raw / 14.19 kB gzip

Observed totals from `admin/dist/assets`:

- JS total: 1.55 MB raw / 519.64 kB gzip
- CSS total: 141.23 kB raw / 22.75 kB gzip

Notes:

- Startup no longer preloads the generated admin client chunk. The generated client runtime now lives in `admin-instance-*.js` and is only initialized on routes that actually need it.
- The eager entry preload set is down to about `99.87 kB gzip`, versus roughly `129.97 kB gzip` in the original baseline and roughly `120.89 kB gzip` before the most recent startup-path refactors.
- `@serino/utils` preview and image-upload helpers have been moved off the admin entry path by switching startup code to subpath imports.

## Findings

### 1. Base route cost is already non-trivial before page-specific logic

- Route-level lazy loading is present in `admin/src/App.tsx`, but the root still carries a heavy shared startup surface and only sets `retry` + `refetchOnWindowFocus` on the global query client.
- `admin/src/App.tsx:46` has no default `staleTime`, so admin GET queries tend to refetch on remount/navigation even when the data is effectively static for a session.
- Built output shows a relatively expensive shared base:
  - `index-*.js` 273.78 kB raw
  - `admin-*.js` 91.36 kB raw
  - `createLucideIcon-*.js` 142.12 kB raw
  - `lib-*.js` 149.68 kB raw

Impact:

- First load of `/admin/` is not just “dashboard code”; it also pays for large shared runtime and utility chunks.
- Back-and-forth navigation is more network/chatty than necessary because cache freshness is conservative.

### 2. Layout layer performs background work on every page

- `admin/src/layouts/AdminLayout.tsx:110` and `admin/src/layouts/AdminLayout.tsx:120` poll two moderation count queries every 30 seconds from the global shell.
- The same layout also attaches scroll and resize listeners in `admin/src/layouts/AdminLayout.tsx:135`.

Impact:

- Every admin screen pays moderation badge cost even when the user never opens moderation.
- This is low per request, but it is always-on background traffic and permanent shell work.

### 3. Automation module ships too much editor code into non-editor screens

- `admin/src/pages/automation/AgentWorkflowsSection.tsx:15` imports helpers from `workflow-editor-types.ts` just to create a blank workflow payload.
- `admin/src/pages/automation/workflow-editor-types.ts:1` is a 1338-line mega-module and becomes a 197.38 kB raw chunk in production.
- The built `workflow-editor-types-*.js` chunk contains workflow copy, D3 helpers, icon declarations, schema helpers, and editor-only logic together.

Impact:

- The workflows list page pulls editor-oriented code even before the visual editor dialog opens.
- The module is too coarse for the bundler to split efficiently.

### 4. Automation pages over-poll and duplicate nearby data fetches

- `admin/src/pages/automation/AgentActivitySection.tsx:34` polls approvals every 5 seconds.
- `admin/src/pages/automation/ApprovalsPage.tsx:86` polls the same approvals list again every 5 seconds.
- `admin/src/pages/automation/AgentRunDetailPage.tsx:12` to `admin/src/pages/automation/AgentRunDetailPage.tsx:14` polls run detail, steps, and approvals every 5 seconds.
- `admin/src/pages/automation/ApprovalsPage.tsx:87` separately fetches runs just to build a name map.

Impact:

- Activity, approvals, and run detail screens create overlapping refresh loops.
- Network cost scales with open tabs and route switches instead of a shared cache policy.

### 5. Moderation page has a serial N+1 title resolution path

- `admin/src/pages/moderation/ModerationPage.tsx:125` to `admin/src/pages/moderation/ModerationPage.tsx:175` resolves content titles by looping `type -> slug -> search term`, awaiting each request serially.
- The same page also renders markdown with `react-markdown` + `remark-gfm`.

Impact:

- One page of moderation items can trigger many follow-up list queries before titles stabilize.
- Time-to-usable is affected more by secondary lookups than by the primary moderation response.

### 6. Markdown preview work is eager

- `admin/src/components/MarkdownEditor.tsx:33` imports `MarkdownPreview` directly, so the preview stack is part of the edit-screen dependency graph even when the user only writes.
- `admin/src/components/MarkdownPreview.tsx:149` fetches link-preview data as soon as a rich link card mounts.
- Built inspection of `lib-*.js` shows the markdown/GFM parser stack is inside a large shared chunk.

Impact:

- Edit pages load markdown rendering machinery immediately instead of only when preview mode is used.
- Pages with many links can trigger a burst of metadata fetches.

### 7. Table-heavy pages still use full render, not selective render

- `admin/src/components/DataTable.tsx` renders all current rows directly, with selectable rows and expandable rows but no virtualization/windowing.
- `admin/src/pages/visitors/VisitorsSubscribersPage.tsx:56` mounts row-level message queries inside expanded content.

Impact:

- Large pages remain sensitive to row count, column richness, and expanded subpanels.
- It is manageable at page size 20 now, but it will become visible quickly on denser admin datasets.

### 8. Several admin pages are already too large to optimize comfortably

- `admin/src/pages/visitors/VisitorsPage.tsx` = 1638 lines
- `admin/src/pages/moderation/ModerationPage.tsx` = 1355 lines
- `admin/src/pages/automation/workflow-editor-types.ts` = 1338 lines
- `admin/src/components/MarkdownPreview.tsx` + `admin/src/components/MarkdownEditor.tsx` = 734 lines combined

Impact:

- Performance work is harder because render, state, request, and view logic are tightly mixed.
- Bundle splitting opportunities are obscured by file-level coupling.

## Priority Order

### P0: Start here

1. Split `workflow-editor-types.ts` into smaller modules.
   - Keep list-page helpers (`WORKFLOWS_QUERY_KEY`, blank workflow defaults) separate from canvas/editor helpers.
   - Goal: opening `/agent/workflows` should not pull the large editor support chunk.

2. Remove shell-level unconditional polling.
   - Replace the two moderation badge queries with a single lightweight endpoint, or only fetch when moderation is visible/relevant.

3. Add more realistic admin query defaults.
   - Introduce `staleTime` for low-volatility GET data such as settings, lists, and system metadata.
   - Prefer page-specific overrides only for truly live views.

4. Replace moderation title N+1 lookup with batch/server support.
   - Best fix: backend returns the title directly in moderation records.
   - Acceptable interim fix: a bulk title lookup endpoint keyed by `(content_type, slug)`.

### P1: Next wave

1. Lazy-load markdown preview internals.
   - Only import/render `MarkdownPreview` when preview mode is active.
   - Defer link-preview fetch until card visibility or explicit user intent.

2. Consolidate automation polling.
   - Reuse approvals/runs caches across `AgentActivitySection`, `ApprovalsPage`, and run detail.
   - Reduce 5-second polling to the routes that actually need live status.

3. Audit `Select` usage frequency.
  - The shared Radix Select / Floating UI chunk is 45.13 kB raw.
   - For simple pickers, consider a lighter native/selective implementation.

### P2: Structural cleanup

1. Break mega-pages into request containers + presentational sections.
2. Add route-level performance marks and request counters for admin pages.
3. Evaluate virtualization for audit log / moderation / visitor datasets if page sizes increase.

## Suggested Acceptance Targets

- Reduce admin first-load transferred JS for the dashboard path by at least 20%.
- Remove all nonessential background polling on routes unrelated to automation/moderation.
- Make moderation page title rendering require zero follow-up list searches after the primary response.
- Ensure markdown preview network work is zero until preview is opened.
- Keep repeated navigation between list pages from issuing avoidable remount refetches.

## Repeatable Workflow

1. Build the admin app.
2. Run `node scripts/analyze-admin-bundle.mjs`.
3. Record the largest JS/CSS chunks before and after each optimization batch.
4. Verify request count on these routes:
   - `/admin/`
   - `/admin/moderation`
   - `/admin/agent/workflows`
   - `/admin/posts`
