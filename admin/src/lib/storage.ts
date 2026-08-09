export const ADMIN_TOKEN_STORAGE_KEY = "admin_token";
export const ADMIN_THEME_STORAGE_KEY = "aerisun-admin-theme";
export const LEGACY_ADMIN_THEME_STORAGE_KEY = "serino-admin-theme";
const CONFIG_CHECK_STATUS_PREFIX = "aerisun-config-check-status:";

interface PersistedConfigCheckStatus {
  signature: string;
  ok: boolean;
  details?: unknown;
}

const readPersistedConfigCheckStatus = (
  key: string,
  signature: string,
): PersistedConfigCheckStatus | null => {
  try {
    const raw = localStorage.getItem(`${CONFIG_CHECK_STATUS_PREFIX}${key}`);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as Partial<PersistedConfigCheckStatus>;
    if (parsed.signature !== signature || typeof parsed.ok !== "boolean") {
      return null;
    }
    return parsed as PersistedConfigCheckStatus;
  } catch {
    return null;
  }
};

export const getAdminToken = () => localStorage.getItem(ADMIN_TOKEN_STORAGE_KEY);

export const setAdminToken = (token: string) => {
  localStorage.setItem(ADMIN_TOKEN_STORAGE_KEY, token);
};

export const clearAdminToken = () => {
  localStorage.removeItem(ADMIN_TOKEN_STORAGE_KEY);
};

export const migrateAdminThemePreference = () => {
  const current = localStorage.getItem(ADMIN_THEME_STORAGE_KEY);
  if (current !== null) {
    return current;
  }

  const legacy = localStorage.getItem(LEGACY_ADMIN_THEME_STORAGE_KEY);
  if (legacy !== null) {
    localStorage.setItem(ADMIN_THEME_STORAGE_KEY, legacy);
  }

  return legacy;
};

export const getPersistedConfigCheckStatus = (
  key: string,
  signature: string,
): boolean | null => {
  return readPersistedConfigCheckStatus(key, signature)?.ok ?? null;
};

export const getPersistedConfigCheckDetails = (
  key: string,
  signature: string,
): unknown => readPersistedConfigCheckStatus(key, signature)?.details ?? null;

export const setPersistedConfigCheckStatus = (
  key: string,
  signature: string,
  ok: boolean,
  details?: unknown,
) => {
  try {
    const payload: PersistedConfigCheckStatus = {
      signature,
      ok,
      ...(details === undefined ? {} : { details }),
    };
    localStorage.setItem(
      `${CONFIG_CHECK_STATUS_PREFIX}${key}`,
      JSON.stringify(payload),
    );
  } catch {
    // Ignore storage write failures and keep the in-memory status only.
  }
};

export const clearPersistedConfigCheckStatus = (key: string) => {
  try {
    localStorage.removeItem(`${CONFIG_CHECK_STATUS_PREFIX}${key}`);
  } catch {
    // Ignore storage access failures and keep the in-memory status only.
  }
};
