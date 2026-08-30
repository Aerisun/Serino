import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

interface TransitionFrame {
  transform: string;
  clipPath: string;
}

interface TransitionModule {
  buildImageTransitionKeyframes: (input: {
    originRect: { left: number; top: number; width: number; height: number };
    previewRect: { left: number; top: number; width: number; height: number };
    objectPosition: string;
    originBorderRadius: number;
    previewBorderRadius: number;
  }) => { open: [TransitionFrame, TransitionFrame]; close: [TransitionFrame, TransitionFrame] } | null;
  buildInterruptedCloseTransition: (input: {
    currentFrame: TransitionFrame;
    originFrame: TransitionFrame;
    openProgress: number | null;
    fullDuration: number;
  }) => { keyframes: [TransitionFrame, TransitionFrame]; duration: number };
  parseObjectPosition: (value: string) => { x: number; y: number };
}

const transitionModulePath = "../src/lib/" + "image-lightbox-transition";

const loadTransitionModule = async () => {
  try {
    return await import(/* @vite-ignore */ transitionModulePath) as TransitionModule;
  } catch {
    return null;
  }
};

const centeredCropInput = {
  originRect: { left: 100, top: 200, width: 300, height: 300 },
  previewRect: { left: 50, top: 50, width: 800, height: 400 },
  objectPosition: "50% 50%",
  originBorderRadius: 12,
  previewBorderRadius: 10,
};

describe("image lightbox crop transition", () => {
  it("continuously reveals a centered cover crop without stretching the image", async () => {
    const transition = await loadTransitionModule();

    expect(transition, "the crop-transition module should exist").not.toBeNull();
    if (!transition) return;

    const keyframes = transition.buildImageTransitionKeyframes(centeredCropInput);

    expect(keyframes?.open).toEqual([
      {
        transform: "translate3d(-100px, 150px, 0) scale(0.75)",
        clipPath: "inset(0px 200px 0px 200px round 16px)",
      },
      {
        transform: "translate3d(0px, 0px, 0) scale(1)",
        clipPath: "inset(0px 0px 0px 0px round 10px)",
      },
    ]);
    expect(keyframes?.close).toEqual([...keyframes!.open].reverse());
    expect(keyframes?.open[0].transform).not.toMatch(/scale\([^,)]+,/);
  });

  it("preserves non-centered object positions while the crop opens", async () => {
    const transition = await loadTransitionModule();
    expect(transition).not.toBeNull();
    if (!transition) return;

    const keyframes = transition.buildImageTransitionKeyframes({
      ...centeredCropInput,
      objectPosition: "25% 75%",
    });

    expect(keyframes?.open[0]).toEqual({
      transform: "translate3d(-25px, 150px, 0) scale(0.75)",
      clipPath: "inset(0px 300px 0px 100px round 16px)",
    });
  });

  it("parses common CSS object-position values and falls back to center", async () => {
    const transition = await loadTransitionModule();
    expect(transition).not.toBeNull();
    if (!transition) return;

    expect(transition.parseObjectPosition("left top")).toEqual({ x: 0, y: 0 });
    expect(transition.parseObjectPosition("right bottom")).toEqual({ x: 1, y: 1 });
    expect(transition.parseObjectPosition("center")).toEqual({ x: 0.5, y: 0.5 });
    expect(transition.parseObjectPosition("not-a-position")).toEqual({ x: 0.5, y: 0.5 });
  });

  it("rejects invalid source or preview geometry", async () => {
    const transition = await loadTransitionModule();
    expect(transition).not.toBeNull();
    if (!transition) return;

    expect(transition.buildImageTransitionKeyframes({
      ...centeredCropInput,
      originRect: { ...centeredCropInput.originRect, width: 0 },
    })).toBeNull();
    expect(transition.buildImageTransitionKeyframes({
      ...centeredCropInput,
      previewRect: { ...centeredCropInput.previewRect, height: Number.NaN },
    })).toBeNull();
  });

  it("continues an interrupted close from the currently rendered frame", async () => {
    const transition = await loadTransitionModule();
    expect(transition).not.toBeNull();
    if (!transition) return;

    const currentFrame = {
      transform: "matrix(1.3, 0, 0, 1.3, -120, -20)",
      clipPath: "inset(0px 140px)",
    };
    const originFrame = {
      transform: "translate3d(-180px, 40px, 0) scale(1.6)",
      clipPath: "inset(0px 280px)",
    };

    expect(transition.buildInterruptedCloseTransition({
      currentFrame,
      originFrame,
      openProgress: 0.4,
      fullDuration: 220,
    })).toEqual({
      keyframes: [currentFrame, originFrame],
      duration: 88,
    });
  });

  it("wires the tested crop morph into the shared lightbox transition layer", () => {
    const lightboxSource = readFileSync(
      new URL("../src/components/ImageLightbox.tsx", import.meta.url),
      "utf8",
    );

    expect(lightboxSource).toContain("buildImageTransitionKeyframes");
    expect(lightboxSource).toContain("buildInterruptedCloseTransition");
    expect(lightboxSource).toMatch(/willChange:\s*"transform, clip-path"/);
    expect(lightboxSource).toMatch(/clipPath:\s*initialFrame\.clipPath/);
    expect(lightboxSource).not.toMatch(/scale\(\$\{scaleX\}, \$\{scaleY\}\)/);

    const openDuration = Number(
      lightboxSource.match(/OPEN_TRANSITION_DURATION\s*=\s*(\d+)/)?.[1],
    );
    const closeDuration = Number(
      lightboxSource.match(/CLOSE_TRANSITION_DURATION\s*=\s*(\d+)/)?.[1],
    );
    expect(openDuration).toBeLessThan(300);
    expect(closeDuration).toBeLessThan(openDuration);
  });

  it("reveals the caption only after the image settles and hides it promptly on close", () => {
    const lightboxSource = readFileSync(
      new URL("../src/components/ImageLightbox.tsx", import.meta.url),
      "utf8",
    );
    const lightboxStyles = readFileSync(
      new URL("../src/components/ImageLightbox.css", import.meta.url),
      "utf8",
    );

    expect(lightboxSource).toMatch(
      /aerisun-image-lightbox__caption \$\{imageReady && !closing \? "is-visible" : ""\}/,
    );
    expect(lightboxStyles).toMatch(
      /\.aerisun-image-lightbox__caption\s*\{[\s\S]*?opacity:\s*0;[\s\S]*?translate3d\(0,\s*0\.25rem,\s*0\)/,
    );
    expect(lightboxStyles).toMatch(
      /\.aerisun-image-lightbox__caption\.is-visible\s*\{[\s\S]*?opacity:\s*1;[\s\S]*?translate3d\(0,\s*0,\s*0\)/,
    );
    expect(lightboxStyles).toMatch(
      /prefers-reduced-motion:\s*reduce[\s\S]*?aerisun-image-lightbox__caption/,
    );
  });
});
