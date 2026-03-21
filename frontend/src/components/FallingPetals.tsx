import { useEffect, useRef } from "react";
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

const PETAL_COUNT = 25;

const PETAL_COLORS = [
  "rgba(255, 182, 193, 0.55)",  // pink
  "rgba(255, 218, 185, 0.50)",  // peach
  "rgba(221, 160, 221, 0.45)",  // plum
  "rgba(173, 216, 230, 0.45)",  // light blue
  "rgba(255, 250, 205, 0.50)",  // lemon
  "rgba(255, 200, 200, 0.55)",  // salmon
  "rgba(200, 180, 255, 0.45)",  // lavender
  "rgba(180, 230, 200, 0.40)",  // mint
];

const FallingPetals = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const petalsRef = useRef<Petal[]>([]);
  const animRef = useRef<number>(0);
  const prefersReducedMotion = useReducedMotionPreference();

  useEffect(() => {
    if (prefersReducedMotion) return;

    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resize();
    window.addEventListener("resize", resize);

    // Initialize petals
    petalsRef.current = Array.from({ length: PETAL_COUNT }, () => createPetal(canvas.width, canvas.height, true));

    const drawPetal = (p: Petal) => {
      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.rotate((p.rotation * Math.PI) / 180);
      ctx.globalAlpha = p.opacity;

      // Draw a simple petal shape
      ctx.beginPath();
      ctx.moveTo(0, 0);
      ctx.bezierCurveTo(
        p.size * 0.4, -p.size * 0.3,
        p.size * 0.8, -p.size * 0.15,
        p.size, 0
      );
      ctx.bezierCurveTo(
        p.size * 0.8, p.size * 0.15,
        p.size * 0.4, p.size * 0.3,
        0, 0
      );

      ctx.fillStyle = p.color;
      ctx.fill();
      ctx.restore();
    };

    const animate = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      petalsRef.current.forEach((p, i) => {
        p.wobble += p.wobbleSpeed;
        p.x += p.speedX + Math.sin(p.wobble) * 0.3;
        p.y += p.speedY;
        p.rotation += p.rotationSpeed;

        // Reset when off screen
        if (p.y > canvas.height + 20 || p.x < -20 || p.x > canvas.width + 20) {
          petalsRef.current[i] = createPetal(canvas.width, canvas.height, false);
        }

        drawPetal(p);
      });

      animRef.current = requestAnimationFrame(animate);
    };

    animate();

    return () => {
      cancelAnimationFrame(animRef.current);
      window.removeEventListener("resize", resize);
    };
  }, [prefersReducedMotion]);

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

function createPetal(w: number, h: number, initial: boolean): Petal {
  return {
    x: Math.random() * w,
    y: initial ? Math.random() * h : -10 - Math.random() * 40,
    size: 3 + Math.random() * 5,
    rotation: Math.random() * 360,
    rotationSpeed: (Math.random() - 0.5) * 1.2,
    speedX: (Math.random() - 0.5) * 0.4,
    speedY: 0.25 + Math.random() * 0.45,
    opacity: 0.12 + Math.random() * 0.22,
    wobble: Math.random() * Math.PI * 2,
    wobbleSpeed: 0.02 + Math.random() * 0.02,
    color: PETAL_COLORS[Math.floor(Math.random() * PETAL_COLORS.length)],
  };
}

export default FallingPetals;
