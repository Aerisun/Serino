import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import {
  RetryableAvatarImage,
  buildRetryableImageSrc,
  retryDelayForAttempt,
} from "../src/components/RetryableAvatarImage";

describe("retryable avatar image URLs", () => {
  it("keeps the original avatar URL on the first load", () => {
    const src = "/api/v1/avatars/10.x/notionists/svg?seed=55fc3d39";

    expect(buildRetryableImageSrc(src, 0)).toBe(src);
  });

  it("retries local avatar SVGs while preserving the seed", () => {
    const src = "/api/v1/avatars/10.x/notionists/svg?seed=55fc3d39";
    const retried = buildRetryableImageSrc(src, 2);

    expect(retried).toBe("/api/v1/avatars/10.x/notionists/svg?seed=55fc3d39&_aerisun_img_retry=2");
  });

  it("does not mutate relative or data image sources", () => {
    expect(buildRetryableImageSrc("/media/avatar.svg", 1)).toBe("/media/avatar.svg");
    expect(buildRetryableImageSrc("data:image/svg+xml,<svg />", 1)).toBe("data:image/svg+xml,<svg />");
  });

  it("backs off retries without growing unbounded", () => {
    expect(retryDelayForAttempt(1)).toBe(350);
    expect(retryDelayForAttempt(2)).toBe(700);
    expect(retryDelayForAttempt(8)).toBe(2400);
  });

  it("keeps cross-origin avatar image attributes stable", () => {
    const markup = renderToStaticMarkup(
      createElement(RetryableAvatarImage, {
        src: "/api/v1/avatars/10.x/notionists/svg?seed=55fc3d39",
        alt: "avatar",
      }),
    );

    expect(markup).toContain('referrerPolicy="no-referrer"');
    expect(markup).toContain('decoding="async"');
  });
});
