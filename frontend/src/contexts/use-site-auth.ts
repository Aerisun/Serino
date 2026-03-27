import { useContext } from "react";
import { SiteAuthContext } from "@/contexts/site-auth-context";

export function useSiteAuth() {
  const context = useContext(SiteAuthContext);
  if (!context) {
    throw new Error("useSiteAuth must be used within SiteAuthProvider");
  }
  return context;
}
