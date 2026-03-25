import { createContext, useState, useEffect, useCallback, type ReactNode } from "react";
import type { AdminUserRead } from "@serino/api-client/models";
import { getMe, login as apiLogin, logout as apiLogout } from "@/api/endpoints/auth";
import { clearAdminToken, getAdminToken, setAdminToken } from "@/lib/storage";

interface AuthState {
  user: AdminUserRead | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (username: string, password: string) => Promise<void>;
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

  const logout = useCallback(async () => {
    try {
      await apiLogout();
    } finally {
      clearAdminToken();
      setUser(null);
    }
  }, []);

  return (
    <AuthContext.Provider value={{ user, isLoading, isAuthenticated: !!user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
