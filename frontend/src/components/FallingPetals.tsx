import { useEffect, useRef } from "react";
import { useTheme } from "@serino/theme";
import { useReducedMotionPreference } from "@/lib/useReducedMotion";

type PetalTheme = "light" | "dark";
type PetalDepth = "far" | "middle" | "near";
type PetalShape = "soft" | "tapered";

interface PetalSprite {
  canvas: HTMLCanvasElement;
  extent: number;
  originOffset: number;
}

interface Petal {
  x: number;
  y: number;
  size: number;
  rotation: number;
  rotationSpeed: number;
  speedX: number;
  speedY: number;
  opacity: number;
  wobble: number;
  wobbleSpeed: number;
  driftAmplitude: number;
  color: string;
  depth: PetalDepth;
  shape: PetalShape;
  sprite: PetalSprite;
}

const PETAL_COUNT = {
  light: {
    desktop: 10,
    mobile: 6,
  },
  dark: {
    desktop: 6,
    mobile: 4,
  },
} as const;

const PETAL_DEPTHS = {
  far: {
    sizeScale: 0.76,
    speedScale: 0.42,
    opacityScale: 0.58,
    wobbleScale: 0.46,
    driftScale: 0.5,
    rotationScale: 0.42,
  },
  middle: {
    sizeScale: 0.94,
    speedScale: 0.58,
    opacityScale: 0.88,
    wobbleScale: 0.6,
    driftScale: 0.64,
    rotationScale: 0.54,
  },
  near: {
    sizeScale: 1.08,
    speedScale: 0.7,
    opacityScale: 1.02,
    wobbleScale: 0.72,
    driftScale: 0.78,
    rotationScale: 0.66,
  },
} as const;

const PETAL_SHAPES = ["soft", "tapered"] as const;

const PETAL_COLORS = {
  light: [
    "rgb(235, 125, 156)",
    "rgb(237, 154, 118)",
    "rgb(202, 139, 228)",
    "rgb(111, 178, 214)",
    "rgb(219, 179, 88)",
    "rgb(116, 185, 137)",
  ],
  dark: [
    "rgb(255, 191, 205)",
    "rgb(255, 220, 194)",
    "rgb(229, 184, 236)",
    "rgb(183, 223, 240)",
    "rgb(255, 241, 189)",
    "rgb(192, 235, 208)",
  ],
} as const;

const PETAL_VISUALS = {
  light: {
    edgeColor: "rgba(120, 56, 86, 0.18)",
    highlightColor: "rgba(255, 255, 255, 0.52)",
    innerGlowColor: "rgba(255, 255, 255, 0.12)",
    shadowColor: "rgba(126, 64, 92, 0.12)",
    shadowBlur: 2,
    strokeWidth: 0.42,
  },
  dark: {
    edgeColor: "rgba(255, 255, 255, 0.16)",
    highlightColor: "rgba(255, 255, 255, 0.5)",
    innerGlowColor: "rgba(255, 255, 255, 0.1)",
    shadowColor: "rgba(255, 180, 205, 0.14)",
    shadowBlur: 1.4,
    strokeWidth: 0.35,
  },
} as const;

const MOBILE_PETAL_QUERY =
  "(max-width: 767px), (hover: none) and (pointer: coarse)";

type PetalVisual = (typeof PETAL_VISUALS)[PetalTheme];

export const getPetalCount = (theme: PetalTheme, isMobile: boolean) =>
  PETAL_COUNT[theme][isMobile ? "mobile" : "desktop"];

const FallingPetals = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const petalsRef = useRef<Petal[]>([]);
  const animRef = useRef<number>(0);
  const prefersReducedMotion = useReducedMotionPreference();
  const { resolvedTheme } = useTheme();

  useEffect(() => {
    if (prefersReducedMotion) return;

    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const theme = resolvedTheme;
    const petalColors = PETAL_COLORS[theme];
    const petalVisuals = PETAL_VISUALS[theme];
    const mobilePetalMedia =
      typeof window.matchMedia === "function"
        ? window.matchMedia(MOBILE_PETAL_QUERY)
        : null;
    let viewportWidth = window.innerWidth;
    let viewportHeight = window.innerHeight;
    let renderScale = 1;
    let isPageActive = !document.hidden;
    let isCanvasVisible = true;
    let disposed = false;

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const shouldRefreshSprites = renderScale !== dpr;
      renderScale = dpr;
      viewportWidth = window.innerWidth;
      viewportHeight = window.innerHeight;
      canvas.width = Math.floor(viewportWidth * dpr);
      canvas.height = Math.floor(viewportHeight * dpr);
      canvas.style.width = `${viewportWidth}px`;
      canvas.style.height = `${viewportHeight}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.imageSmoothingEnabled = true;
      ctx.imageSmoothingQuality = "high";

      if (shouldRefreshSprites) {
        petalsRef.current.forEach((petal) => {
          petal.sprite = createPetalSprite(petal, petalVisuals, renderScale);
        });
      }
    };
    resize();
    window.addEventListener("resize", resize);

    const resetPetals = () => {
      const petalCount = getPetalCount(theme, mobilePetalMedia?.matches ?? false);
      petalsRef.current = Array.from({ length: petalCount }, (_, index) =>
        createPetal(
          viewportWidth,
          viewportHeight,
          theme,
          petalColors,
          petalVisuals,
          renderScale,
          petalDepthForIndex(index, petalCount),
          true,
        ),
      );
    };
    resetPetals();

    const handlePetalDensityChange = () => {
      const nextPetalCount = getPetalCount(theme, mobilePetalMedia?.matches ?? false);
      if (petalsRef.current.length !== nextPetalCount) {
        resetPetals();
      }
    };

    if (mobilePetalMedia) {
      if (typeof mobilePetalMedia.addEventListener === "function") {
        mobilePetalMedia.addEventListener("change", handlePetalDensityChange);
      } else {
        mobilePetalMedia.addListener(handlePetalDensityChange);
      }
    }

    const drawPetal = (petal: Petal) => {
      ctx.save();
      ctx.translate(petal.x, petal.y);
      ctx.rotate((petal.rotation * Math.PI) / 180);
      ctx.globalAlpha = petal.opacity;
      ctx.drawImage(
        petal.sprite.canvas,
        -petal.sprite.originOffset,
        -petal.sprite.originOffset,
        petal.sprite.extent,
        petal.sprite.extent,
      );
      ctx.restore();
    };

    const canAnimate = () =>
      !disposed && isPageActive && !document.hidden && isCanvasVisible;

    const stopAnimation = () => {
      if (animRef.current === 0) return;
      cancelAnimationFrame(animRef.current);
      animRef.current = 0;
    };

    const animate = () => {
      animRef.current = 0;
      if (!canAnimate()) return;

      ctx.clearRect(0, 0, viewportWidth, viewportHeight);

      petalsRef.current.forEach((petal, index) => {
        petal.wobble += petal.wobbleSpeed;
        petal.x += petal.speedX + Math.sin(petal.wobble) * petal.driftAmplitude;
        petal.y += petal.speedY;
        petal.rotation += petal.rotationSpeed;

        let activePetal = petal;
        if (
          petal.y > viewportHeight + 20 ||
          petal.x < -20 ||
          petal.x > viewportWidth + 20
        ) {
          activePetal = createPetal(
            viewportWidth,
            viewportHeight,
            theme,
            petalColors,
            petalVisuals,
            renderScale,
            petal.depth,
            false,
          );
          petalsRef.current[index] = activePetal;
        }

        drawPetal(activePetal);
      });

      animRef.current = requestAnimationFrame(animate);
    };

    const syncAnimation = () => {
      if (!canAnimate()) {
        stopAnimation();
        return;
      }

      if (animRef.current === 0) {
        animRef.current = requestAnimationFrame(animate);
      }
    };

    const handleVisibilityChange = () => {
      isPageActive = !document.hidden;
      syncAnimation();
    };
    const handlePageHide = () => {
      isPageActive = false;
      syncAnimation();
    };
    const handlePageShow = () => {
      isPageActive = !document.hidden;
      syncAnimation();
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);
    window.addEventListener("pagehide", handlePageHide);
    window.addEventListener("pageshow", handlePageShow);

    const intersectionObserver =
      typeof IntersectionObserver === "undefined"
        ? null
        : new IntersectionObserver(([entry]) => {
            isCanvasVisible = entry?.isIntersecting ?? true;
            syncAnimation();
          });
    intersectionObserver?.observe(canvas);

    syncAnimation();

    return () => {
      disposed = true;
      stopAnimation();
      intersectionObserver?.disconnect();
      if (mobilePetalMedia) {
        if (typeof mobilePetalMedia.removeEventListener === "function") {
          mobilePetalMedia.removeEventListener("change", handlePetalDensityChange);
        } else {
          mobilePetalMedia.removeListener(handlePetalDensityChange);
        }
      }
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      window.removeEventListener("pagehide", handlePageHide);
      window.removeEventListener("pageshow", handlePageShow);
      window.removeEventListener("resize", resize);
    };
  }, [prefersReducedMotion, resolvedTheme]);

  if (prefersReducedMotion) {
    return null;
  }

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 pointer-events-none z-0"
      aria-hidden="true"
    />
  );
};

function petalDepthForIndex(index: number, count: number): PetalDepth {
  const farCount = Math.max(1, Math.round(count * 0.25));
  const nearCount = Math.max(1, Math.round(count * 0.24));

  if (index < farCount) return "far";
  if (index >= count - nearCount) return "near";
  return "middle";
}

function createPetal(
  width: number,
  height: number,
  theme: PetalTheme,
  petalColors: readonly string[],
  petalVisuals: PetalVisual,
  renderScale: number,
  depth: PetalDepth,
  initial: boolean,
): Petal {
  const isLight = theme === "light";
  const depthVisual = PETAL_DEPTHS[depth];
  const baseSize = isLight ? 4.6 + Math.random() * 4.2 : 4.2 + Math.random() * 4.4;
  const baseOpacity = isLight
    ? 0.28 + Math.random() * 0.12
    : 0.24 + Math.random() * 0.18;
  const shape = PETAL_SHAPES[Math.floor(Math.random() * PETAL_SHAPES.length)];

  const petal = {
    x: Math.random() * width,
    y: initial ? Math.random() * height : -8 - Math.random() * 28,
    size: baseSize * depthVisual.sizeScale,
    rotation: Math.random() * 360,
    rotationSpeed:
      (Math.random() - 0.5) * (isLight ? 1 : 1.2) * depthVisual.rotationScale,
    speedX: (Math.random() - 0.5) * (isLight ? 0.4 : 0.42) * depthVisual.speedScale,
    speedY:
      (isLight ? 0.26 + Math.random() * 0.38 : 0.28 + Math.random() * 0.4) *
      depthVisual.speedScale,
    opacity: Math.min(0.44, baseOpacity * depthVisual.opacityScale),
    wobble: Math.random() * Math.PI * 2,
    wobbleSpeed:
      (0.012 + Math.random() * 0.012) * depthVisual.wobbleScale,
    driftAmplitude: 0.16 * depthVisual.driftScale,
    color: petalColors[Math.floor(Math.random() * petalColors.length)],
    depth,
    shape,
  };

  return {
    ...petal,
    sprite: createPetalSprite(petal, petalVisuals, renderScale),
  };
}

function createPetalSprite(
  petal: Pick<Petal, "size" | "color" | "depth" | "shape">,
  petalVisuals: PetalVisual,
  renderScale: number,
): PetalSprite {
  const originOffset = Math.max(
    3,
    (petalVisuals.shadowBlur * 2 + petalVisuals.strokeWidth + 1.5) / renderScale,
  );
  const extent = petal.size + originOffset * 2;
  const sprite = document.createElement("canvas");
  sprite.width = Math.ceil(extent * renderScale);
  sprite.height = Math.ceil(extent * renderScale);

  const spriteContext = sprite.getContext("2d");
  if (!spriteContext) {
    return { canvas: sprite, extent, originOffset };
  }

  spriteContext.setTransform(renderScale, 0, 0, renderScale, 0, 0);
  spriteContext.translate(originOffset, originOffset);
  drawPetalPath(spriteContext, petal.size, petal.shape);

  const fill = spriteContext.createLinearGradient(
    petal.size * 0.06,
    -petal.size * 0.42,
    petal.size,
    petal.size * 0.34,
  );
  fill.addColorStop(0, petalVisuals.highlightColor);
  fill.addColorStop(0.2, petal.color);
  fill.addColorStop(0.78, petal.color);
  fill.addColorStop(1, petal.color);

  spriteContext.shadowColor = petalVisuals.shadowColor;
  spriteContext.shadowBlur = petalVisuals.shadowBlur;
  spriteContext.fillStyle = fill;
  spriteContext.fill();
  spriteContext.shadowBlur = 0;

  const innerGlow = spriteContext.createRadialGradient(
    petal.size * 0.38,
    -petal.size * 0.06,
    0,
    petal.size * 0.46,
    0,
    petal.size * 0.72,
  );
  innerGlow.addColorStop(0, petalVisuals.innerGlowColor);
  innerGlow.addColorStop(0.72, "rgba(255, 255, 255, 0)");
  spriteContext.fillStyle = innerGlow;
  spriteContext.fill();

  spriteContext.lineWidth = petalVisuals.strokeWidth;
  spriteContext.strokeStyle = petalVisuals.edgeColor;
  spriteContext.stroke();

  return { canvas: sprite, extent, originOffset };
}

function drawPetalPath(
  context: CanvasRenderingContext2D,
  size: number,
  shape: PetalShape,
) {
  context.beginPath();
  context.moveTo(0, 0);

  if (shape === "tapered") {
    context.bezierCurveTo(
      size * 0.3,
      -size * 0.4,
      size * 0.78,
      -size * 0.22,
      size,
      0,
    );
    context.bezierCurveTo(
      size * 0.76,
      size * 0.26,
      size * 0.28,
      size * 0.38,
      0,
      0,
    );
    return;
  }

  context.bezierCurveTo(
    size * 0.36,
    -size * 0.36,
    size * 0.82,
    -size * 0.24,
    size,
    0,
  );
  context.bezierCurveTo(
    size * 0.8,
    size * 0.28,
    size * 0.34,
    size * 0.4,
    0,
    0,
  );
}

export default FallingPetals;
