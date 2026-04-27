import { useEffect, useRef } from "react";
import { useTheme } from "@serino/theme";
import { useReducedMotionPreference } from "@/lib/useReducedMotion";

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
  color: string;
}

const PETAL_COUNT = {
  light: 14,
  dark: 8,
} as const;

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
    edgeColor: "rgba(120, 56, 86, 0.22)",
    highlightColor: "rgba(255, 255, 255, 0.5)",
    shadowColor: "rgba(126, 64, 92, 0.1)",
    shadowBlur: 2,
    strokeWidth: 0.42,
  },
  dark: {
    edgeColor: "rgba(255, 255, 255, 0.18)",
    highlightColor: "rgba(255, 255, 255, 0.48)",
    shadowColor: "rgba(255, 180, 205, 0.1)",
    shadowBlur: 1.4,
    strokeWidth: 0.35,
  },
} as const;

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
    const petalCount = PETAL_COUNT[theme];
    const petalVisuals = PETAL_VISUALS[theme];
    let viewportWidth = window.innerWidth;
    let viewportHeight = window.innerHeight;

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      viewportWidth = window.innerWidth;
      viewportHeight = window.innerHeight;
      canvas.width = Math.floor(viewportWidth * dpr);
      canvas.height = Math.floor(viewportHeight * dpr);
      canvas.style.width = `${viewportWidth}px`;
      canvas.style.height = `${viewportHeight}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    window.addEventListener("resize", resize);

    petalsRef.current = Array.from({ length: petalCount }, () =>
      createPetal(viewportWidth, viewportHeight, theme, petalColors, true),
    );

    const drawPetal = (petal: Petal) => {
      ctx.save();
      ctx.translate(petal.x, petal.y);
      ctx.rotate((petal.rotation * Math.PI) / 180);
      ctx.globalAlpha = petal.opacity;

      ctx.beginPath();
      ctx.moveTo(0, 0);
      ctx.bezierCurveTo(
        petal.size * 0.4,
        -petal.size * 0.3,
        petal.size * 0.8,
        -petal.size * 0.15,
        petal.size,
        0,
      );
      ctx.bezierCurveTo(
        petal.size * 0.8,
        petal.size * 0.15,
        petal.size * 0.4,
        petal.size * 0.3,
        0,
        0,
      );

      const fill = ctx.createLinearGradient(
        0,
        -petal.size * 0.34,
        petal.size,
        petal.size * 0.28,
      );
      fill.addColorStop(0, petalVisuals.highlightColor);
      fill.addColorStop(0.26, petal.color);
      fill.addColorStop(1, petal.color);

      ctx.shadowColor = petalVisuals.shadowColor;
      ctx.shadowBlur = petalVisuals.shadowBlur;
      ctx.fillStyle = fill;
      ctx.fill();
      ctx.shadowBlur = 0;
      ctx.lineWidth = petalVisuals.strokeWidth;
      ctx.strokeStyle = petalVisuals.edgeColor;
      ctx.stroke();
      ctx.restore();
    };

    const animate = () => {
      ctx.clearRect(0, 0, viewportWidth, viewportHeight);

      petalsRef.current.forEach((petal, index) => {
        petal.wobble += petal.wobbleSpeed;
        petal.x += petal.speedX + Math.sin(petal.wobble) * 0.22;
        petal.y += petal.speedY;
        petal.rotation += petal.rotationSpeed;

        if (
          petal.y > viewportHeight + 20 ||
          petal.x < -20 ||
          petal.x > viewportWidth + 20
        ) {
          petalsRef.current[index] = createPetal(
            viewportWidth,
            viewportHeight,
            theme,
            petalColors,
            false,
          );
        }

        drawPetal(petal);
      });

      animRef.current = requestAnimationFrame(animate);
    };

    animate();

    return () => {
      cancelAnimationFrame(animRef.current);
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

function createPetal(
  width: number,
  height: number,
  theme: "light" | "dark",
  petalColors: readonly string[],
  initial: boolean,
): Petal {
  const isLight = theme === "light";

  return {
    x: Math.random() * width,
    y: initial ? Math.random() * height : -8 - Math.random() * 28,
    size: isLight ? 4.6 + Math.random() * 4.2 : 4.2 + Math.random() * 4.4,
    rotation: Math.random() * 360,
    rotationSpeed: (Math.random() - 0.5) * (isLight ? 1 : 1.2),
    speedX: (Math.random() - 0.5) * (isLight ? 0.4 : 0.42),
    speedY: isLight ? 0.26 + Math.random() * 0.38 : 0.28 + Math.random() * 0.4,
    opacity: isLight
      ? 0.28 + Math.random() * 0.12
      : 0.24 + Math.random() * 0.18,
    wobble: Math.random() * Math.PI * 2,
    wobbleSpeed: isLight
      ? 0.018 + Math.random() * 0.018
      : 0.018 + Math.random() * 0.018,
    color: petalColors[Math.floor(Math.random() * petalColors.length)],
  };
}

export default FallingPetals;
