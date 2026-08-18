import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = resolve(frontendRoot, "..");
const readSource = (path) => readFileSync(resolve(repoRoot, path), "utf8");

test("Markdown directives replace gallery and grid with underline, thumb and carousel", () => {
  const directives = readSource("frontend/src/components/markdown-directives.ts");

  assert.match(directives, /case "underline":/);
  assert.match(directives, /case "thumb":/);
  assert.match(directives, /case "thumbnail":/);
  assert.match(directives, /case "carousel":/);
  assert.match(directives, /"data-md-kind": "underline"/);
  assert.match(directives, /"data-md-kind": "thumbnail"/);
  assert.match(directives, /"data-md-kind": "carousel"/);
  assert.doesNotMatch(directives, /case "gallery":/);
  assert.doesNotMatch(directives, /case "grid":/);
});

test("article Markdown renders the new directive components", () => {
  const renderer = readSource("frontend/src/components/MarkdownRenderer.tsx");
  const carousel = readSource("frontend/src/components/MarkdownCarousel.tsx");

  assert.match(renderer, /function MarkdownUnderline/);
  assert.match(renderer, /function MarkdownThumbnailBlock/);
  assert.match(renderer, /function MarkdownCarouselBlock/);
  assert.match(renderer, /props\["data-md-kind"\] === "underline"/);
  assert.match(renderer, /kind === "thumbnail"/);
  assert.match(renderer, /kind === "carousel"/);
  assert.match(renderer, /import MarkdownCarousel/);
  assert.match(carousel, /onTouchStart/);
  assert.match(carousel, /onTouchEnd/);
  assert.match(carousel, /ArrowLeft/);
  assert.match(carousel, /ArrowRight/);
  assert.match(carousel, /const \[direction, setDirection\] = useState/);
  assert.match(carousel, /is-entering-\$\{direction/);
  assert.match(carousel, /markdown-carousel-controls/);
  assert.doesNotMatch(renderer, /function MarkdownGalleryBlock/);
  assert.doesNotMatch(renderer, /function MarkdownGridBlock/);
});

test("thumbnail directive crops a compact image while preserving the existing image viewer", () => {
  const css = readSource("frontend/src/components/markdown.css");
  const adminDirectives = readSource("admin/src/components/markdown-directives.ts");
  const adminPreview = readSource("admin/src/components/MarkdownPreview.tsx");

  assert.match(css, /\.prose \.markdown-thumbnail\s*\{/);
  assert.match(css, /\.prose \.markdown-thumbnail\s*\{[^}]*?width:\s*min\(100%, 26rem\);/);
  assert.match(css, /\.markdown-thumbnail \.markdown-figure-button\s*\{[\s\S]*?aspect-ratio:\s*4\s*\/\s*3;/);
  assert.match(css, /\.markdown-thumbnail \.markdown-figure-image\s*\{[\s\S]*?object-fit:\s*cover;/);
  assert.match(css, /@media \(max-width: 640px\) \{[\s\S]*?\.prose \.markdown-thumbnail\s*\{[\s\S]*?width:\s*min\(21rem,\s*calc\(100%\s*-\s*3rem\)\);/);
  assert.match(adminDirectives, /name === "thumb" \|\| name === "thumbnail"/);
  assert.match(adminPreview, /function MarkdownPreviewThumbnail/);
  assert.match(adminPreview, /=== "thumbnail"/);
});

test("carousel follows a horizontal touch drag and settles with a swipe or rebound", () => {
  const carousel = readSource("frontend/src/components/MarkdownCarousel.tsx");
  const css = readSource("frontend/src/components/markdown.css");

  assert.match(carousel, /const \[isDragging, setIsDragging\] = useState\(false\)/);
  assert.match(carousel, /onTouchMove=/);
  assert.match(carousel, /onTouchCancel=/);
  assert.match(carousel, /Math\.abs\(deltaX\) >= 56/);
  assert.match(carousel, /Math\.abs\(velocity\) > 0\.35/);
  assert.match(carousel, /--markdown-carousel-drag-x/);
  assert.match(css, /\.prose \.markdown-carousel\.is-dragging \.markdown-carousel-slide\s*\{[\s\S]*?transition:\s*none;/);
  assert.match(css, /translate3d\(var\(--markdown-carousel-drag-x\), 0, 0\)/);
  assert.match(css, /cubic-bezier\(0\.22, 1, 0\.36, 1\)/);
});

test("carousel keeps an outgoing layer while circularly entering the next or previous image", () => {
  const carousel = readSource("frontend/src/components/MarkdownCarousel.tsx");
  const css = readSource("frontend/src/components/markdown.css");

  assert.match(carousel, /const \[leavingSlide, setLeavingSlide\] = useState<CarouselTransition \| null>\(null\)/);
  assert.match(carousel, /setLeavingSlide\(\{ index: activeIndex, direction: nextDirection \}\)/);
  assert.match(carousel, /className="markdown-carousel-slide is-leaving"/);
  assert.match(carousel, /onAnimationEnd=\{\(event\) => \{/);
  assert.match(css, /@keyframes markdown-carousel-leave-forward/);
  assert.match(css, /@keyframes markdown-carousel-leave-backward/);
});

test("carousel preloads only nearby images during browser idle time", () => {
  const carousel = readSource("frontend/src/components/MarkdownCarousel.tsx");

  assert.match(carousel, /import \{ scheduleIdleTask, shouldBackgroundPrefetch \} from "@\/lib\/idle"/);
  assert.match(carousel, /const carouselImageSources = useMemo/);
  assert.match(carousel, /if \(!shouldBackgroundPrefetch\(\) \|\| total === 0\) return;/);
  assert.match(carousel, /scheduleIdleTask\(\(\) => \{/);
  assert.match(carousel, /preloadCarouselImage\(src\)/);
  assert.match(carousel, /image\.decode\(\)/);
  assert.match(carousel, /new Set(?:<number>)?\(\[activeIndex, nextIndex, followingIndex, previousIndex, earlierIndex\]\)/);
});

test("carousel splits image-only custom Markdown paragraphs into individual cards", () => {
  const carousel = readSource("frontend/src/components/MarkdownCarousel.tsx");

  assert.doesNotMatch(carousel, /child\.type === "p"/);
  assert.match(carousel, /isValidElement<\{ children\?: ReactNode \}>\(child\)/);
  assert.match(carousel, /!containsText && paragraphChildren\.length > 0/);
});

test("carousel shows the active image description instead of a gallery heading", () => {
  const carousel = readSource("frontend/src/components/MarkdownCarousel.tsx");
  const css = readSource("frontend/src/components/markdown.css");

  assert.match(carousel, /const activeDescription = getCarouselImageDescription\(items\[activeIndex\]\)/);
  assert.match(carousel, /className="markdown-carousel-description"/);
  assert.match(carousel, /typeof child\.props\.title === "string"/);
  assert.doesNotMatch(carousel, /markdown-carousel-title/);
  assert.match(css, /\.prose \.markdown-carousel-description\s*\{[^}]*text-align:\s*center;/);
  assert.doesNotMatch(css, /\.prose \.markdown-carousel-title/);
});

test("carousel syntax keeps descriptions on each image instead of accepting a gallery title", () => {
  const directives = readSource("frontend/src/components/markdown-directives.ts");
  const renderer = readSource("frontend/src/components/MarkdownRenderer.tsx");
  const carousel = readSource("frontend/src/components/MarkdownCarousel.tsx");
  const adminDirectives = readSource("admin/src/components/markdown-directives.ts");
  const adminPreview = readSource("admin/src/components/MarkdownPreview.tsx");
  const carouselDirectiveBlock = directives.slice(
    directives.indexOf('case "carousel":'),
    directives.indexOf('case "tabs":'),
  );
  const adminCarouselDirectiveBlock = adminDirectives.slice(
    adminDirectives.indexOf('if (name === "carousel")'),
    adminDirectives.indexOf("}", adminDirectives.indexOf('if (name === "carousel")')),
  );

  assert.doesNotMatch(carouselDirectiveBlock, /"data-md-title"/);
  assert.match(renderer, /function MarkdownCarouselBlock\(\{ children \}: \{ children: ReactNode \}\)/);
  assert.doesNotMatch(carousel, /titleLabel/);
  assert.doesNotMatch(adminCarouselDirectiveBlock, /"data-md-title"/);
  assert.match(adminPreview, /return <MarkdownPreviewCarousel>\{children\}<\/MarkdownPreviewCarousel>;/);
});

test("carousel moves its active description without changing the visual stack", () => {
  const carousel = readSource("frontend/src/components/MarkdownCarousel.tsx");
  const css = readSource("frontend/src/components/markdown.css");

  assert.match(css, /\.prose \.markdown-carousel\s*\{/);
  assert.doesNotMatch(carousel, /markdown-carousel-layout/);
  assert.match(css, /\.prose \.markdown-carousel-description\s*\{[^}]*position:\s*relative;[^}]*left:\s*-1\.45rem;[^}]*text-align:\s*center;/);
  assert.match(css, /\.prose \.markdown-carousel-stage\s*\{[^}]*width:\s*min\(100%,\s*32rem\);[^}]*margin:\s*0 auto;/);
  assert.match(css, /\.prose \.markdown-carousel-slide\s*\{[\s\S]*?position:\s*absolute;[\s\S]*?inset:\s*0\s+2\.9rem\s+1\.35rem\s+0;/);
  assert.match(css, /\.prose \.markdown-carousel-slide,\s*\.prose \.markdown-carousel-preview\s*\{[\s\S]*?border:\s*0;[\s\S]*?background:\s*transparent;[\s\S]*?box-shadow:\s*none;/);
  assert.match(css, /\.markdown-carousel-preview\[data-depth="1"\]\s*\{[\s\S]*?rotate\(1\.4deg\)/);
  assert.match(css, /@keyframes markdown-carousel-enter-forward/);
  assert.match(css, /\.prose \.markdown-carousel-controls\s*\{/);
  assert.match(css, /\.prose \.markdown-carousel-slide \.markdown-figure-image,\s*\.prose \.markdown-carousel-preview \.markdown-figure-image\s*\{[^}]*width:\s*100%;[^}]*max-width:\s*none;[^}]*height:\s*100%;[^}]*max-height:\s*none;[^}]*object-fit:\s*cover;[^}]*object-position:\s*center;/);
  assert.match(css, /touch-action:\s*pan-y;/);
  assert.match(css, /\.prose \.markdown-carousel-control:focus-visible/);
  assert.match(css, /@media \(prefers-reduced-motion: reduce\)/);
  assert.match(css, /@media \(max-width: 640px\)/);
  assert.match(css, /@media \(max-width: 640px\) \{[\s\S]*?\.prose \.markdown-carousel-description\s*\{[\s\S]*?left:\s*-0\.6rem;/);
  assert.match(css, /@media \(max-width: 640px\) \{[\s\S]*?\.prose \.markdown-carousel-stage\s*\{[\s\S]*?width:\s*min\(19\.5rem,\s*calc\(100%\s*-\s*3rem\)\);/);
  assert.match(css, /@media \(max-width: 640px\) \{[\s\S]*?\.prose \.markdown-carousel-slide\s*\{[\s\S]*?border-radius:\s*min\(0\.75rem, 2\.4%\);/);
  assert.match(css, /@media \(max-width: 640px\) \{[\s\S]*?\.prose \.markdown-carousel-footer\s*\{[\s\S]*?align-items:\s*center;/);
  assert.match(css, /@media \(max-width: 640px\) \{[\s\S]*?\.prose \.markdown-carousel-control\s*\{[\s\S]*?border:\s*0;[\s\S]*?background:\s*transparent;/);
  assert.doesNotMatch(css, /\.markdown-gallery/);
  assert.doesNotMatch(css, /\.markdown-grid/);
});

test("article Markdown images reuse the shared lightbox with the established viewport and gesture behavior", () => {
  const renderer = readSource("frontend/src/components/MarkdownRenderer.tsx");
  const css = readSource("frontend/src/components/ImageLightbox.css");
  const lightbox = readSource("frontend/src/components/ImageLightbox.tsx");

  assert.match(renderer, /import ImageLightbox from "@\/components\/ImageLightbox"/);
  assert.match(renderer, /<ImageLightbox[\s\S]*?src=\{resolvedSrc\}[\s\S]*?caption=\{caption\}/);
  assert.doesNotMatch(renderer, /viewerOverlayRef/);
  assert.doesNotMatch(renderer, /handleNativeViewerWheel/);
  assert.doesNotMatch(renderer, /createPortal/);
  assert.doesNotMatch(renderer, /markdown-image-lightbox/);
  assert.match(lightbox, /const originalOverflow = document\.body\.style\.overflow/);
  assert.match(lightbox, /document\.body\.style\.overflow = originalOverflow/);
  assert.match(lightbox, /addEventListener\("wheel", handleWheel, \{ passive: false \}\)/);
  assert.match(lightbox, /event\.ctrlKey[\s\S]*event\.metaKey/);
  assert.match(lightbox, /onPointerDown=\{handlePointerDown\}/);
  assert.match(lightbox, /onPointerMove=\{handlePointerMove\}/);
  assert.match(lightbox, /onPointerUp=\{handlePointerEnd\}/);
  assert.match(lightbox, /onClick=\{requestClose\}/);
  assert.match(lightbox, /onCloseRef\.current\(\)/);
  assert.match(css, /\.aerisun-image-lightbox::before\s*\{[^}]*?background:\s*rgb\(15 23 42 \/ 0\.46\);[^}]*?opacity:\s*0;/);
  assert.match(css, /\.aerisun-image-lightbox__frame\s*\{[\s\S]*?max-width:\s*min\(92vw, 1080px\);/);
  assert.match(css, /\.aerisun-image-lightbox__viewport\s*\{[\s\S]*?max-height:\s*min\([\s\S]*?920px/);
  assert.match(css, /\.aerisun-image-lightbox__viewport\s*\{[^}]*?touch-action:\s*none;/);
  assert.match(css, /\.aerisun-image-lightbox__image\s*\{[\s\S]*?max-width:\s*min\(92vw, 1080px\);/);
  assert.match(css, /\.aerisun-image-lightbox__image\.is-zoomed\s*\{[\s\S]*?cursor:\s*grab;/);
  assert.match(css, /\.aerisun-image-lightbox__image\.is-dragging\s*\{[^}]*?transition:\s*none;/);
  assert.match(css, /\.aerisun-image-lightbox__image\s*\{[^}]*?-webkit-user-drag:\s*none;/);
});

test("comment-oriented Markdown hides lightbox captions without changing the default", () => {
  const commentRenderer = readSource("frontend/src/components/CommentMarkdownRenderer.tsx");
  const articleRenderer = readSource("frontend/src/components/MarkdownRenderer.tsx");
  const lightbox = readSource("frontend/src/components/ImageLightbox.tsx");

  assert.match(lightbox, /showCaption\?: boolean;/);
  assert.match(lightbox, /showCaption = true/);
  assert.match(lightbox, /showCaption && text/);
  assert.match(commentRenderer, /<ImageLightbox[\s\S]*?showCaption=\{false\}/);
  assert.doesNotMatch(articleRenderer, /showCaption=\{false\}/);
});

test("shared lightbox batches gesture transforms to animation frames and only promotes zoomed images", () => {
  const css = readSource("frontend/src/components/ImageLightbox.css");
  const lightbox = readSource("frontend/src/components/ImageLightbox.tsx");
  const baseImageRule = css.match(/\.aerisun-image-lightbox__image\s*\{([^}]*)\}/)?.[1] ?? "";

  assert.match(lightbox, /window\.requestAnimationFrame/);
  assert.match(lightbox, /window\.cancelAnimationFrame/);
  assert.match(lightbox, /const scheduleTransform/);
  assert.match(lightbox, /scheduleTransform\(nextZoom, nextOffset\)/);
  assert.doesNotMatch(baseImageRule, /will-change:/);
  assert.match(css, /\.aerisun-image-lightbox__image\.is-zoomed\s*\{[^}]*will-change:\s*transform;/);
});

test("embedded Markdown images use proportionate corners for narrow uploads", () => {
  const css = readSource("frontend/src/components/markdown.css");

  assert.match(css, /\.prose \.markdown-figure-image\s*\{[\s\S]*?border-radius:\s*min\(1\.1rem, 10%\);/);
});

test("embedded Markdown images keep a readable desktop width instead of filling the article", () => {
  const css = readSource("frontend/src/components/markdown.css");

  assert.match(
    css,
    /\.prose \.markdown-figure\s*\{[\s\S]*?max-width:\s*min\(100%, 48rem\);/,
  );
});

test("thoughts and excerpts retain the original attachment-grid Markdown renderer", () => {
  const commentRenderer = readSource("frontend/src/components/CommentMarkdownRenderer.tsx");
  const imageAttachments = readSource("frontend/src/lib/markdown-images.ts");

  assert.match(commentRenderer, /import remarkDirective from "remark-directive"/);
  assert.match(commentRenderer, /remarkAerisunIndentDirectives/);
  assert.match(
    commentRenderer,
    /remarkPlugins=\{\[[\s\S]*remarkGfm,[\s\S]*remarkMath,[\s\S]*remarkDirective,[\s\S]*remarkAerisunIndentDirectives,[\s\S]*\]\}/,
  );
  assert.match(commentRenderer, /import ImageLightbox from "@\/components\/ImageLightbox"/);
  assert.match(commentRenderer, /<ImageLightbox/);
  assert.doesNotMatch(commentRenderer, /aerisun-comment-image-lightbox__close/);
  assert.doesNotMatch(commentRenderer, /remarkAerisunDirectives/);
  assert.doesNotMatch(commentRenderer, /MarkdownCarousel/);
  assert.doesNotMatch(imageAttachments, /isCarouselDirectiveStart/);
  assert.doesNotMatch(imageAttachments, /carouselDirectiveDepth/);
});
