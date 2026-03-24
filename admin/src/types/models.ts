/**
 * Compatibility re-exports from Orval-generated models.
 *
 * Existing code imports from `@/types/models`. This file re-exports the
 * generated types so we don't have to update every consumer at once.
 *
 * TODO: Gradually migrate consumers to import directly from
 * `@/api/generated/model` and then delete this file.
 */
export type {
  LoginRequest,
  LoginResponse,
  AdminUserRead as AdminUser,
  ContentAdminRead as ContentItem,
  ContentCreate,
  ContentUpdate,
  SiteProfileAdminRead as SiteProfile,
  SiteProfileUpdate,
  SocialLinkAdminRead as SocialLink,
  SocialLinkCreate,
  SocialLinkUpdate,
  PoemAdminRead as Poem,
  PoemCreate,
  PoemUpdate,
  PageCopyAdminRead as PageCopy,
  PageCopyCreate,
  PageCopyUpdate,
  PageDisplayOptionAdminRead as PageDisplayOption,
  PageDisplayOptionCreate,
  PageDisplayOptionUpdate,
  NavItemAdminRead as NavItem,
  NavItemCreate,
  NavItemUpdate,
  CommunityConfigAdminRead as CommunityConfig,
  CommunityConfigUpdate,
  AerisunApiAdminSchemasCommunitySurfaceRead as CommunitySurfaceConfig,
  ResumeBasicsAdminRead as ResumeBasics,
  ResumeBasicsCreate,
  ResumeBasicsUpdate,
  ResumeSkillGroupAdminRead as ResumeSkillGroup,
  ResumeSkillGroupCreate,
  ResumeSkillGroupUpdate,
  ResumeExperienceAdminRead as ResumeExperience,
  ResumeExperienceCreate,
  ResumeExperienceUpdate,
  FriendAdminRead as Friend,
  FriendCreate,
  FriendUpdate,
  FriendFeedSourceAdminRead as FriendFeedSource,
  FriendFeedSourceCreate,
  FriendFeedSourceUpdate,
  CommentAdminRead as Comment,
  GuestbookAdminRead as GuestbookEntry,
  ModerateAction,
  AssetAdminRead as Asset,
  ApiKeyAdminRead as ApiKey,
  ApiKeyCreate,
  ApiKeyUpdate,
  ApiKeyCreateResponse,
  AuditLogRead as AuditLog,
  BackupSnapshotRead as BackupSnapshot,
  EnhancedDashboardStats,
  MonthlyCount,
  RecentContentItem,
  BulkActionResponse,
} from "@/api/generated/model";

// Backwards-compatible PaginatedResponse generic type
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

// DashboardStats - alias for compatibility
export type { EnhancedDashboardStats as DashboardStats } from "@/api/generated/model";
