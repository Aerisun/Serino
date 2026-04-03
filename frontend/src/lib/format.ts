import { translateFrontendText } from "@/i18n";

export function formatPostCount(count: number): string {
  return translateFrontendText("format.postCount", { count }, `${count} 篇文章`);
}

export function formatSiteCount(count: number): string {
  return translateFrontendText("format.siteCount", { count }, `${count} 个站点`);
}

export function formatFriendCircleSubtitle(
  total: number,
  active: number,
): string {
  return translateFrontendText(
    "format.friendCircleSubtitle",
    { total, active },
    `${total} links · ${active} articles in total`,
  );
}
