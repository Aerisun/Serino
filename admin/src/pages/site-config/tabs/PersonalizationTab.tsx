import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ChevronRight } from "lucide-react";
import {
  deleteAssetEndpointApiV1AdminAssetsAssetIdDelete,
  getGetBackgroundMusicApiV1AdminSiteConfigBackgroundMusicGetQueryKey,
  useCreateBackgroundMusicTrackApiV1AdminSiteConfigBackgroundMusicTracksPost,
  useDeleteBackgroundMusicTrackApiV1AdminSiteConfigBackgroundMusicTracksTrackIdDelete,
  useGetBackgroundMusicApiV1AdminSiteConfigBackgroundMusicGet,
  useReorderBackgroundMusicTracksApiV1AdminSiteConfigBackgroundMusicTracksReorderPut,
  useUpdateBackgroundMusicApiV1AdminSiteConfigBackgroundMusicPut,
  useUpdateBackgroundMusicTrackApiV1AdminSiteConfigBackgroundMusicTracksTrackIdPatch,
} from "@serino/api-client/admin";
import type { BackgroundMusicTrackAdminRead } from "@serino/api-client/models";
import { AppleSwitch } from "@/components/ui/AppleSwitch";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { NativeSelect } from "@/components/ui/NativeSelect";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { useI18n } from "@/i18n";
import { extractApiErrorMessage } from "@/lib/api-error";
import { uploadManagedAsset } from "@/lib/managedAssetUpload";
import { cn, formatBytes } from "@/lib/utils";
import { toast } from "sonner";

const MAX_MUSIC_FILE_BYTES = 50 * 1024 * 1024;
const MUSIC_EXTENSIONS = new Set(["mp3", "m4a", "aac"]);
const MUSIC_MIME_TYPES = new Set([
  "audio/mpeg",
  "audio/mp4",
  "audio/x-m4a",
  "audio/m4a",
  "audio/aac",
]);

export function validateBackgroundMusicFile(file: File): string | null {
  if (file.size > MAX_MUSIC_FILE_BYTES) {
    return "音乐文件不能超过 50 MiB";
  }
  const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
  if (!MUSIC_EXTENSIONS.has(extension) || !MUSIC_MIME_TYPES.has(file.type.toLowerCase())) {
    return "仅支持 MP3、M4A 或 AAC 音频文件";
  }
  return null;
}

function MusicTrackRow({
  track,
  index,
  count,
  previewing,
  onPreview,
  onUpdate,
  onMove,
  onDelete,
  pending,
}: {
  track: BackgroundMusicTrackAdminRead;
  index: number;
  count: number;
  previewing: boolean;
  onPreview: () => void;
  onUpdate: (data: { title?: string; is_enabled?: boolean }) => void;
  onMove: (direction: -1 | 1) => void;
  onDelete: () => void;
  pending: boolean;
}) {
  const { t } = useI18n();
  const [title, setTitle] = useState(track.title);

  useEffect(() => setTitle(track.title), [track.title]);

  const normalizedTitle = title.trim();
  const titleChanged = normalizedTitle !== track.title;

  return (
    <li className="rounded-[var(--admin-radius-md)] border border-border/60 bg-background/30 p-3">
      <div className="space-y-2.5">
        <div className="flex min-w-0 gap-2">
          <Input
            value={title}
            maxLength={160}
            onChange={(event) => setTitle(event.target.value)}
            aria-label={t("siteConfig.music.titleInput", { title: track.title })}
            className="min-w-0"
          />
          <Button
            type="button"
            size="sm"
            variant="outline"
            aria-label={t("siteConfig.music.saveTitle", { title: track.title })}
            disabled={!titleChanged || !normalizedTitle || pending}
            onClick={() => onUpdate({ title: normalizedTitle })}
            className="h-11"
          >
            {t("common.save")}
          </Button>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
          <span className="min-w-0 truncate">
            {track.file_name} · {track.byte_size ? formatBytes(track.byte_size) : "—"}
          </span>
          <div className="flex shrink-0 flex-wrap items-center justify-end gap-1">
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={onPreview}
              aria-label={previewing ? t("siteConfig.music.previewPause", { title: track.title }) : t("siteConfig.music.previewPlay", { title: track.title })}
              className="h-8 min-h-8 px-2.5 text-xs"
            >
              {previewing ? t("siteConfig.music.pausePreview") : t("siteConfig.music.preview")}
            </Button>
            <button
              type="button"
              role="switch"
              aria-checked={track.is_enabled}
              aria-label={t("siteConfig.music.enableTrack", { title: track.title })}
              onClick={() => onUpdate({ is_enabled: !track.is_enabled })}
              disabled={pending}
              className={`inline-flex h-8 items-center rounded-full border px-3 text-xs font-medium transition ${
                track.is_enabled
                  ? "border-emerald-400/35 bg-emerald-400/10 text-emerald-700 dark:text-emerald-300"
                  : "border-border/60 bg-background/40 text-muted-foreground"
              }`}
            >
              {track.is_enabled ? t("common.enabled") : t("common.disabled")}
            </button>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              aria-label={t("siteConfig.music.moveUp", { title: track.title })}
              disabled={index === 0 || pending}
              onClick={() => onMove(-1)}
              className="h-8 min-h-8 px-2.5 text-xs"
            >
              {t("siteConfig.music.moveUpLabel")}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              aria-label={t("siteConfig.music.moveDown", { title: track.title })}
              disabled={index === count - 1 || pending}
              onClick={() => onMove(1)}
              className="h-8 min-h-8 px-2.5 text-xs"
            >
              {t("siteConfig.music.moveDownLabel")}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              aria-label={t("siteConfig.music.deleteTrack", { title: track.title })}
              disabled={pending}
              onClick={onDelete}
              className="h-8 min-h-8 px-2.5 text-xs text-destructive hover:text-destructive"
            >
              {t("common.delete")}
            </Button>
          </div>
        </div>
      </div>
    </li>
  );
}

export function PersonalizationTab() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const previewAudioRef = useRef<HTMLAudioElement | null>(null);
  const [previewingTrackId, setPreviewingTrackId] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<BackgroundMusicTrackAdminRead | null>(null);
  const queryKey = getGetBackgroundMusicApiV1AdminSiteConfigBackgroundMusicGetQueryKey();
  const { data: response, isLoading } = useGetBackgroundMusicApiV1AdminSiteConfigBackgroundMusicGet();
  const config = response?.data;
  const tracks = config?.tracks ?? [];
  const hasEnabledTrack = tracks.some((track) => track.is_enabled);

  const refresh = () => queryClient.invalidateQueries({ queryKey });
  const mutationError = (error: unknown) => {
    toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
  };
  const updateConfig = useUpdateBackgroundMusicApiV1AdminSiteConfigBackgroundMusicPut({
    mutation: {
      onSuccess: () => {
        void refresh();
        toast.success(t("common.operationSuccess"));
      },
      onError: mutationError,
    },
  });
  const createTrack = useCreateBackgroundMusicTrackApiV1AdminSiteConfigBackgroundMusicTracksPost();
  const reorderTracks = useReorderBackgroundMusicTracksApiV1AdminSiteConfigBackgroundMusicTracksReorderPut({
    mutation: {
      onSuccess: () => void refresh(),
      onError: mutationError,
    },
  });
  const updateTrack = useUpdateBackgroundMusicTrackApiV1AdminSiteConfigBackgroundMusicTracksTrackIdPatch({
    mutation: {
      onSuccess: () => {
        void refresh();
        toast.success(t("common.operationSuccess"));
      },
      onError: mutationError,
    },
  });
  const deleteTrack = useDeleteBackgroundMusicTrackApiV1AdminSiteConfigBackgroundMusicTracksTrackIdDelete({
    mutation: {
      onSuccess: () => {
        setDeleteTarget(null);
        void refresh();
        toast.success(t("common.operationSuccess"));
      },
      onError: mutationError,
    },
  });

  useEffect(() => {
    return () => {
      previewAudioRef.current?.pause();
      previewAudioRef.current = null;
    };
  }, []);

  const togglePreview = (track: BackgroundMusicTrackAdminRead) => {
    if (previewingTrackId === track.id && previewAudioRef.current) {
      previewAudioRef.current.pause();
      previewAudioRef.current = null;
      setPreviewingTrackId(null);
      return;
    }
    previewAudioRef.current?.pause();
    const audio = new Audio(track.stream_url);
    audio.preload = "none";
    audio.addEventListener("ended", () => setPreviewingTrackId(null), { once: true });
    audio.addEventListener("error", () => {
      setPreviewingTrackId(null);
      toast.error(t("siteConfig.music.previewFailed"));
    }, { once: true });
    previewAudioRef.current = audio;
    setPreviewingTrackId(track.id);
    void audio.play().catch(() => {
      setPreviewingTrackId(null);
      previewAudioRef.current = null;
      toast.error(t("siteConfig.music.previewFailed"));
    });
  };

  const moveTrack = (index: number, direction: -1 | 1) => {
    const target = index + direction;
    if (target < 0 || target >= tracks.length) return;
    const ids = tracks.map((track) => track.id);
    [ids[index], ids[target]] = [ids[target], ids[index]];
    reorderTracks.mutate({ data: { track_ids: ids } });
  };

  const uploadMusic = async (file: File) => {
    const validationError = validateBackgroundMusicFile(file);
    if (validationError) {
      toast.error(validationError);
      return;
    }
    setUploading(true);
    let assetId: string | null = null;
    try {
      const asset = await uploadManagedAsset({
        file,
        visibility: "public",
        scope: "system",
        category: "music",
        note: "背景音乐",
      });
      assetId = asset.id;
      await createTrack.mutateAsync({ data: { asset_id: asset.id } });
      await refresh();
      toast.success(t("siteConfig.music.uploadSuccess"));
    } catch (error) {
      if (assetId) {
        try {
          await deleteAssetEndpointApiV1AdminAssetsAssetIdDelete(assetId);
        } catch {
          toast.error(t("siteConfig.music.cleanupFailed"));
        }
      }
      mutationError(error);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  if (isLoading && !config) {
    return <p className="py-4 text-muted-foreground">{t("common.loading")}</p>;
  }

  return (
    <>
      <AppleSwitch
        checked={Boolean(config?.enabled)}
        onCheckedChange={(enabled) => updateConfig.mutate({ data: { enabled } })}
        ariaLabel={t("siteConfig.music.enable")}
        disabled={updateConfig.isPending}
        switchDisabled={!hasEnabledTrack}
        label={t("siteConfig.music.title")}
        description={t("siteConfig.music.description")}
        switchLeading={
          <button
            type="button"
            aria-label={expanded ? t("common.collapse") : t("common.expand")}
            aria-expanded={expanded}
            disabled={updateConfig.isPending}
            onClick={() => setExpanded((current) => !current)}
            className={cn(
              "inline-flex h-6 w-6 items-center justify-center rounded-md border border-border/70 bg-background/40 text-muted-foreground transition hover:bg-background/70 hover:text-foreground",
              updateConfig.isPending && "cursor-not-allowed opacity-60",
              expanded && "text-foreground",
            )}
          >
            <ChevronRight
              className={cn(
                "h-4 w-4 transition-transform duration-200",
                expanded && "rotate-90",
              )}
            />
          </button>
        }
        expandableOpen={expanded}
        expandableContent={
          <div className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
              <div className="grid gap-2 sm:grid-cols-[8rem_minmax(0,1fr)] sm:items-center">
                <Label htmlFor="background-music-playback-mode">
                  {t("siteConfig.music.playbackMode")}
                </Label>
                <NativeSelect
                  id="background-music-playback-mode"
                  aria-label={t("siteConfig.music.playbackMode")}
                  value={config?.playback_mode ?? "sequential"}
                  disabled={updateConfig.isPending}
                  onChange={(event) => updateConfig.mutate({
                    data: { playback_mode: event.target.value as "sequential" | "random" },
                  })}
                >
                  <option value="sequential">{t("siteConfig.music.sequential")}</option>
                  <option value="random">{t("siteConfig.music.random")}</option>
                </NativeSelect>
              </div>

              <Button
                type="button"
                variant="outline"
                disabled={uploading || createTrack.isPending}
                onClick={() => fileInputRef.current?.click()}
              >
                {uploading ? t("siteConfig.music.uploading") : t("siteConfig.music.upload")}
              </Button>
              <input
                ref={fileInputRef}
                type="file"
                accept=".mp3,.m4a,.aac,audio/mpeg,audio/mp4,audio/aac"
                aria-label={t("siteConfig.music.chooseFile")}
                className="sr-only"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) void uploadMusic(file);
                }}
              />
            </div>

            {tracks.length ? (
              <ul
                className="max-h-[32rem] space-y-2 overflow-y-auto pr-1"
                aria-label={t("siteConfig.music.playlist")}
              >
                {tracks.map((track, index) => (
                  <MusicTrackRow
                    key={track.id}
                    track={track}
                    index={index}
                    count={tracks.length}
                    previewing={previewingTrackId === track.id}
                    onPreview={() => togglePreview(track)}
                    onUpdate={(data) => updateTrack.mutate({ trackId: track.id, data })}
                    onMove={(direction) => moveTrack(index, direction)}
                    onDelete={() => setDeleteTarget(track)}
                    pending={updateTrack.isPending || reorderTracks.isPending}
                  />
                ))}
              </ul>
            ) : (
              <div className="rounded-[var(--admin-radius-md)] border border-dashed border-border/70 px-4 py-6 text-center text-sm text-muted-foreground">
                {t("siteConfig.music.empty")}
              </div>
            )}
          </div>
        }
      />

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        onCancel={() => setDeleteTarget(null)}
        onConfirm={() => {
          if (deleteTarget) deleteTrack.mutate({ trackId: deleteTarget.id });
        }}
        title={t("siteConfig.music.deleteConfirmTitle")}
        description={t("siteConfig.music.deleteConfirmDescription", { title: deleteTarget?.title ?? "" })}
        confirmLabel={t("common.delete")}
        variant="destructive"
        isPending={deleteTrack.isPending}
      />
    </>
  );
}
