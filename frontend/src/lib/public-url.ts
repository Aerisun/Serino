const HTTP_PROTOCOLS = new Set(["http:", "https:"]);

export const normalizePublicBaseUrl = (value: string): string => {
  const candidate = value.trim();
  if (!candidate || /[\\\s]/.test(candidate)) return "";

  try {
    const parsed = new URL(candidate);
    if (
      !HTTP_PROTOCOLS.has(parsed.protocol) ||
      !parsed.hostname ||
      parsed.username ||
      parsed.password ||
      (parsed.pathname !== "" && parsed.pathname !== "/") ||
      parsed.search ||
      parsed.hash
    ) {
      return "";
    }

    return parsed.origin;
  } catch {
    return "";
  }
};

export const isPublicHttpUrl = (value: string): boolean => {
  const candidate = value.trim();
  if (!candidate || /[\\\s]/.test(candidate)) return false;

  try {
    const parsed = new URL(candidate);
    return (
      HTTP_PROTOCOLS.has(parsed.protocol) &&
      Boolean(parsed.hostname) &&
      !parsed.username &&
      !parsed.password
    );
  } catch {
    return false;
  }
};

export const resolvePublicUrl = ({
  canonicalBaseUrl,
  fallbackBaseUrl,
  pathname = "/",
}: {
  canonicalBaseUrl?: string;
  fallbackBaseUrl?: string;
  pathname?: string;
}): string => {
  const baseUrl =
    normalizePublicBaseUrl(canonicalBaseUrl ?? "") ||
    normalizePublicBaseUrl(fallbackBaseUrl ?? "");
  const normalizedPath = pathname.startsWith("/") ? pathname : `/${pathname}`;
  return baseUrl ? `${baseUrl}${normalizedPath}` : normalizedPath;
};

export const resolvePublicResourceUrl = ({
  value,
  canonicalBaseUrl,
  fallbackBaseUrl,
}: {
  value: string;
  canonicalBaseUrl?: string;
  fallbackBaseUrl?: string;
}): string => {
  const candidate = value.trim();
  if (!candidate) return "";
  if (isPublicHttpUrl(candidate)) return candidate;
  if (/^[a-z][a-z\d+.-]*:/i.test(candidate)) return "";
  return resolvePublicUrl({
    canonicalBaseUrl,
    fallbackBaseUrl,
    pathname: candidate.startsWith("/") ? candidate : `/${candidate}`,
  });
};
