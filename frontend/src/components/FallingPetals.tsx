import { useEffect, useRef } from "react";
import { useTheme } from "@/contexts/useTheme";
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
  light: 22,
  dark: 26,
} as const;

const PETAL_COLORS = {
  light: [
    "rgb(246, 191, 205)",
    "rgb(248, 214, 198)",
    "rgb(230, 206, 241)",
    "rgb(201, 223, 238)",
    "rgb(246, 231, 191)",
    "rgb(205, 229, 210)",
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

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resize();
    window.addEventListener("resize", resize);

    petalsRef.current = Array.from({ length: petalCount }, () =>
      createPetal(canvas.width, canvas.height, theme, petalColors, true),
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

      ctx.fillStyle = petal.color;
      ctx.fill();
      ctx.restore();
    };

    const animate = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      petalsRef.current.forEach((petal, index) => {
        petal.wobble += petal.wobbleSpeed;
        petal.x += petal.speedX + Math.sin(petal.wobble) * 0.22;
        petal.y += petal.speedY;
        petal.rotation += petal.rotationSpeed;

        if (petal.y > canvas.height + 20 || petal.x < -20 || petal.x > canvas.width + 20) {
          petalsRef.current[index] = createPetal(
            canvas.width,
            canvas.height,
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
      className="fixed inset-0 pointer-events-none z-[1]"
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
    size: isLight ? 3.8 + Math.random() * 4 : 4.2 + Math.random() * 4.4,
    rotation: Math.random() * 360,
    rotationSpeed: (Math.random() - 0.5) * (isLight ? 1 : 1.2),
    speedX: (Math.random() - 0.5) * (isLight ? 0.34 : 0.42),
    speedY: isLight ? 0.24 + Math.random() * 0.34 : 0.28 + Math.random() * 0.4,
    opacity: isLight ? 0.2 + Math.random() * 0.16 : 0.24 + Math.random() * 0.18,
    wobble: Math.random() * Math.PI * 2,
    wobbleSpeed: isLight ? 0.016 + Math.random() * 0.016 : 0.018 + Math.random() * 0.018,
    color: petalColors[Math.floor(Math.random() * petalColors.length)],
  };
}

export default FallingPetals;
