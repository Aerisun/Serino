# 单篇文章查看审批 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让管理员可为单篇公开文章开启查看审批，访客经登录、申请与审核后限时查看，并将 RSS 缺省摘要限制为 30 个字符。

**Architecture:** 为文章建立独立 `post_access` 领域和数据表，避免与站点级日记权限混淆。文章详情路由在总开关及单篇开关均开启时调用该领域的访问校验；申请、审核、邮件反馈和后台表格复用日记流程的交互与数据形态。RSS 摘要长度作为文章 RSS 查询的专用参数传入，避免改变文章列表的摘要回退长度。

**Tech Stack:** FastAPI、SQLAlchemy、Alembic、Pydantic、Orval、React 19、TanStack Query、Vitest、pytest。

---

### Task 1: 为文章审批字段和 RSS 回退规则写失败测试

**Files:**
- Modify: `backend/tests/admin/test_content_crud.py`
- Modify: `backend/tests/public/test_feeds.py`
- Modify: `backend/tests/test_migrations.py`

**Step 1: Write the failing tests**

断言文章创建、读取、更新、导出/导入均包含 `requires_approval: false`；文章 RSS 在没有手写摘要时仅含首段前 30 个字符（含省略号），但 `/api/v1/site/posts` 的同一文章保留当前最多 500 字的列表摘要；迁移 head 和 `posts.requires_approval` 列存在。

**Step 2: Run tests to verify they fail**

Run: `uv run --directory backend pytest tests/admin/test_content_crud.py tests/public/test_feeds.py tests/test_migrations.py -q`

Expected: FAIL because the post field, migration and RSS-specific summary length do not exist.

**Step 3: Implement the minimal data model and RSS-length plumbing**

- Add `requires_approval: Mapped[bool]` to `PostEntry`.
- Add `requires_approval` to `PostContentCreate`, `PostContentUpdate`, `PostContentAdminRead`, `_POST_ALLOWED_FIELDS`, JSON and Markdown import/export handling.
- Add an optional `summary_fallback_max_length` parameter to `_list_summary_entries`; call it with `30` only from `list_rss_posts`.
- Add Alembic revision after `0016_post_rss_exclusion` with a non-null false server default for the existing `posts` rows.
- Update migration-head tests.

**Step 4: Run tests to verify they pass**

Run: `uv run --directory backend pytest tests/admin/test_content_crud.py tests/public/test_feeds.py tests/test_migrations.py -q`

Expected: PASS.

### Task 2: 为独立文章申请领域写失败测试

**Files:**
- Create: `backend/tests/content/test_post_access.py`
- Modify: `backend/tests/public/test_site_auth.py` (only if shared site-auth fixtures need extension)

**Step 1: Write the failing tests**

覆盖：未登录访问受保护文章返回 401；已登录未获权返回 403；同一用户对同一文章的待审申请更新而不重复；不同文章必须独立申请；管理员批准后仅能读取该文章；撤销后再次 403；总开关关闭时恢复公开；私密文章仍不对外公开；管理员审核列表含文章标题和正确统计。

**Step 2: Run test to verify it fails**

Run: `uv run --directory backend pytest tests/content/test_post_access.py -q`

Expected: FAIL because article access endpoints and persistence do not exist.

### Task 3: 实现文章访问申请模型、服务和邮件反馈

**Files:**
- Create: `backend/src/aerisun/domain/post_access/__init__.py`
- Create: `backend/src/aerisun/domain/post_access/models.py`
- Create: `backend/src/aerisun/domain/post_access/schemas.py`
- Create: `backend/src/aerisun/domain/post_access/service.py`
- Create: `backend/alembic/versions/0017_post_access_requests.py`
- Modify: `backend/src/aerisun/domain/subscription/service.py`
- Modify: `backend/src/aerisun/core/app_factory.py` or the existing model-import module that initializes SQLAlchemy metadata

**Step 1: Implement minimal persistence and domain operations**

Create `post_access_requests` with `post_id`, `site_user_id`, reason, state, grant/revoke/review timestamps and reviewer, plus indexes for `(post_id, site_user_id, created_at, id)` and status. Implement `post_access_enabled`, active-request lookup, request validation, per-article access check, latest-request admin listing, approve/extend/revoke and typed Pydantic reads. Default the global flag `post_access_approval_enabled` to true and only enforce when both it and `PostEntry.requires_approval` are true.

**Step 2: Reuse notification infrastructure without duplicating SMTP validation**

Extract the diary notification's SMTP-ready check and template rendering into a small access-feedback helper or add a typed article variant alongside it. The article message must use “文章查看申请” wording and identify the article title; it uses the same SMTP availability and send behavior as diary feedback.

**Step 3: Run the domain test to verify it passes**

Run: `uv run --directory backend pytest tests/content/test_post_access.py -q`

Expected: PASS.

### Task 4: 公开和后台 API 接口及 OpenAPI 客户端

**Files:**
- Create: `backend/src/aerisun/api/post_access.py`
- Modify: `backend/src/aerisun/api/site.py`
- Modify: `backend/src/aerisun/api/admin/moderation.py`
- Modify: `backend/src/aerisun/api/admin/schemas.py`
- Modify: `backend/src/aerisun/core/app_factory.py`
- Modify: generated `packages/api-client/openapi.json` and `packages/api-client/src/generated/**` via `pnpm run generate:api`
- Test: `backend/tests/content/test_post_access.py`

**Step 1: Add failing route-level assertions**

Extend the post-access test to call `GET /api/v1/site/post-access/{slug}/me`, `POST /api/v1/site/post-access/{slug}/requests`, `GET /api/v1/admin/moderation/post-access-requests`, and its review `PATCH`, then assert status codes and schemas.

**Step 2: Run the test to verify it fails**

Run: `uv run --directory backend pytest tests/content/test_post_access.py -q`

Expected: FAIL with missing routes.

**Step 3: Implement routes and protected detail cache behavior**

- Register the new site router and add the moderation routes.
- In `read_post`, call the article access requirement before loading the entry; when protection is active return the same private/no-store and `Vary: Cookie` policy as protected diary detail.
- Ensure user-visible request state exposes only the current article, not other approvals.
- Regenerate the API client with `pnpm run generate:api`.

**Step 4: Run API and generated-client verification**

Run: `uv run --directory backend pytest tests/content/test_post_access.py -q && pnpm run verify:generated:api-client`

Expected: PASS.

### Task 5: 管理端配置与文章编辑页测试先行

**Files:**
- Modify: `admin/tests/feature-toggles-layout.test.ts`
- Modify: `admin/tests/post-edit-page.test.tsx`
- Modify: `admin/src/pages/more/FeatureTogglesSection.tsx`
- Modify: `admin/src/pages/posts/PostEditPage.tsx`
- Modify: `admin/src/components/content/PublishTimeFooter.tsx`

**Step 1: Write failing UI tests**

Assert the personalization area has a `LabelWithHelp` for “允许文章配置查看审批”; new and loaded posts default `requires_approval` to false; visible controls are ordered RSS → approval → custom time; both RSS and approval controls are absent for private posts; disabling the global flag hides the approval control and saves the flag.

**Step 2: Run tests to verify they fail**

Run: `pnpm -C admin test -- post-edit-page.test.tsx feature-toggles-layout.test.ts`

Expected: FAIL because the form and feature flag do not exist.

**Step 3: Implement minimal admin UI**

Add the feature flag to the resolved flag list with default true, use `LabelWithHelp` for its explanation, and add a generic second inline footer toggle API so `PostEditPage` can render the controls in the specified order. Render both article-only controls only for public visibility, and serialize `requires_approval` through the existing content editor.

**Step 4: Run tests to verify they pass**

Run: `pnpm -C admin test -- post-edit-page.test.tsx feature-toggles-layout.test.ts`

Expected: PASS.

### Task 6: 文章审核后台页签与测试先行

**Files:**
- Create: `admin/src/pages/moderation/PostAccessRequestsPanel.tsx`
- Modify: `admin/src/pages/moderation/ModerationPage.tsx`
- Modify: `admin/tests/moderation-page.test.tsx` or create a focused `admin/tests/post-access-requests-panel.test.tsx`

**Step 1: Write the failing test**

Mock the generated article access endpoints and assert the moderation navigation shows “文章查看申请” only while the global feature is enabled; the panel renders article title, visitor, reason/status and calls the correct approve/revoke endpoint.

**Step 2: Run the test to verify it fails**

Run: `pnpm -C admin test -- post-access-requests-panel.test.tsx`

Expected: FAIL because the new tab and panel do not exist.

**Step 3: Implement the panel by extracting or parameterizing diary panel primitives**

Reuse the diary panel's row normalization, expiration dialog, query invalidation and mail feedback handling where interfaces are identical. Keep article title returned by the API so the browser does not need N+1 title lookups.

**Step 4: Run the test to verify it passes**

Run: `pnpm -C admin test -- post-access-requests-panel.test.tsx`

Expected: PASS.

### Task 7: 蓝色前台申请弹窗和详情访问体验

**Files:**
- Modify: `frontend/src/components/DiaryAccessPrompt.tsx` or extract a reusable content-access prompt
- Modify: `frontend/src/pages/PostDetail.tsx`
- Create: `frontend/tests/post-access-prompt.test.mjs` or focused Vitest test

**Step 1: Write the failing test**

Assert a 401/403 protected article uses the article request endpoint, offers login/apply actions, and carries the blue article-access visual token; normal/404 post behavior remains unchanged.

**Step 2: Run test to verify it fails**

Run: `pnpm -C frontend test -- post-access-prompt.test.mjs`

Expected: FAIL because post detail treats 401/403 as a generic error.

**Step 3: Implement reusable prompt configuration**

Parameterize the existing diary prompt with target-specific API calls, labels, query keys and color classes, rather than duplicate its focus, toast, request validation and portal behavior. Wire `PostDetail` to classify 401/403 as blocked, disable retries for access errors and show the blue prompt.

**Step 4: Run tests to verify they pass**

Run: `pnpm -C frontend test -- post-access-prompt.test.mjs frontend/tests/subscribe-modal-diary-private.test.mjs`

Expected: PASS.

### Task 8: 全量回归与提交

**Files:**
- Modify: all files from Tasks 1–7

**Step 1: Run focused lint/type/test checks**

Run: `pnpm run lint && pnpm run typecheck && pnpm run test`

Expected: PASS.

**Step 2: Run complete verification**

Run: `pnpm run check`

Expected: PASS including OpenAPI generation, all backend/frontend/admin tests and both builds.

**Step 3: Inspect final scope**

Run: `git diff --check && git status --short && git diff --stat HEAD~1..HEAD`

Expected: no whitespace errors and only the planned feature files plus generated API changes.

**Step 4: Commit only after successful verification**

```bash
git add backend admin frontend packages docs
git commit -m "feat(posts): 支持单篇文章查看审批"
git show -s --format=%B HEAD
```

Expected: Conventional Commit body uses actual newlines and correctly describes the feature.
