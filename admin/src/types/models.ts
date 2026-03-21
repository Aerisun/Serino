// ---- Auth ----
export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  token: string;
  expires_at: string;
}

export interface AdminUser {
  id: string;
  username: string;
  is_active: boolean;
  created_at: string;
}

// ---- Content (Post, Diary, Thought, Excerpt) ----
export interface ContentItem {
  id: string;
  slug: string;
  title: string;
  summary: string | null;
  body: string;
  tags: string[];
  status: string;
  visibility: string;
  published_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ContentCreate {
  slug: string;
  title: string;
  summary?: string | null;
  body: string;
  tags?: string[];
  status?: string;
  visibility?: string;
  published_at?: string | null;
}

export interface ContentUpdate {
  slug?: string;
  title?: string;
  summary?: string | null;
  body?: string;
  tags?: string[];
  status?: string;
  visibility?: string;
  published_at?: string | null;
}

// ---- Site Profile ----
export interface SiteProfile {
  id: string;
  name: string;
  title: string;
  bio: string;
  role: string;
  footer_text: string;
  created_at: string;
  updated_at: string;
}

export interface SiteProfileUpdate {
  name?: string;
  title?: string;
  bio?: string;
  role?: string;
  footer_text?: string;
}

// ---- Social Link ----
export interface SocialLink {
  id: string;
  site_profile_id: string;
  name: string;
  href: string;
  icon_key: string;
  placement: string;
  order_index: number;
  created_at: string;
  updated_at: string;
}

export interface SocialLinkCreate {
  site_profile_id: string;
  name: string;
  href: string;
  icon_key: string;
  placement?: string;
  order_index?: number;
}

export interface SocialLinkUpdate {
  name?: string;
  href?: string;
  icon_key?: string;
  placement?: string;
  order_index?: number;
}

// ---- Poem ----
export interface Poem {
  id: string;
  site_profile_id: string;
  order_index: number;
  content: string;
  created_at: string;
  updated_at: string;
}

export interface PoemCreate {
  site_profile_id: string;
  order_index?: number;
  content: string;
}

export interface PoemUpdate {
  order_index?: number;
  content?: string;
}

// ---- PageCopy ----
export interface PageCopy {
  id: string;
  page_key: string;
  label: string | null;
  title: string;
  subtitle: string;
  description: string | null;
  search_placeholder: string | null;
  empty_message: string | null;
  max_width: string | null;
  page_size: number | null;
  download_label: string | null;
  extras: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface PageCopyCreate {
  page_key: string;
  label?: string | null;
  title: string;
  subtitle: string;
  description?: string | null;
  search_placeholder?: string | null;
  empty_message?: string | null;
  max_width?: string | null;
  page_size?: number | null;
  download_label?: string | null;
  extras?: Record<string, any>;
}

export interface PageCopyUpdate {
  label?: string | null;
  title?: string;
  subtitle?: string;
  description?: string | null;
  search_placeholder?: string | null;
  empty_message?: string | null;
  max_width?: string | null;
  page_size?: number | null;
  download_label?: string | null;
  extras?: Record<string, any>;
}

// ---- PageDisplayOption ----
export interface PageDisplayOption {
  id: string;
  page_key: string;
  is_enabled: boolean;
  settings: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface PageDisplayOptionCreate {
  page_key: string;
  is_enabled?: boolean;
  settings?: Record<string, any>;
}

export interface PageDisplayOptionUpdate {
  is_enabled?: boolean;
  settings?: Record<string, any>;
}

// ---- Resume ----
export interface ResumeBasics {
  id: string;
  title: string;
  subtitle: string;
  summary: string;
  download_label: string;
  created_at: string;
  updated_at: string;
}

export interface ResumeBasicsCreate {
  title: string;
  subtitle: string;
  summary: string;
  download_label: string;
}

export interface ResumeBasicsUpdate {
  title?: string;
  subtitle?: string;
  summary?: string;
  download_label?: string;
}

export interface ResumeSkillGroup {
  id: string;
  resume_basics_id: string;
  category: string;
  items: string[];
  order_index: number;
  created_at: string;
  updated_at: string;
}

export interface ResumeSkillGroupCreate {
  resume_basics_id: string;
  category: string;
  items?: string[];
  order_index?: number;
}

export interface ResumeSkillGroupUpdate {
  category?: string;
  items?: string[];
  order_index?: number;
}

export interface ResumeExperience {
  id: string;
  resume_basics_id: string;
  title: string;
  company: string;
  period: string;
  summary: string;
  order_index: number;
  created_at: string;
  updated_at: string;
}

export interface ResumeExperienceCreate {
  resume_basics_id: string;
  title: string;
  company: string;
  period: string;
  summary: string;
  order_index?: number;
}

export interface ResumeExperienceUpdate {
  title?: string;
  company?: string;
  period?: string;
  summary?: string;
  order_index?: number;
}

// ---- Friend ----
export interface Friend {
  id: string;
  name: string;
  url: string;
  avatar_url: string | null;
  description: string | null;
  status: string;
  order_index: number;
  created_at: string;
  updated_at: string;
}

export interface FriendCreate {
  name: string;
  url: string;
  avatar_url?: string | null;
  description?: string | null;
  status?: string;
  order_index?: number;
}

export interface FriendUpdate {
  name?: string;
  url?: string;
  avatar_url?: string | null;
  description?: string | null;
  status?: string;
  order_index?: number;
}

export interface FriendFeedSource {
  id: string;
  friend_id: string;
  feed_url: string;
  last_fetched_at: string | null;
  is_enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface FriendFeedSourceCreate {
  friend_id: string;
  feed_url: string;
  is_enabled?: boolean;
}

export interface FriendFeedSourceUpdate {
  feed_url?: string;
  is_enabled?: boolean;
}

// ---- Moderation ----
export interface Comment {
  id: string;
  content_type: string;
  content_slug: string;
  parent_id: string | null;
  author_name: string;
  author_email: string | null;
  body: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface GuestbookEntry {
  id: string;
  name: string;
  email: string | null;
  website: string | null;
  body: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface ModerateAction {
  action: "approve" | "reject" | "delete";
  reason?: string | null;
}

// ---- Asset ----
export interface Asset {
  id: string;
  file_name: string;
  storage_path: string;
  mime_type: string | null;
  byte_size: number | null;
  sha256: string | null;
  created_at: string;
  updated_at: string;
}

// ---- System ----
export interface ApiKey {
  id: string;
  key_name: string;
  key_prefix: string;
  scopes: string[];
  last_used_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ApiKeyCreate {
  key_name: string;
  scopes?: string[];
}

export interface ApiKeyUpdate {
  key_name?: string;
  scopes?: string[];
}

export interface ApiKeyCreateResponse {
  item: ApiKey;
  raw_key: string;
}

export interface AuditLog {
  id: string;
  actor_type: string;
  actor_id: string | null;
  action: string;
  target_type: string | null;
  target_id: string | null;
  payload: Record<string, any>;
  created_at: string;
}

export interface BackupSnapshot {
  id: string;
  snapshot_type: string;
  status: string;
  db_path: string;
  replica_url: string | null;
  backup_path: string | null;
  checksum: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface DashboardStats {
  posts: number;
  diary_entries: number;
  thoughts: number;
  excerpts: number;
  comments: number;
  guestbook_entries: number;
  friends: number;
  assets: number;
  reactions: number;
  sync_runs: number;
}

// ---- Paginated ----
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}
