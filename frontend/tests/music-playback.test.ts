import { describe, expect, it } from "vitest";
import {
  MOBILE_MUSIC_COLLAPSE_MS,
  advanceRandomTrack,
  clampMusicSeekTime,
  createRandomPlaybackState,
  nextSequentialIndex,
  previousRandomTrack,
  previousSequentialIndex,
  resolveDesktopMusicOverlay,
  resolveCollapsedMusicTap,
} from "../src/lib/music-playback";
import { normalizeBackgroundMusicConfig } from "../src/lib/runtime-config";

describe("background music runtime config", () => {
  it("normalizes valid title-only tracks and disables an empty playlist", () => {
    expect(normalizeBackgroundMusicConfig(undefined)).toEqual({
      enabled: false,
      playbackMode: "sequential",
      tracks: [],
    });

    expect(normalizeBackgroundMusicConfig({
      enabled: true,
      playback_mode: "random",
      tracks: [
        { id: "track-1", title: "  晚风  ", stream_url: "/media/assets/one.mp3" },
        { id: "track-2", title: "", stream_url: "/media/assets/two.mp3" },
      ],
    })).toEqual({
      enabled: true,
      playbackMode: "random",
      tracks: [
        { id: "track-1", title: "晚风", streamUrl: "/media/assets/one.mp3" },
      ],
    });
  });
});

describe("sequential playback", () => {
  it("wraps in both directions", () => {
    expect(nextSequentialIndex(-1, 3)).toBe(0);
    expect(nextSequentialIndex(2, 3)).toBe(0);
    expect(previousSequentialIndex(0, 3)).toBe(2);
    expect(previousSequentialIndex(2, 3)).toBe(1);
  });
});

describe("shuffle bag playback", () => {
  it("does not repeat within a round or across the round boundary", () => {
    const ids = ["a", "b", "c"];
    let state = createRandomPlaybackState();
    const played: string[] = [];

    for (let index = 0; index < 4; index += 1) {
      const result = advanceRandomTrack(ids, state, () => 0);
      expect(result.trackId).not.toBeNull();
      played.push(result.trackId!);
      state = result.state;
    }

    expect(new Set(played.slice(0, 3)).size).toBe(3);
    expect(played[3]).not.toBe(played[2]);
  });

  it("uses real playback history for previous and forward navigation", () => {
    const ids = ["a", "b", "c"];
    const state = createRandomPlaybackState();
    const first = advanceRandomTrack(ids, state, () => 0);
    const second = advanceRandomTrack(ids, first.state, () => 0);
    const third = advanceRandomTrack(ids, second.state, () => 0);

    const previous = previousRandomTrack(ids, third.state);
    expect(previous.trackId).toBe(second.trackId);

    const forward = advanceRandomTrack(ids, previous.state, () => 0.9);
    expect(forward.trackId).toBe(third.trackId);
  });
});

describe("mobile collapsed control", () => {
  it("starts on the first tap, then only expands after an automatic collapse", () => {
    expect(MOBILE_MUSIC_COLLAPSE_MS).toBe(2500);
    expect(resolveCollapsedMusicTap(false)).toBe("start-and-expand");
    expect(resolveCollapsedMusicTap(true)).toBe("expand");
  });
});

describe("music seeking", () => {
  it("snaps requested progress to the playable duration", () => {
    expect(clampMusicSeekTime(24.5, 120)).toBe(24.5);
    expect(clampMusicSeekTime(-3, 120)).toBe(0);
    expect(clampMusicSeekTime(150, 120)).toBe(120);
    expect(clampMusicSeekTime(Number.NaN, 120)).toBe(0);
    expect(clampMusicSeekTime(30, Number.NaN)).toBe(0);
  });
});

describe("desktop music overlay", () => {
  it("shows the play hint while paused and the player panel only while playing", () => {
    expect(resolveDesktopMusicOverlay).toBeTypeOf("function");
    if (typeof resolveDesktopMusicOverlay !== "function") return;

    expect(resolveDesktopMusicOverlay(false, false)).toBe("none");
    expect(resolveDesktopMusicOverlay(false, true)).toBe("play-hint");
    expect(resolveDesktopMusicOverlay(true, false)).toBe("none");
    expect(resolveDesktopMusicOverlay(true, true)).toBe("player");
  });
});
