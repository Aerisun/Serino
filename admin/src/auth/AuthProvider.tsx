import { createContext, useState, useEffect, useCallback, type ReactNode } from "react";
import type { AdminUserRead } from "@serino/api-client/models";
import {
  exchangeSiteUserLogin as apiExchangeSiteUserLogin,
  getLoginOptions as apiGetLoginOptions,
  getMe,
  login as apiLogin,
  loginWithBoundEmail as apiLoginWithBoundEmail,
  logout as apiLogout,
} from "@/api/endpoints/auth";
import { clearAdminToken, getAdminToken, setAdminToken } from "@/lib/storage";

interface AuthState {
  user: AdminUserRead | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  loginOptions: {
    oauth_providers: string[];
    email_enabled: boolean;
  } | null;
  login: (username: string, password: string) => Promise<void>;
  loginWithAdminEmail: (email: string) => Promise<void>;
  exchangeSiteUserLogin: () => Promise<void>;
  logout: () => Promise<void>;
}

export const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AdminUserRead | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loginOptions, setLoginOptions] = useState<AuthState["loginOptions"]>(null);

  useEffect(() => {
    apiGetLoginOptions().then(setLoginOptions).catch(() => setLoginOptions(null));

    const token = getAdminToken();
    if (!token) {
      setIsLoading(false);
      return;
    }
    getMe()
      .then(setUser)
      .catch(clearAdminToken)
      .finally(() => setIsLoading(false));
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const res = await apiLogin({ username, password });
    setAdminToken(res.token);
    const me = await getMe();
    setUser(me);
  }, []);

  const loginWithAdminEmail = useCallback(async (email: string) => {
    const res = await apiLoginWithBoundEmail({ email });
    setAdminToken(res.token);
    const me = await getMe();
    setUser(me);
  }, []);

  const exchangeSiteUserLogin = useCallback(async () => {
    const res = await apiExchangeSiteUserLogin();
    setAdminToken(res.token);
    const me = await getMe();
    setUser(me);
  }, []);

  const logout = useCallback(async () => {
    try {
      await apiLogout();
    } finally {
      clearAdminToken();
      setUser(null);
    }
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated: !!user,
        loginOptions,
        login,
        loginWithAdminEmail,
        exchangeSiteUserLogin,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
