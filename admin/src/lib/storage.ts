export const ADMIN_TOKEN_STORAGE_KEY = "admin_token";
export const ADMIN_THEME_STORAGE_KEY = "aerisun-admin-theme";
export const LEGACY_ADMIN_THEME_STORAGE_KEY = "serino-admin-theme";

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
