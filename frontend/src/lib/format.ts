export function formatPostCount(count: number): string {
  return `${count} 篇文章`;
}

export function formatSiteCount(count: number): string {
  return `${count} 个站点`;
}

export function formatFriendCircleSubtitle(
  total: number,
  active: number,
): string {
  return `${total} links · ${active} articles in total`;
}
