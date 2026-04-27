import { createContext, useState, useEffect, useCallback, type ReactNode } from "react";
import type { AdminUserRead } from "@serino/api-client/models";
import {
  exchangeSiteAdminLogin,
  getCurrentAdmin,
  loginAdmin,
  loginWithAdminEmail as loginWithAdminEmailRequest,
  logoutAdmin,
} from "./adminAuthApi";
import { clearAdminToken, getAdminToken, setAdminToken } from "@/lib/storage";

interface AuthState {
  user: AdminUserRead | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (username: string, password: string) => Promise<void>;
  loginWithAdminEmail: (email: string, password: string) => Promise<void>;
  exchangeSiteUserLogin: () => Promise<void>;
  logout: () => Promise<void>;
}

export const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AdminUserRead | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const token = getAdminToken();
    if (!token) {
      setIsLoading(false);
      return;
    }
    getCurrentAdmin()
      .then(setUser)
      .catch(clearAdminToken)
      .finally(() => setIsLoading(false));
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const res = await loginAdmin(username, password);
    setAdminToken(res.token);
    const me = await getCurrentAdmin();
    setUser(me);
  }, []);

  const loginWithAdminEmail = useCallback(async (email: string, password: string) => {
    const res = await loginWithAdminEmailRequest(email, password);
    setAdminToken(res.token);
    const me = await getCurrentAdmin();
    setUser(me);
  }, []);

  const exchangeSiteUserLogin = useCallback(async () => {
    const res = await exchangeSiteAdminLogin();
    setAdminToken(res.token);
    const me = await getCurrentAdmin();
    setUser(me);
  }, []);

  const logout = useCallback(async () => {
    try {
      await logoutAdmin();
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
