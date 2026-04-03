import { API_BASE_PATH, API_BASE_URL } from "@/lib/api";

export interface LinkPreviewPayload {
  url: string;
  resolved_url: string;
  hostname: string;
  title: string | null;
  description: string | null;
  site_name: string | null;
  image_url: string | null;
  image_width: number | null;
  image_height: number | null;
  icon_url: string | null;
  available: boolean;
  error: string | null;
}

const previewCache = new Map<string, LinkPreviewPayload | null>();
const inflightRequests = new Map<string, Promise<LinkPreviewPayload | null>>();

const buildPreviewRequestUrl = (href: string) => {
  const pathname = `${API_BASE_PATH}/v1/site/link-preview`;
  const search = new URLSearchParams({ url: href }).toString();
  const relativePath = `${pathname}?${search}`;
  return API_BASE_URL ? new URL(relativePath, API_BASE_URL).toString() : relativePath;
};

export const buildPreviewImageUrl = (href: string) => {
  const pathname = `${API_BASE_PATH}/v1/site/link-preview-image`;
  const search = new URLSearchParams({ url: href }).toString();
  const relativePath = `${pathname}?${search}`;
  return API_BASE_URL ? new URL(relativePath, API_BASE_URL).toString() : relativePath;
};

export const fetchLinkPreview = async (
  href: string,
  signal?: AbortSignal,
): Promise<LinkPreviewPayload | null> => {
  if (previewCache.has(href)) {
    return previewCache.get(href) ?? null;
  }

  const existing = inflightRequests.get(href);
  if (existing) {
    return existing;
  }

  const request = (async () => {
    try {
      const response = await fetch(buildPreviewRequestUrl(href), {
        method: "GET",
        headers: {
          Accept: "application/json",
        },
        signal,
      });

      if (!response.ok) {
        previewCache.set(href, null);
        return null;
      }

      const payload = (await response.json()) as LinkPreviewPayload;
      previewCache.set(href, payload);
      return payload;
    } catch {
      return null;
    } finally {
      inflightRequests.delete(href);
    }
  })();

  inflightRequests.set(href, request);
  return request;
};
