// @vitest-environment jsdom

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { LanguageProvider } from "../src/i18n";
import AgentPage from "../src/pages/automation/AgentPage";
import { AgentSectionSwitch } from "../src/pages/automation/AgentSectionSwitch";

vi.mock("../src/pages/automation/AgentWorkflowsSection", () => ({
  AgentWorkflowsSection: () => <div>workflow-content</div>,
}));

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location">{location.pathname}</output>;
}

beforeEach(() => {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
});

afterEach(() => {
  cleanup();
  localStorage.clear();
  vi.clearAllMocks();
});

describe("Agent overview removal", () => {
  it.each(["/agent", "/agent/overview"])(
    "redirects %s to the workflow section",
    async (initialEntry) => {
      render(
        <MemoryRouter
          initialEntries={[initialEntry]}
          future={{ v7_relativeSplatPath: true, v7_startTransition: true }}
        >
          <LanguageProvider>
            <Routes>
              <Route
                path="/agent/:section?"
                element={
                  <>
                    <AgentPage />
                    <LocationProbe />
                  </>
                }
              />
            </Routes>
          </LanguageProvider>
        </MemoryRouter>,
      );

      await waitFor(() => {
        expect(screen.getByTestId("location").textContent).toBe("/agent/workflows");
      });
    },
  );

  it("shows only workflows, activity, and webhooks in the Agent section switch", () => {
    render(
      <MemoryRouter
        initialEntries={["/agent/workflows"]}
        future={{ v7_relativeSplatPath: true, v7_startTransition: true }}
      >
        <LanguageProvider>
          <AgentSectionSwitch />
        </LanguageProvider>
      </MemoryRouter>,
    );

    expect(screen.queryByRole("link", { name: "总览" })).toBeNull();
    expect(screen.getAllByRole("link").map((link) => link.getAttribute("href"))).toEqual([
      "/agent/workflows",
      "/agent/activity",
      "/agent/webhooks",
    ]);
  });
});
