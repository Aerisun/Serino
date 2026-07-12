// @vitest-environment jsdom

import { afterEach, describe, expect, it } from "vitest";
import {
  applySynchronizedStateUpdate,
  clearEditorDraftSnapshot,
  normalizeServerTextField,
  readEditorDraftSnapshot,
  saveEditorDraftSnapshot,
} from "../src/lib/content-editor";

afterEach(() => {
  localStorage.clear();
});

describe("applySynchronizedStateUpdate", () => {
  it("updates the mutable ref immediately so save handlers read the latest select values", () => {
    const formRef = {
      current: {
        mood: "",
        weather: "",
      },
    };

    const withMood = applySynchronizedStateUpdate(formRef, (previous) => ({
      ...previous,
      mood: "calm",
    }));
    const withWeather = applySynchronizedStateUpdate(formRef, (previous) => ({
      ...previous,
      weather: "overcast",
    }));

    expect(withMood.mood).toBe("calm");
    expect(withWeather).toEqual({
      mood: "calm",
      weather: "overcast",
    });
    expect(formRef.current).toBe(withWeather);
  });
});

describe("normalizeServerTextField", () => {
  it("preserves saved diary mood and overcast weather values from admin read responses", () => {
    expect(normalizeServerTextField("calm")).toBe("calm");
    expect(normalizeServerTextField("overcast")).toBe("overcast");
  });

  it("normalizes missing or non-string response values to an empty form value", () => {
    expect(normalizeServerTextField(null)).toBe("");
    expect(normalizeServerTextField(undefined)).toBe("");
    expect(normalizeServerTextField({ value: "overcast" })).toBe("");
  });
});

describe("editor draft snapshots", () => {
  it("keeps the last draft for each content type independently", () => {
    saveEditorDraftSnapshot({
      contentType: "diary",
      draftId: "new",
      form: { body: "第一篇日记" },
      isPublishedAtManual: false,
      isAutoTitleEnabled: true,
      sourceUpdatedAt: null,
    });
    saveEditorDraftSnapshot({
      contentType: "posts",
      draftId: "post-1",
      form: { body: "文章草稿" },
      isPublishedAtManual: true,
      isAutoTitleEnabled: false,
      sourceUpdatedAt: "2026-07-12T10:00:00+08:00",
    });
    saveEditorDraftSnapshot({
      contentType: "posts",
      draftId: "post-2",
      form: { body: "更新后的文章草稿" },
      isPublishedAtManual: false,
      isAutoTitleEnabled: false,
      sourceUpdatedAt: "2026-07-12T11:00:00+08:00",
    });

    expect(readEditorDraftSnapshot("diary", "new", null))
      .toMatchObject({ form: { body: "第一篇日记" } });
    expect(readEditorDraftSnapshot("posts", "post-1", "2026-07-12T10:00:00+08:00"))
      .toBeNull();
    expect(readEditorDraftSnapshot("posts", "post-2", "2026-07-12T11:00:00+08:00"))
      .toMatchObject({ form: { body: "更新后的文章草稿" } });
  });

  it("rejects an existing-item draft when the server version changed", () => {
    saveEditorDraftSnapshot({
      contentType: "posts",
      draftId: "post-1",
      form: { title: "本地标题" },
      isPublishedAtManual: false,
      isAutoTitleEnabled: false,
      sourceUpdatedAt: "2026-07-12T10:00:00+08:00",
    });

    expect(readEditorDraftSnapshot("posts", "post-1", "2026-07-12T11:00:00+08:00"))
      .toBeNull();
    expect(readEditorDraftSnapshot("posts", "post-1", "2026-07-12T10:00:00+08:00"))
      .toMatchObject({ form: { title: "本地标题" } });
  });

  it("clears only the draft owned by the matching editor", () => {
    saveEditorDraftSnapshot({
      contentType: "thoughts",
      draftId: "thought-1",
      form: { body: "暂存想法" },
      isPublishedAtManual: false,
      isAutoTitleEnabled: true,
      sourceUpdatedAt: "2026-07-12T10:00:00+08:00",
    });

    clearEditorDraftSnapshot("excerpts", "excerpt-1");
    expect(readEditorDraftSnapshot("thoughts", "thought-1", "2026-07-12T10:00:00+08:00"))
      .not.toBeNull();

    clearEditorDraftSnapshot("thoughts", "thought-1");
    expect(readEditorDraftSnapshot("thoughts", "thought-1", "2026-07-12T10:00:00+08:00"))
      .toBeNull();
  });

  it("ignores a damaged stored snapshot", () => {
    localStorage.setItem("aerisun-admin-editor-draft-v1:diary", "{");

    expect(readEditorDraftSnapshot("diary", "new", null)).toBeNull();
  });
});
