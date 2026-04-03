import { createContext, useState, useEffect, useCallback, type ReactNode } from "react";
import type { AdminUserRead } from "@serino/api-client/models";
import {
  exchangeSiteUserLoginApiV1AdminAuthExchangeSiteUserPost,
  loginOptionsApiV1AdminAuthOptionsGet,
  meApiV1AdminAuthMeGet,
  loginApiV1AdminAuthLoginPost,
  loginWithBoundEmailApiV1AdminAuthEmailPost,
  logoutApiV1AdminAuthLogoutPost,
} from "@serino/api-client/admin";
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
  loginWithAdminEmail: (email: string, password: string) => Promise<void>;
  exchangeSiteUserLogin: () => Promise<void>;
  logout: () => Promise<void>;
}

export const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AdminUserRead | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loginOptions, setLoginOptions] = useState<AuthState["loginOptions"]>(null);

  useEffect(() => {
    loginOptionsApiV1AdminAuthOptionsGet().then((r) => r.data).then(setLoginOptions).catch(() => setLoginOptions(null));

    const token = getAdminToken();
    if (!token) {
      setIsLoading(false);
      return;
    }
    meApiV1AdminAuthMeGet()
      .then((r) => r.data)
      .then(setUser)
      .catch(clearAdminToken)
      .finally(() => setIsLoading(false));
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const { data: res } = await loginApiV1AdminAuthLoginPost({ username, password });
    setAdminToken(res.token);
    const { data: me } = await meApiV1AdminAuthMeGet();
    setUser(me);
  }, []);

  const loginWithAdminEmail = useCallback(async (email: string, password: string) => {
    const { data: res } = await loginWithBoundEmailApiV1AdminAuthEmailPost({ email, password });
    setAdminToken(res.token);
    const { data: me } = await meApiV1AdminAuthMeGet();
    setUser(me);
  }, []);

  const exchangeSiteUserLogin = useCallback(async () => {
    const { data: res } = await exchangeSiteUserLoginApiV1AdminAuthExchangeSiteUserPost();
    setAdminToken(res.token);
    const { data: me } = await meApiV1AdminAuthMeGet();
    setUser(me);
  }, []);

  const logout = useCallback(async () => {
    try {
      await logoutApiV1AdminAuthLogoutPost();
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
