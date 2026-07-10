// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { CollapsibleSection } from "../src/components/ui/CollapsibleSection";

afterEach(cleanup);

describe("CollapsibleSection", () => {
  it("keeps collapsed content out of the accessibility tree until expanded", () => {
    render(
      <CollapsibleSection title="个性化">
        <button type="button">隐藏的设置</button>
      </CollapsibleSection>,
    );

    const trigger = screen.getByRole("button", { name: "个性化" });
    const hiddenControl = screen.getByRole("button", { name: "隐藏的设置", hidden: true });
    const content = hiddenControl.closest("[aria-hidden]");

    expect(trigger.getAttribute("aria-expanded")).toBe("false");
    expect(content?.getAttribute("aria-hidden")).toBe("true");
    expect(content?.hasAttribute("inert")).toBe(true);

    fireEvent.click(trigger);

    expect(trigger.getAttribute("aria-expanded")).toBe("true");
    expect(content?.getAttribute("aria-hidden")).toBe("false");
    expect(content?.hasAttribute("inert")).toBe(false);
  });
});
