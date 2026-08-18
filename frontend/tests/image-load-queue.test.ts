import { describe, expect, it } from "vitest";
import { createImageLoadQueue } from "../src/lib/image-load-queue";

describe("image load queue", () => {
  it("starts background images one at a time after foreground work is complete", () => {
    const started: string[] = [];
    const queue = createImageLoadQueue();
    const first = queue.enqueue("background", () => started.push("first"));
    const second = queue.enqueue("background", () => started.push("second"));
    const foreground = queue.enqueue("foreground", () => started.push("foreground"));

    queue.resumeBackground();

    expect(started).toEqual(["foreground"]);

    foreground.finish();
    expect(started).toEqual(["foreground", "first"]);

    first.finish();
    expect(started).toEqual(["foreground", "first", "second"]);

    second.finish();
  });

  it("starts a newly visible image immediately and waits before continuing the background queue", () => {
    const started: string[] = [];
    const queue = createImageLoadQueue();
    const first = queue.enqueue("background", () => started.push("first"));
    const second = queue.enqueue("background", () => started.push("second"));

    queue.resumeBackground();
    expect(started).toEqual(["first"]);

    const visible = second.promote();
    expect(started).toEqual(["first", "second"]);

    first.finish();
    expect(started).toEqual(["first", "second"]);

    visible.finish();
  });

  it("continues with the next background image after a failed image reports completion", () => {
    const started: string[] = [];
    const queue = createImageLoadQueue();
    const first = queue.enqueue("background", () => started.push("first"));
    queue.enqueue("background", () => started.push("second"));

    queue.resumeBackground();
    first.finish();

    expect(started).toEqual(["first", "second"]);
  });

  it("does not let a promoted in-flight image release the background queue early", () => {
    const started: string[] = [];
    const queue = createImageLoadQueue();
    const first = queue.enqueue("background", () => started.push("first"));
    queue.enqueue("background", () => started.push("second"));

    queue.resumeBackground();
    first.promote();
    const foreground = queue.enqueue("foreground", () => started.push("foreground"));
    foreground.finish();

    expect(started).toEqual(["first", "foreground"]);

    first.finish();
    expect(started).toEqual(["first", "foreground", "second"]);
  });
});
