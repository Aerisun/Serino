# Asset List Column Layout Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Restore the resource list's stable desktop column proportions and prevent long filenames from squeezing compact metadata columns into multiple lines.

**Architecture:** Reuse the existing `DataTable` column `className` API and add an optional table-level class pass-through. The resource file list alone uses fixed table layout, compact column widths, and inner truncation wrappers; other tables keep their existing automatic layout and all resource data behavior remains unchanged.

**Tech Stack:** React 19, TypeScript, Tailwind CSS 3, Vitest, Testing Library

---

### Task 1: Add a failing resource-list layout regression test

**Files:**
- Modify: `admin/tests/assets-page.test.tsx:135-245`
- Test: `admin/tests/assets-page.test.tsx`

**Step 1: Stabilize the mutable asset fixture**

Reset `file_name`, `note`, `category`, `scope`, `visibility`, and `public_url` in `beforeEach` so the new long-name test cannot leak state into existing preview and dialog tests.

**Step 2: Write the failing test**

Add a test that assigns a deliberately long filename, renders `AssetsPage`, and asserts:

```tsx
const fileNameElement = screen.getByText(longFileName);
expect(fileNameElement.getAttribute("title")).toBe(longFileName);
expect(fileNameElement.className).toContain("truncate");
expect(fileNameElement.closest("td")?.className).toContain("min-w-[12rem]");

for (const header of ["分类", "资源范围", "可见性", "文件大小", "链接"]) {
  expect(screen.getByRole("columnheader", { name: header }).className).toContain("whitespace-nowrap");
}
```

Also assert that the table uses `table-fixed` with a `59rem` minimum, compact columns have explicit minimum widths, the filename preview icon follows the text, and the link/action groups are centered in two separately labelled columns.

**Step 3: Run the test to verify RED**

Run:

```bash
pnpm -C admin test -- assets-page.test.tsx
```

Expected: the new test fails because the filename has no `title`/`truncate` treatment and the columns have no width or `whitespace-nowrap` classes.

### Task 2: Apply stable resource-list column sizing

**Files:**
- Modify: `admin/src/components/DataTable.tsx:20-75`
- Modify: `admin/src/pages/assets/AssetsPage.tsx:613-735`
- Test: `admin/tests/assets-page.test.tsx`

**Step 1: Constrain the filename column**

Add an optional `tableClassName` prop to `DataTable` and pass it to the existing `Table`. Enable `min-w-[59rem] table-fixed` only on the resource file list so long content cannot override declared column widths.

Use the existing column `className` API for the filename column:

```tsx
className: "w-[12rem] min-w-[12rem]"
```

Wrap the filename and preview button in a full-width, `min-w-0` flex row with a `0.375rem` gap. Give the text `min-w-0 truncate` without `flex-1`, set `title={row.file_name}`, and keep the preview button `shrink-0`. Short filenames therefore keep the preview icon immediately beside the name, while long names still truncate first.

**Step 2: Constrain the note and category columns**

- Note: `10rem` base/minimum width; render as one-line ellipsis with its full value in `title`.
- Category: `8rem` base/minimum width with compact horizontal padding and `whitespace-nowrap`; truncate unusually long custom category names inside the cell.

**Step 3: Protect the compact metadata and action columns**

Apply explicit width/min-width plus `whitespace-nowrap` to:

```text
资源范围  5.25rem
可见性    4.75rem
文件大小  5.5rem
链接      4.75rem
操作      4.75rem
```

Keep link and action controls in single-line flex rows (`flex-nowrap`) with 2rem icon buttons. Center the link controls in the “链接” column, and center edit/delete in a separate, visibly labelled “操作” column. The `59rem` table minimum fits a 958px desktop content area without overflow and only triggers horizontal scrolling below that width.

**Step 4: Run the focused test to verify GREEN**

Run:

```bash
pnpm -C admin test -- assets-page.test.tsx
```

Expected: all resource-page tests pass.

### Task 3: Verify behavior and visual proportions

**Files:**
- Verify: `admin/src/pages/assets/AssetsPage.tsx`
- Verify: `admin/tests/assets-page.test.tsx`

**Step 1: Run focused static checks**

Run:

```bash
pnpm -C admin typecheck
pnpm -C admin lint
pnpm -C admin build
```

Expected: all commands exit successfully without warnings.

**Step 2: Inspect the page in a real browser**

Use `@playwright` with the existing development environment. Check the resource list at the original screenshot's desktop width and at a narrower admin width.

Expected desktop result:

- Filename and note receive the main horizontal space.
- Category, scope, visibility, size, links, and actions remain single-line.
- Long filenames end in an ellipsis, with the full value available through the title tooltip.

Expected narrow result:

- At a 958px content width, the table fits exactly and the delete button remains visible.
- Below the `59rem` table minimum, the table scrolls horizontally.
- Compact fields and action buttons do not stack or wrap.

**Step 3: Run the project check if the surrounding in-progress work is ready**

Run:

```bash
pnpm run check
```

Expected: all workspace checks pass. If an unrelated pre-existing in-progress change fails, preserve the output and report the exact failure without modifying unrelated files.

**Step 4: Preserve the user's existing uncommitted work**

Do not create an implementation commit automatically: `AssetsPage.tsx` and its test already contain the user's broader uncommitted resource work. Report the exact files and hunks changed for this layout fix so the user can include them in the eventual feature commit without accidentally splitting or capturing unrelated work.
