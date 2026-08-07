// @vitest-environment jsdom

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import AssetPreviewPage from "../src/pages/assets/AssetPreviewPage";
import { LanguageProvider } from "../src/i18n";

const api = vi.hoisted(() => ({
  createOpenUrl: vi.fn(),
  replaceLocation: vi.fn(),
}));

vi.mock("@serino/api-client/admin", () => ({
  createAssetOpenUrlEndpointApiV1AdminAssetsAssetIdOpenUrlPost: api.createOpenUrl,
}));

vi.mock("@/lib/browserNavigation", () => ({
  replaceBrowserLocation: api.replaceLocation,
}));

afterEach(() => {
  cleanup();
});

describe("AssetPreviewPage", () => {
  it("redirects the new tab to the authorized native browser file response", async () => {
    api.createOpenUrl.mockResolvedValue({
      data: {
        url: "/media/assets/asset-1.pdf?preview_token=signed",
        expires_at: "2026-08-07T13:30:00+08:00",
      },
      status: 200,
    });

    render(
      <MemoryRouter
        initialEntries={["/assets/preview/asset-1"]}
        future={{ v7_relativeSplatPath: true, v7_startTransition: true }}
      >
        <LanguageProvider>
          <Routes>
            <Route path="assets/preview/:assetId" element={<AssetPreviewPage />} />
          </Routes>
        </LanguageProvider>
      </MemoryRouter>,
    );

    expect(screen.getByLabelText("加载中...")).toBeTruthy();
    await waitFor(() => {
      expect(api.createOpenUrl).toHaveBeenCalledWith("asset-1");
      expect(api.replaceLocation).toHaveBeenCalledWith(
        "/media/assets/asset-1.pdf?preview_token=signed",
      );
    });
  });
});
