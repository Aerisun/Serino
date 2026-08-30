// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LanguageProvider } from "../src/i18n";
import { PersonalizationTab, validateBackgroundMusicFile } from "../src/pages/site-config/tabs/PersonalizationTab";

const api = vi.hoisted(() => ({
  config: {
    enabled: false,
    playback_mode: "sequential" as const,
    tracks: [] as Array<{
      id: string;
      asset_id: string;
      title: string;
      file_name: string;
      byte_size: number;
      mime_type: string;
      stream_url: string;
      order_index: number;
      is_enabled: boolean;
      created_at: string;
      updated_at: string;
    }>,
  },
  updateConfig: vi.fn(),
  createTrackAsync: vi.fn(),
  reorderTracks: vi.fn(),
  updateTrack: vi.fn(),
  deleteTrack: vi.fn(),
  uploadAsset: vi.fn(),
  deleteAsset: vi.fn(),
  invalidateQueries: vi.fn(),
}));

vi.mock("@serino/api-client/admin", () => ({
  getGetBackgroundMusicApiV1AdminSiteConfigBackgroundMusicGetQueryKey: () => ["background-music"],
  useGetBackgroundMusicApiV1AdminSiteConfigBackgroundMusicGet: () => ({
    data: { data: api.config },
    isLoading: false,
  }),
  useUpdateBackgroundMusicApiV1AdminSiteConfigBackgroundMusicPut: () => ({
    mutate: api.updateConfig,
    isPending: false,
  }),
  useCreateBackgroundMusicTrackApiV1AdminSiteConfigBackgroundMusicTracksPost: () => ({
    mutateAsync: api.createTrackAsync,
    isPending: false,
  }),
  useReorderBackgroundMusicTracksApiV1AdminSiteConfigBackgroundMusicTracksReorderPut: () => ({
    mutate: api.reorderTracks,
    isPending: false,
  }),
  useUpdateBackgroundMusicTrackApiV1AdminSiteConfigBackgroundMusicTracksTrackIdPatch: () => ({
    mutate: api.updateTrack,
    isPending: false,
  }),
  useDeleteBackgroundMusicTrackApiV1AdminSiteConfigBackgroundMusicTracksTrackIdDelete: () => ({
    mutate: api.deleteTrack,
    isPending: false,
  }),
  deleteAssetEndpointApiV1AdminAssetsAssetIdDelete: api.deleteAsset,
}));

vi.mock("@/lib/managedAssetUpload", () => ({
  uploadManagedAsset: api.uploadAsset,
}));

const renderTab = () => {
  const queryClient = new QueryClient();
  vi.spyOn(queryClient, "invalidateQueries").mockImplementation(api.invalidateQueries);
  return render(
    <QueryClientProvider client={queryClient}>
      <LanguageProvider>
        <PersonalizationTab />
      </LanguageProvider>
    </QueryClientProvider>,
  );
};

const track = {
  id: "track-1",
  asset_id: "asset-1",
  title: "晚风",
  file_name: "evening.mp3",
  byte_size: 1024,
  mime_type: "audio/mpeg",
  stream_url: "/media/assets/asset-1.mp3",
  order_index: 0,
  is_enabled: true,
  created_at: "2026-08-30T00:00:00+08:00",
  updated_at: "2026-08-30T00:00:00+08:00",
};

beforeEach(() => {
  localStorage.clear();
  api.config.enabled = false;
  api.config.playback_mode = "sequential";
  api.config.tracks = [];
  api.updateConfig.mockReset();
  api.createTrackAsync.mockReset().mockResolvedValue({ data: track });
  api.reorderTracks.mockReset();
  api.updateTrack.mockReset();
  api.deleteTrack.mockReset();
  api.uploadAsset.mockReset().mockResolvedValue({
    id: "asset-uploaded",
    internal_url: "/media/assets/asset-uploaded.mp3",
  });
  api.deleteAsset.mockReset().mockResolvedValue(undefined);
  api.invalidateQueries.mockReset().mockResolvedValue(undefined);
});

afterEach(cleanup);

describe("background music personalization", () => {
  it("lives inside the existing feature-toggle personalization section without a duplicate site tab", () => {
    const featureTogglesSource = readFileSync(
      resolve(process.cwd(), "src/pages/more/FeatureTogglesSection.tsx"),
      "utf8",
    );
    const siteConfigSource = readFileSync(
      resolve(process.cwd(), "src/pages/site-config/SiteConfigPage.tsx"),
      "utf8",
    );
    const personalizationSection = featureTogglesSource.slice(
      featureTogglesSource.indexOf('<CollapsibleSection title={t("siteConfig.personalization")}'),
    );

    expect(personalizationSection).toContain("<PersonalizationTab");
    expect(siteConfigSource).not.toContain("PersonalizationTab");
    expect(siteConfigSource).not.toContain('value: "personalization"');
  });

  it("uses a concise description and an icon-only disclosure in the collapsed switch row", async () => {
    renderTab();

    expect(screen.queryByRole("heading", { name: "背景音乐" })).toBeNull();
    expect(screen.getByText("背景音乐")).toBeTruthy();
    expect(screen.getByText("管理前台可播放的背景音乐。")).toBeTruthy();
    expect(screen.getByRole("switch", { name: "开启背景音乐" }).hasAttribute("disabled")).toBe(true);
    expect(screen.queryByRole("combobox", { name: "播放模式" })).toBeNull();
    expect(screen.queryByText(/CDN/)).toBeNull();

    const disclosure = screen.getByRole("button", { name: "展开" });
    expect(disclosure.textContent).toBe("");
    expect(disclosure.querySelector(".lucide-chevron-right")).toBeTruthy();
    await userEvent.click(disclosure);

    const collapse = screen.getByRole("button", { name: "收起" });
    expect(collapse.querySelector(".lucide-chevron-right")?.classList.contains("rotate-90")).toBe(true);

    expect(screen.getByLabelText("播放模式")).toBeTruthy();
    expect(screen.getByRole("button", { name: "上传音乐" })).toBeTruthy();
    expect(screen.getByText("暂无音乐，上传第一首歌曲后即可开启。")).toBeTruthy();
    expect(document.querySelector(".lucide-music2, .lucide-upload")).toBeNull();
  });

  it("updates playback mode, title, enabled state and order with compact controls", async () => {
    api.config.tracks = [
      track,
      { ...track, id: "track-2", asset_id: "asset-2", title: "清晨", order_index: 1 },
    ];
    renderTab();
    await userEvent.click(screen.getByRole("button", { name: "展开" }));

    fireEvent.change(screen.getByLabelText("播放模式"), { target: { value: "random" } });
    expect(api.updateConfig).toHaveBeenCalledWith({ data: { playback_mode: "random" } });

    const titleInput = screen.getByRole("textbox", { name: "晚风的歌名" });
    fireEvent.change(titleInput, { target: { value: "新的歌名" } });
    await userEvent.click(screen.getByRole("button", { name: "保存晚风的歌名" }));
    expect(api.updateTrack).toHaveBeenCalledWith({
      trackId: "track-1",
      data: { title: "新的歌名" },
    });

    await userEvent.click(screen.getByRole("switch", { name: "启用晚风" }));
    expect(api.updateTrack).toHaveBeenCalledWith({
      trackId: "track-1",
      data: { is_enabled: false },
    });

    await userEvent.click(screen.getByRole("button", { name: "下移晚风" }));
    expect(api.reorderTracks).toHaveBeenCalledWith({
      data: { track_ids: ["track-2", "track-1"] },
    });
  });

  it("uploads a validated public system music asset and creates a track", async () => {
    renderTab();
    await userEvent.click(screen.getByRole("button", { name: "展开" }));
    const file = new File(["ID3-audio"], "Rain.mp3", { type: "audio/mpeg" });

    await userEvent.upload(screen.getByLabelText("选择音乐文件"), file);

    await waitFor(() => {
      expect(api.uploadAsset).toHaveBeenCalledWith({
        file,
        visibility: "public",
        scope: "system",
        category: "music",
        note: "背景音乐",
      });
    });
    expect(api.createTrackAsync).toHaveBeenCalledWith({
      data: { asset_id: "asset-uploaded" },
    });
  });

  it("validates the 50 MiB limit and supported extensions before upload", () => {
    const oversized = new File(["x"], "large.mp3", { type: "audio/mpeg" });
    Object.defineProperty(oversized, "size", { value: 50 * 1024 * 1024 + 1 });
    const wav = new File(["wave"], "track.wav", { type: "audio/wav" });
    const mp3 = new File(["ID3"], "track.mp3", { type: "audio/mpeg" });

    expect(validateBackgroundMusicFile(oversized)).toContain("50 MiB");
    expect(validateBackgroundMusicFile(wav)).toContain("MP3");
    expect(validateBackgroundMusicFile(mp3)).toBeNull();
  });
});
