import { createContext } from "react";
import type { SiteAuthUser } from "@/lib/site-auth";

export interface SiteAuthContextValue {
  user: SiteAuthUser | null;
  loading: boolean;
  emailLoginEnabled: boolean;
  oauthProviders: string[];
  openLogin: (options?: { allowEmailLogin?: boolean }) => void;
  openProfileEditor: () => void;
  closeLogin: () => void;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

export const SiteAuthContext = createContext<SiteAuthContextValue | null>(null);
