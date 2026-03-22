import client from "../client";
import type {
  SiteProfile,
  SiteProfileUpdate,
  SocialLink,
  SocialLinkCreate,
  SocialLinkUpdate,
  Poem,
  PoemCreate,
  PoemUpdate,
  PageCopy,
  PageCopyCreate,
  PageCopyUpdate,
  PageDisplayOption,
  PageDisplayOptionCreate,
  PageDisplayOptionUpdate,
  NavItem,
  NavItemCreate,
  NavItemUpdate,
  CommunityConfig,
  CommunityConfigUpdate,
  PaginatedResponse,
} from "@/types/models";
import { COMMUNITY_CONFIG_ENDPOINTS } from "@/lib/community-config";

// --- Profile ---
export async function getProfile(): Promise<SiteProfile> {
  const res = await client.get("/site-config/profile");
  return res.data;
}

export async function updateProfile(data: SiteProfileUpdate): Promise<SiteProfile> {
  const res = await client.put("/site-config/profile", data);
  return res.data;
}

// --- Social Links ---
export async function listSocialLinks(params?: { page?: number }): Promise<PaginatedResponse<SocialLink>> {
  const res = await client.get("/site-config/social-links/", { params });
  return res.data;
}

export async function createSocialLink(data: SocialLinkCreate): Promise<SocialLink> {
  const res = await client.post("/site-config/social-links/", data);
  return res.data;
}

export async function updateSocialLink(id: string, data: SocialLinkUpdate): Promise<SocialLink> {
  const res = await client.put(`/site-config/social-links/${id}`, data);
  return res.data;
}

export async function deleteSocialLink(id: string): Promise<void> {
  await client.delete(`/site-config/social-links/${id}`);
}

// --- Poems ---
export async function listPoems(params?: { page?: number }): Promise<PaginatedResponse<Poem>> {
  const res = await client.get("/site-config/poems/", { params });
  return res.data;
}

export async function createPoem(data: PoemCreate): Promise<Poem> {
  const res = await client.post("/site-config/poems/", data);
  return res.data;
}

export async function updatePoem(id: string, data: PoemUpdate): Promise<Poem> {
  const res = await client.put(`/site-config/poems/${id}`, data);
  return res.data;
}

export async function deletePoem(id: string): Promise<void> {
  await client.delete(`/site-config/poems/${id}`);
}

// --- PageCopy ---
export async function listPageCopy(params?: { page?: number }): Promise<PaginatedResponse<PageCopy>> {
  const res = await client.get("/site-config/page-copy/", { params });
  return res.data;
}

export async function createPageCopy(data: PageCopyCreate): Promise<PageCopy> {
  const res = await client.post("/site-config/page-copy/", data);
  return res.data;
}

export async function updatePageCopy(id: string, data: PageCopyUpdate): Promise<PageCopy> {
  const res = await client.put(`/site-config/page-copy/${id}`, data);
  return res.data;
}

export async function deletePageCopy(id: string): Promise<void> {
  await client.delete(`/site-config/page-copy/${id}`);
}

// --- Display Options ---
export async function listDisplayOptions(params?: { page?: number }): Promise<PaginatedResponse<PageDisplayOption>> {
  const res = await client.get("/site-config/display-options/", { params });
  return res.data;
}

export async function createDisplayOption(data: PageDisplayOptionCreate): Promise<PageDisplayOption> {
  const res = await client.post("/site-config/display-options/", data);
  return res.data;
}

export async function updateDisplayOption(id: string, data: PageDisplayOptionUpdate): Promise<PageDisplayOption> {
  const res = await client.put(`/site-config/display-options/${id}`, data);
  return res.data;
}

export async function deleteDisplayOption(id: string): Promise<void> {
  await client.delete(`/site-config/display-options/${id}`);
}

// --- Nav Items ---
export async function listNavItems(params?: { page?: number }): Promise<PaginatedResponse<NavItem>> {
  const res = await client.get("/site-config/nav-items/", { params });
  return res.data;
}

export async function createNavItem(data: NavItemCreate): Promise<NavItem> {
  const res = await client.post("/site-config/nav-items/", data);
  return res.data;
}

export async function updateNavItem(id: string, data: NavItemUpdate): Promise<NavItem> {
  const res = await client.put(`/site-config/nav-items/${id}`, data);
  return res.data;
}

export async function deleteNavItem(id: string): Promise<void> {
  await client.delete(`/site-config/nav-items/${id}`);
}

export async function reorderNavItems(items: { id: string; order_index: number }[]): Promise<void> {
  await client.put("/site-config/nav-items/reorder", items);
}

// --- Community / Comment System ---
async function requestCommunityConfig<T>(method: "get" | "put", data?: CommunityConfigUpdate): Promise<T> {
  let lastError: unknown = null;

  for (const endpoint of COMMUNITY_CONFIG_ENDPOINTS) {
    try {
      const res = method === "get"
        ? await client.get(endpoint)
        : await client.put(endpoint, data);
      return (res.data?.item ?? res.data) as T;
    } catch (error) {
      lastError = error;
    }
  }

  throw lastError instanceof Error ? lastError : new Error("Unable to load community config");
}

export async function getCommunityConfig(): Promise<CommunityConfig> {
  return requestCommunityConfig<CommunityConfig>("get");
}

export async function updateCommunityConfig(data: CommunityConfigUpdate): Promise<CommunityConfig> {
  return requestCommunityConfig<CommunityConfig>("put", data);
}
