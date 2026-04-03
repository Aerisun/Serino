export const ADMIN_TOKEN_STORAGE_KEY = "admin_token";
export const ADMIN_THEME_STORAGE_KEY = "aerisun-admin-theme";
export const LEGACY_ADMIN_THEME_STORAGE_KEY = "serino-admin-theme";
const CONFIG_CHECK_STATUS_PREFIX = "aerisun-config-check-status:";

interface PersistedConfigCheckStatus {
  signature: string;
  ok: boolean;
}

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
  try {
    const raw = localStorage.getItem(`${CONFIG_CHECK_STATUS_PREFIX}${key}`);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as Partial<PersistedConfigCheckStatus>;
    if (parsed.signature !== signature || typeof parsed.ok !== "boolean") {
      return null;
    }
    return parsed.ok;
  } catch {
    return null;
  }
};

export const setPersistedConfigCheckStatus = (
  key: string,
  signature: string,
  ok: boolean,
) => {
  try {
    const payload: PersistedConfigCheckStatus = { signature, ok };
    localStorage.setItem(
      `${CONFIG_CHECK_STATUS_PREFIX}${key}`,
      JSON.stringify(payload),
    );
  } catch {
    // Ignore storage write failures and keep the in-memory status only.
  }
};
