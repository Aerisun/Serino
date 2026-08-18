import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = resolve(frontendRoot, "..");
const readSource = (path) => readFileSync(resolve(repoRoot, path), "utf8");

test("shared lightbox animates between the source image and preview using compositor-only properties", () => {
  const lightbox = readSource("frontend/src/components/ImageLightbox.tsx");
  const css = readSource("frontend/src/components/ImageLightbox.css");
  const transitionKeyframes = lightbox.slice(
    lightbox.indexOf("const getTransitionKeyframes"),
    lightbox.indexOf("export default function ImageLightbox"),
  );

  assert.match(lightbox, /originImage\?: HTMLImageElement \| null;/);
  assert.match(lightbox, /useReducedMotionPreference/);
  assert.match(lightbox, /getBoundingClientRect\(\)/);
  assert.match(lightbox, /document\.createElement\("img"\)/);
  assert.match(lightbox, /pointerEvents:\s*"none"/);
  assert.match(lightbox, /willChange:\s*"transform"/);
  assert.match(lightbox, /transform:\s*`translate3d\(/);
  assert.match(lightbox, /\.animate\(/);
  assert.match(lightbox, /animation\.finished/);
  assert.match(lightbox, /animation\.cancel\(\)/);
  assert.match(lightbox, /const OPEN_TRANSITION_DURATION = 320;/);
  assert.match(lightbox, /const CLOSE_TRANSITION_DURATION = 260;/);
  assert.match(lightbox, /setOpening\(true\)/);
  assert.match(lightbox, /setPresented\(true\)/);
  assert.match(lightbox, /playImageTransition\(originImage, from, to, OPEN_TRANSITION_DURATION/);
  assert.match(lightbox, /playImageTransition\(targetImage, from, to, CLOSE_TRANSITION_DURATION/);
  assert.doesNotMatch(transitionKeyframes, /fadeAtEnd/);
  assert.doesNotMatch(transitionKeyframes, /opacity/);
  assert.doesNotMatch(transitionKeyframes, /offset:\s*0\.76/);
  assert.doesNotMatch(css, /backdrop-filter/);
  assert.match(css, /\.aerisun-image-lightbox\s*\{[^}]*isolation:\s*isolate;/);
  assert.match(css, /\.aerisun-image-lightbox::before\s*\{[^}]*opacity:\s*0;[^}]*transition:\s*opacity 180ms/);
  assert.match(css, /\.aerisun-image-lightbox\.is-presented::before\s*\{[^}]*opacity:\s*1;/);
  assert.match(css, /\.aerisun-image-lightbox\.is-closing::before\s*\{[^}]*opacity:\s*0;/);
  assert.match(css, /\.aerisun-image-lightbox__frame\s*\{[^}]*position:\s*relative;[^}]*z-index:\s*1;/);
  assert.match(css, /\.aerisun-image-lightbox__image\.is-opening\s*\{[^}]*transition:\s*none;/);
});

test("lightbox keeps the preview hidden until its backdrop has entered", () => {
  const lightbox = readSource("frontend/src/components/ImageLightbox.tsx");
  const loadHandler = lightbox.slice(
    lightbox.indexOf("const handlePreviewImageLoad"),
    lightbox.indexOf("const handlePointerDown"),
  );

  assert.match(lightbox, /const \[imageLoaded, setImageLoaded\] = useState\(false\);/);
  assert.match(lightbox, /if \(!presented \|\| !imageLoaded \|\| opening \|\| closing\) return;/);
  assert.match(loadHandler, /setImageLoaded\(true\);/);
  assert.match(lightbox, /onError=\{\(\) => setImageLoaded\(true\)\}/);
});

test("lightbox keeps surrounding content on stable compositor layers during the handoff", () => {
  const lightbox = readSource("frontend/src/components/ImageLightbox.tsx");
  const css = readSource("frontend/src/components/ImageLightbox.css");
  const loadHandler = lightbox.slice(
    lightbox.indexOf("const handlePreviewImageLoad"),
    lightbox.indexOf("const handlePointerDown"),
  );

  assert.doesNotMatch(loadHandler, /restoreOriginImage/);
  assert.match(lightbox, /hiddenOriginRef = useRef<\{ image: HTMLImageElement; opacity: string; willChange: string \} \| null>/);
  assert.match(lightbox, /image\.style\.willChange = "opacity";/);
  assert.match(lightbox, /image\.style\.opacity = "0";/);
  assert.doesNotMatch(lightbox, /image\.style\.visibility/);
  assert.match(css, /\.aerisun-image-lightbox\s*\{[^}]*contain:\s*layout paint;/);
  assert.match(css, /\.aerisun-image-lightbox::before\s*\{[^}]*will-change:\s*opacity;/);
});

test("lightbox reveals the final-size preview only after the moving image reaches it", () => {
  const lightbox = readSource("frontend/src/components/ImageLightbox.tsx");
  const loadHandler = lightbox.slice(
    lightbox.indexOf("const handlePreviewImageLoad"),
    lightbox.indexOf("const handlePointerDown"),
  );

  assert.doesNotMatch(lightbox, /IMAGE_REVEAL_DELAY/);
  assert.doesNotMatch(lightbox, /transitionDelay:/);
  assert.match(lightbox, /if \(!presented \|\| !imageLoaded \|\| opening \|\| closing\) return;/);
  assert.match(lightbox, /retainTransitionImage = false/);
  assert.match(lightbox, /if \(!retainTransitionImage\) \{\s*transitionImage\.remove\(\);/s);
  assert.match(
    loadHandler,
    /playImageTransition\(originImage, from, to, OPEN_TRANSITION_DURATION, \(\) => \{\s*setImageReady\(true\);\s*\}, true\);/s,
  );
  assert.match(
    lightbox,
    /if \(!opening \|\| !imageReady\) return;\s*removeTransitionImage\(\);\s*revealFrameRef\.current = window\.requestAnimationFrame\(\(\) => \{\s*revealFrameRef\.current = window\.requestAnimationFrame\(\(\) => \{\s*revealFrameRef\.current = null;\s*setOpening\(false\);/s,
  );
});

test("all existing lightbox entry points pass their clicked image as the animation origin", () => {
  const articleRenderer = readSource("frontend/src/components/MarkdownRenderer.tsx");
  const commentRenderer = readSource("frontend/src/components/CommentMarkdownRenderer.tsx");

  assert.match(articleRenderer, /const imageRef = useRef<HTMLImageElement \| null>\(null\);/);
  assert.match(articleRenderer, /originImage=\{imageRef\.current\}/);
  assert.match(commentRenderer, /originImage: HTMLImageElement \| null/);
  assert.match(commentRenderer, /onOpen=\{\(event\) => onImageOpen\(\s*resolvedSrc,\s*String\(alt \?\? ""\),\s*event\.currentTarget\.querySelector<HTMLImageElement>\("img"\),\s*\)\}/s);
  assert.match(commentRenderer, /originImage=\{lightboxImage\.originImage\}/);
});
