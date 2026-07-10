# Recent Activity Comment Filter Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add collapsible personalization toggles and let administrators choose which content types count owner comments in recent activity.

**Architecture:** Persist the selected Waline URL content types under `SiteProfile.feature_flags`, with absence of the key meaning all four types are enabled. The admin settings page manages this list alongside the existing profile feature flags, and the activity service excludes only comments bound to an administrator when their parsed content type is disabled.

**Tech Stack:** React, TypeScript, TanStack Query, Vitest, FastAPI, SQLAlchemy, SQLite/Waline, pytest.

---

### Task 1: Define and test owner-comment filtering in recent activity

**Files:**
- Modify: `backend/tests/public/test_activity.py`
- Modify: `backend/src/aerisun/domain/activity/service.py`
- Modify: `backend/src/aerisun/domain/engagement/service.py`

**Step 1: Write the failing test**

Add a test that binds an admin comment identity, creates approved comments on `/posts/...` and `/thoughts/...`, disables `posts` through the new feature-flag list, and requests `/api/v1/site/recent-activity`. Assert that the owner post comment is absent, the owner thought comment remains, and a published-content entry remains present.

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/public/test_activity.py -k owner_comment -v`

Expected: FAIL because activity ignores the new setting.

**Step 3: Write minimal implementation**

Extract a reusable public helper in engagement service that identifies an admin-bound comment from its email and avatar key. In activity service, normalize `feature_flags["recent_activity_owner_comment_content_types"]` against `posts`, `diary`, `thoughts`, and `excerpts`, defaulting to all four when missing or invalid. Filter an admin-bound comment when its parsed URL type is not selected; retain visitor comments and all non-comment activity.

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/public/test_activity.py -k owner_comment -v`

Expected: PASS.

### Task 2: Add the settings UI and localization

**Files:**
- Modify: `admin/tests/feature-toggles-layout.test.ts`
- Modify: `admin/src/pages/more/FeatureTogglesSection.tsx`
- Modify: `admin/src/i18n/translations-zh.ts`
- Modify: `admin/src/i18n/translations-en.ts`

**Step 1: Write the failing test**

Extend the feature-toggle layout test to assert that the source contains the `personalization` and `recentActivityOwnerComment` labels, the four options (`posts`, `diary`, `thoughts`, `excerpts`), and profile save payload wiring for `recent_activity_owner_comment_content_types`.

**Step 2: Run test to verify it fails**

Run: `pnpm --filter aerisun-admin test -- feature-toggles-layout.test.ts`

Expected: FAIL because these settings do not exist.

**Step 3: Write minimal implementation**

Add local expansion and draft/saved selection state. Wrap article-directory and reading-progress switches in a default-closed `AppleSwitch` expansion labelled “个性化”; keep private-diary as a separate existing switch. Add a default-closed owner-comment settings row whose label uses `LabelWithHelp`; its expansion contains four selectable buttons, starts with all selected when no valid saved list exists, and saves the ordered list through the existing profile mutation. Add Chinese and English translation strings.

**Step 4: Run test to verify it passes**

Run: `pnpm --filter aerisun-admin test -- feature-toggles-layout.test.ts`

Expected: PASS.

### Task 3: Verify integration

**Files:**
- Verify: `backend/tests/public/test_activity.py`
- Verify: `admin/tests/feature-toggles-layout.test.ts`
- Verify: `admin/src/pages/more/FeatureTogglesSection.tsx`

**Step 1: Run focused test suites**

Run: `cd backend && uv run pytest tests/public/test_activity.py -v`

Run: `pnpm --filter aerisun-admin test -- feature-toggles-layout.test.ts`

**Step 2: Run static checks**

Run: `pnpm --filter aerisun-admin typecheck && pnpm --filter aerisun-admin lint`

**Step 3: Review change scope**

Run: `git diff --check && git status --short && git diff -- backend/src/aerisun/domain/activity/service.py backend/src/aerisun/domain/engagement/service.py backend/tests/public/test_activity.py admin/src/pages/more/FeatureTogglesSection.tsx admin/tests/feature-toggles-layout.test.ts admin/src/i18n/translations-zh.ts admin/src/i18n/translations-en.ts`

Confirm both files under `docs/plans/` remain untracked and are excluded from any later commit.
