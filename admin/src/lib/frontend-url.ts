const LOCALHOST_HOSTNAMES = new Set(["localhost", "127.0.0.1", "::1", "[::1]"]);

function isLocalHostname(hostname: string) {
  return LOCALHOST_HOSTNAMES.has(hostname.trim().toLowerCase());
}

export function resolveFrontendUrl(siteUrl?: string | null) {
  const adminOrigin = window.location.origin;
  const trimmedSiteUrl = (siteUrl || "").trim();

  if (!trimmedSiteUrl) {
    return adminOrigin;
  }

  try {
    const parsed = new URL(trimmedSiteUrl, adminOrigin);
    const adminHostname = window.location.hostname.trim().toLowerCase();
    const siteHostname = parsed.hostname.trim().toLowerCase();

    // When the backend still exposes the local default site_url in a deployed
    // admin session, opening the preview against localhost breaks outright.
    if (!isLocalHostname(adminHostname) && isLocalHostname(siteHostname)) {
      return adminOrigin;
    }

    return parsed.toString().replace(/\/+$/, "");
  } catch {
    return adminOrigin;
  }
}
