import type { QueryClient } from "@tanstack/react-query";
import { ensureAdminClientInitialized } from "@/lib/adminClient";
import { prefetchDashboardStats } from "@/pages/dashboard/dashboardQueries";
import { prefetchPendingModerationCount } from "@/pages/moderation/moderationQueries";

type RouteWarmup = {
  key: string;
  match: (path: string) => boolean;
  warm: (queryClient: QueryClient) => Promise<unknown>;
};

const routeWarmups: RouteWarmup[] = [
  {
    key: "/",
    match: (path) => path === "/",
    warm: (queryClient) =>
      Promise.all([
        import("@/layouts/AdminLayout"),
        import("@/pages/DashboardPage"),
        prefetchDashboardStats(queryClient),
        prefetchPendingModerationCount(queryClient),
      ]),
  },
  {
    key: "/moderation",
    match: (path) => path === "/moderation",
    warm: async (queryClient) => {
      await ensureAdminClientInitialized();
      return Promise.all([
        import("@/pages/moderation/ModerationPage"),
        prefetchPendingModerationCount(queryClient),
      ]);
    },
  },
  {
    key: "/agent",
    match: (path) => path === "/agent",
    warm: async () => {
      await ensureAdminClientInitialized();
      return import("@/pages/automation/AgentPage");
    },
  },
];

const inflightWarmups = new Map<string, Promise<void>>();

function normalizeRoutePath(to: string) {
  const url = new URL(to, window.location.origin);
  const normalized = url.pathname.replace(/\/+$/, "");
  return normalized || "/";
}

export function warmAdminRoute(to: string, queryClient: QueryClient) {
  const path = normalizeRoutePath(to);
  const warmup = routeWarmups.find((candidate) => candidate.match(path));
  if (!warmup) {
    return undefined;
  }

  const existing = inflightWarmups.get(warmup.key);
  if (existing) {
    return existing;
  }

  const promise = Promise.resolve(warmup.warm(queryClient))
    .then(() => undefined)
    .catch((error) => {
      inflightWarmups.delete(warmup.key);
      throw error;
    });

  inflightWarmups.set(warmup.key, promise);
  return promise;
}
