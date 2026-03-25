export const queryKeys = {
  posts: {
    all: ["posts"] as const,
    lists: () => [...queryKeys.posts.all, "list"] as const,
    list: (params: Record<string, unknown>) =>
      [...queryKeys.posts.lists(), params] as const,
    detail: (slug: string) =>
      [...queryKeys.posts.all, "detail", slug] as const,
  },
  diary: {
    all: ["diary"] as const,
    lists: () => [...queryKeys.diary.all, "list"] as const,
    list: (params: Record<string, unknown>) =>
      [...queryKeys.diary.lists(), params] as const,
    detail: (slug: string) =>
      [...queryKeys.diary.all, "detail", slug] as const,
  },
  thoughts: {
    all: ["thoughts"] as const,
    lists: () => [...queryKeys.thoughts.all, "list"] as const,
    list: (params: Record<string, unknown>) =>
      [...queryKeys.thoughts.lists(), params] as const,
    detail: (slug: string) =>
      [...queryKeys.thoughts.all, "detail", slug] as const,
  },
  excerpts: {
    all: ["excerpts"] as const,
    lists: () => [...queryKeys.excerpts.all, "list"] as const,
    list: (params: Record<string, unknown>) =>
      [...queryKeys.excerpts.lists(), params] as const,
    detail: (slug: string) =>
      [...queryKeys.excerpts.all, "detail", slug] as const,
  },
  friends: {
    all: ["friends"] as const,
    list: () => [...queryKeys.friends.all, "list"] as const,
    feed: () => [...queryKeys.friends.all, "feed"] as const,
  },
  site: {
    all: ["site"] as const,
    config: () => [...queryKeys.site.all, "config"] as const,
    community: () => [...queryKeys.site.all, "community"] as const,
    pages: () => [...queryKeys.site.all, "pages"] as const,
  },
  activity: {
    all: ["activity"] as const,
    heatmap: () => [...queryKeys.activity.all, "heatmap"] as const,
    recent: () => [...queryKeys.activity.all, "recent"] as const,
  },
  calendar: {
    all: ["calendar"] as const,
    events: () => [...queryKeys.calendar.all, "events"] as const,
  },
} as const;
