import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const readSource = (path: string) => readFileSync(new URL(path, import.meta.url), "utf8");

describe("music player UI contract", () => {
  it("keeps the desktop trigger play-pause only and reveals the title control on hover or focus", () => {
    const source = readSource("../src/components/MusicNavControl.tsx");

    expect(source).toMatch(/togglePlayback/);
    expect(source).toMatch(/onMouseEnter/);
    expect(source).toMatch(/onFocus/);
    expect(source).toMatch(/nextTrack/);
    expect(source).not.toMatch(/artist|歌手/i);
  });

  it("uses a rotating music icon and a fixed two-row overflow-aware popover", () => {
    const source = readSource("../src/components/MusicNavControl.tsx");
    const overflowSource = readSource("../src/lib/useOverflowingText.ts");
    const cssUrl = new URL("../src/components/MusicNavControl.css", import.meta.url);
    const cssExists = existsSync(fileURLToPath(cssUrl));
    const css = cssExists ? readFileSync(cssUrl, "utf8") : "";

    expect(source).toMatch(/Music2/);
    expect(source).toMatch(/music-nav-icon--playing/);
    expect(source).toMatch(/useOverflowingText/);
    expect(overflowSource).toMatch(/ResizeObserver/);
    expect(overflowSource).toMatch(/scrollWidth/);
    expect(source).toMatch(/music-nav-popover__title/);
    expect(source).toMatch(/music-nav-popover__controls/);
    expect(source).toMatch(/music-nav-popover__card--literary/);
    expect(source).not.toMatch(/border-t|border-l/);
    expect(cssExists).toBe(true);
    expect(css).toMatch(/@keyframes music-nav-spin/);
    expect(css).toMatch(/@keyframes music-nav-marquee/);
    expect(css).toMatch(/linear infinite/);
    expect(css).toMatch(/prefers-reduced-motion/);
  });

  it("puts a draggable snapping progress slider and one next-track action on the second row", () => {
    const source = readSource("../src/components/MusicNavControl.tsx");
    const contextSource = readSource("../src/contexts/music-player.ts");
    const providerSource = readSource("../src/contexts/MusicPlayerContext.tsx");

    expect(source).toMatch(/type="range"/);
    expect(source).toMatch(/seekTo/);
    expect(source).toMatch(/onChange/);
    expect(source).toMatch(/nextTrack/);
    expect(source).not.toMatch(/previousTrack/);
    expect(contextSource).toMatch(/currentTime: number/);
    expect(contextSource).toMatch(/duration: number/);
    expect(contextSource).toMatch(/seekTo: \(time: number\)/);
    expect(providerSource).toMatch(/onTimeUpdate/);
    expect(providerSource).toMatch(/onDurationChange/);
  });

  it("shows a centered neutral play hint while paused and gates the full panel behind playback", () => {
    const source = readSource("../src/components/MusicNavControl.tsx");

    expect(source).toMatch(/role="tooltip"/);
    expect(source).toMatch(/music-play-hint/);
    expect(source).toMatch(/left-1\/2/);
    expect(source).toMatch(/-translate-x-1\/2/);
    expect(source).toMatch(/x: "-50%"/);
    expect(source).toMatch(/music-play-hint__surface/);
    expect(source).toMatch(/t\("music\.play"\)/);
    expect(source).toMatch(/open && isPlaying/);
    expect(source).toMatch(/if \(!isPlaying\)[\s\S]*setOpen\(false\)/);
  });

  it("uses a compact right-side mobile capsule aligned above the article directory", () => {
    const source = readSource("../src/components/MobileMusicControl.tsx");

    expect(source).toMatch(/MOBILE_MUSIC_COLLAPSE_MS/);
    expect(source).toMatch(/safe-area-inset-right/);
    expect(source).toMatch(/data-toc-mobile-button/);
    expect(source).toMatch(/h-11 w-11/);
    expect(source).toMatch(/previousTrack/);
    expect(source).toMatch(/nextTrack/);
    expect(source).toMatch(/useOverflowingText/);
    expect(source).toMatch(/music-nav-popover__marquee/);
    expect(source).toMatch(/titleOverflowing && !prefersReducedMotion/);
    expect(source).not.toMatch(/safe-area-inset-left/);
    expect(source).not.toMatch(/artist|歌手/i);
  });

  it("mounts one provider above routed pages so route changes do not recreate audio", () => {
    const source = readSource("../src/AppRuntime.tsx");

    expect(source).toMatch(/MusicPlayerProvider/);
    expect(source).toMatch(/<MusicPlayerProvider[\s\S]*<Routes>/);
  });
});
