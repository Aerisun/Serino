import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const source = readFileSync(resolve(frontendRoot, "src/components/ActivityHeatmap.tsx"), "utf8");

test("activity heatmap only animates while its chart and page are visible", () => {
  assert.match(source, /IntersectionObserver/);
  assert.match(source, /document\.addEventListener\("visibilitychange"/);
  assert.match(source, /isChartVisible/);
  assert.match(source, /isPageVisible/);
  assert.match(
    source,
    /const shouldAnimate = hasData && isChartVisible && isPageVisible && !prefersReducedMotion;/,
  );
  assert.match(source, /requestAnimationFrame\(tick\)/);
});

test("activity heatmap keeps hover overlays non-interactive without decorative particles", () => {
  assert.match(source, /DESKTOP_MOTION_QUERY/);
  assert.match(source, /const MOBILE_FRAME_INTERVAL_MS = 1000 \/ 30/);
  assert.match(source, /DESKTOP_WAVE_AMPLITUDE/);
  assert.match(source, /MOBILE_WAVE_AMPLITUDE/);
  assert.match(source, /isDesktopMotion \? DESKTOP_WAVE_AMPLITUDE : MOBILE_WAVE_AMPLITUDE/);
  assert.doesNotMatch(source, /DESKTOP_PARTICLE_COUNT/);
  assert.doesNotMatch(source, /showDesktopParticles/);
  assert.doesNotMatch(source, /waveParticles/);
  assert.doesNotMatch(source, /particlePoint/);
  assert.doesNotMatch(source, /Math\.random/);
  assert.doesNotMatch(source, /\bblobPath\b/);
  assert.match(source, /<circle\s+pointerEvents="none"/);
  assert.ok((source.match(/<g pointerEvents="none">/g) ?? []).length >= 2);
});

test("activity heatmap keeps the desktop cubic Bézier wave unrestricted", () => {
  assert.match(source, /const DESKTOP_WAVE_AMPLITUDE = 10/);
  assert.match(source, /const buildCubicBezierPath =/);
  assert.match(source, /<filter id="dotGlow" x="-150%" y="-150%" width="400%" height="400%">/);
  assert.match(source, /const p0 = points\[Math\.max\(index - 1, 0\)\]/);
  assert.match(source, /C \$\{controlPoint1X\} \$\{controlPoint1Y\}, \$\{controlPoint2X\} \$\{controlPoint2Y\}/);
  assert.match(source, /y: animatedY/);
  assert.doesNotMatch(source, /const buildMonotonePath =/);
  assert.doesNotMatch(source, /softenDownwardOvershoot/);
});

test("activity heatmap aligns its first rendered frame with the newest week", () => {
  assert.match(source, /import \{[^}]*useLayoutEffect[^}]*\} from "react"/);
  assert.match(
    source,
    /useLayoutEffect\(\(\) => \{[\s\S]*scrollLeft = viewport\.scrollWidth - viewport\.clientWidth/,
  );
  assert.match(source, /const frameId = requestAnimationFrame\(alignToNewestWeek\)/);
  assert.match(source, /return \(\) => cancelAnimationFrame\(frameId\)/);
});
