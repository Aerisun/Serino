// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import BackupsPage from "../src/pages/system/BackupsPage";
import { LanguageProvider } from "../src/i18n";

const api = vi.hoisted(() => {
  const defaultConfig = () => ({
    id: "config-1",
    enabled: false,
    paused: false,
    interval_minutes: 60,
    transport_mode: "sftp",
    site_slug: "aerisun",
    credential_ref: "aerisun-backup-source",
    encrypt_runtime_data: false,
    max_retries: 3,
    retry_backoff_seconds: 300,
    max_retention_count: 0,
    last_scheduled_at: null,
    last_synced_at: null,
    last_error: null,
    recovery_key_ready: false,
    recovery_key_acknowledged: false,
    active_recovery_key_fingerprint: null,
    archived_recovery_key_count: 0,
    transport: {
      mode: "sftp",
      remote_host: "",
      remote_port: 22,
      remote_path: "",
      remote_username: "",
    },
    created_at: "2026-07-02T00:00:00+08:00",
    updated_at: "2026-07-02T00:00:00+08:00",
  });

  return {
    state: {
      config: defaultConfig(),
      queue: [] as any[],
      runs: [] as any[],
      commits: [] as any[],
      ensureResponse: {
        credential_ref: "aerisun-backup-source",
        site_slug: "aerisun",
        credential_dir: ".store/secrets/backup-sync/aerisun-backup-source",
        secrets_fingerprint: "fingerprint-active",
        created: false,
        archived_fingerprints: [],
      },
      exportResponse: {
        credential_ref: "aerisun-backup-source",
        site_slug: "aerisun",
        credential_dir: ".store/secrets/backup-sync/aerisun-backup-source",
        secrets_fingerprint: "fingerprint-active",
        archived_fingerprints: [],
        rotated: false,
        filename: "aerisun-backup-source-fingerprint.pem",
        private_key_pem: "recovery-key-export-fixture",
      },
      testResponse: {
        ok: true,
        summary: "SFTP 连接正常，远端目录可写。",
        latency_ms: 37,
        remote_path_preview: "/srv/aerisun/backup",
        recovery_key_ready: true,
        recovery_key_acknowledged: true,
      },
    },
    resetState() {
      this.state.config = defaultConfig();
      this.state.queue = [];
      this.state.runs = [];
      this.state.commits = [];
    },
    invalidateQueries: vi.fn(),
    ensureCredentials: vi.fn(),
    exportRecoveryKey: vi.fn(),
    acknowledgeRecoveryKey: vi.fn(),
    testConfig: vi.fn(),
    updateMutateAsync: vi.fn(),
    triggerMutateAsync: vi.fn(),
    triggerMutate: vi.fn(),
    pauseMutate: vi.fn(),
    resumeMutate: vi.fn(),
    retryMutate: vi.fn(),
    restoreMutate: vi.fn(),
    toastSuccess: vi.fn(),
    toastError: vi.fn(),
  };
});

vi.mock("@serino/api-client/admin", () => ({
  getGetBackupSyncConfigApiV1AdminSystemBackupSyncConfigGetQueryKey: () => ["backup-config"],
  getListBackupSyncCommitsApiV1AdminSystemBackupSyncCommitsGetQueryKey: () => ["backup-commits"],
  getListBackupSyncQueueApiV1AdminSystemBackupSyncQueueGetQueryKey: () => ["backup-queue"],
  getListBackupSyncRunsApiV1AdminSystemBackupSyncRunsGetQueryKey: () => ["backup-runs"],
  useGetBackupSyncConfigApiV1AdminSystemBackupSyncConfigGet: () => ({
    data: { data: api.state.config },
    isLoading: false,
  }),
  useListBackupSyncQueueApiV1AdminSystemBackupSyncQueueGet: () => ({
    data: { data: api.state.queue },
    isLoading: false,
  }),
  useListBackupSyncRunsApiV1AdminSystemBackupSyncRunsGet: () => ({
    data: { data: api.state.runs },
    isLoading: false,
  }),
  useListBackupSyncCommitsApiV1AdminSystemBackupSyncCommitsGet: () => ({
    data: { data: api.state.commits },
    isLoading: false,
  }),
  useUpdateBackupSyncConfigApiV1AdminSystemBackupSyncConfigPut: () => ({
    mutateAsync: api.updateMutateAsync,
    isPending: false,
  }),
  useTriggerBackupSyncApiV1AdminSystemBackupSyncRunsPost: () => ({
    mutateAsync: api.triggerMutateAsync,
    mutate: api.triggerMutate,
    isPending: false,
  }),
  usePauseBackupSyncApiV1AdminSystemBackupSyncPausePost: () => ({
    mutate: api.pauseMutate,
    isPending: false,
  }),
  useResumeBackupSyncApiV1AdminSystemBackupSyncResumePost: () => ({
    mutate: api.resumeMutate,
    isPending: false,
  }),
  useRetryBackupSyncApiV1AdminSystemBackupSyncRunsRunIdRetryPost: () => ({
    mutate: api.retryMutate,
    isPending: false,
  }),
  useRestoreBackupCommitApiV1AdminSystemBackupSyncCommitsCommitIdRestorePost: () => ({
    mutate: api.restoreMutate,
    isPending: false,
  }),
  ensureBackupCredentialsApiV1AdminSystemBackupSyncCredentialsEnsurePost: (payload: unknown) => {
    api.ensureCredentials(payload);
    return Promise.resolve({ data: api.state.ensureResponse });
  },
  exportBackupRecoveryKeyApiV1AdminSystemBackupSyncRecoveryKeyExportPost: (payload: unknown) => {
    api.exportRecoveryKey(payload);
    return Promise.resolve({ data: api.state.exportResponse });
  },
  acknowledgeBackupRecoveryKeyApiV1AdminSystemBackupSyncRecoveryKeyAcknowledgePost: (payload: unknown) => {
    api.acknowledgeRecoveryKey(payload);
    return Promise.resolve({ data: api.state.ensureResponse });
  },
  testBackupSyncConfigApiV1AdminSystemBackupSyncConfigTestPost: (payload: unknown) => {
    api.testConfig(payload);
    return Promise.resolve({ data: api.state.testResponse });
  },
}));

vi.mock("sonner", () => ({
  toast: {
    success: api.toastSuccess,
    error: api.toastError,
  },
}));

vi.mock("@tanstack/react-query", async () => {
  const actual = await vi.importActual<typeof import("@tanstack/react-query")>("@tanstack/react-query");
  return {
    ...actual,
    useQueryClient: () => ({
      invalidateQueries: api.invalidateQueries,
    }),
  };
});

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(
    <MemoryRouter future={{ v7_relativeSplatPath: true, v7_startTransition: true }}>
      <QueryClientProvider client={queryClient}>
        <LanguageProvider>
          <BackupsPage />
        </LanguageProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

async function fillSftpFields(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByPlaceholderText("backup.example.com"), "backup.example.com");
  await user.type(screen.getByPlaceholderText("backup-user"), "backup-user");
  await user.type(screen.getByPlaceholderText("/home/<ssh-user>/aerisun-backups"), "/srv/aerisun/backup");
}

function expectButtonDisabled(name: string, disabled: boolean) {
  const button = screen.getByRole("button", { name }) as HTMLButtonElement;
  expect(button.disabled).toBe(disabled);
}

function buttonContainingText(text: string) {
  const button = screen.getByText(text).closest("button");
  expect(button).not.toBeNull();
  return button as HTMLButtonElement;
}

beforeEach(() => {
  api.resetState();
  vi.clearAllMocks();
  localStorage.clear();
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation(() => ({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  });
  HTMLElement.prototype.scrollIntoView = vi.fn();
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: {
      writeText: vi.fn().mockResolvedValue(undefined),
    },
  });
  window.confirm = vi.fn();
  api.updateMutateAsync.mockResolvedValue({ data: api.state.config });
  api.triggerMutateAsync.mockResolvedValue({ data: { id: "run-1", status: "completed" } });
});

afterEach(() => {
  cleanup();
});

describe("BackupsPage usability", () => {
  it("blocks saving and first backup until the recovery key is exported and acknowledged", async () => {
    const user = userEvent.setup();
    renderPage();

    await fillSftpFields(user);

    expectButtonDisabled("保存", true);
    expectButtonDisabled("保存并创建首次备份", true);

    await user.click(screen.getByRole("button", { name: "获取恢复私钥" }));
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByPlaceholderText("********"), "super-safe-passphrase");
    await user.click(within(dialog).getByRole("button", { name: "获取恢复私钥" }));

    await user.click(await within(dialog).findByRole("button", { name: "复制恢复私钥" }));
    await user.click(within(dialog).getByRole("button", { name: "完成" }));

    await waitFor(() => {
      expectButtonDisabled("保存", false);
      expectButtonDisabled("保存并创建首次备份", false);
    });
    expect(api.exportRecoveryKey).toHaveBeenCalledWith({
      credential_ref: "aerisun-backup-source",
      site_slug: "aerisun",
      passphrase: "super-safe-passphrase",
      rotate: false,
    });
    expect(api.acknowledgeRecoveryKey).toHaveBeenCalledWith({
      credential_ref: "aerisun-backup-source",
    });
  });

  it("shows backup configuration test status, remote path, and latency", async () => {
    const user = userEvent.setup();
    renderPage();

    await fillSftpFields(user);
    await user.click(screen.getByRole("button", { name: "测试配置" }));

    await waitFor(() => expect(screen.getAllByText("可连接").length).toBeGreaterThan(0));
    expect(screen.getByText("/srv/aerisun/backup")).not.toBeNull();
    expect(screen.getByText("37 ms")).not.toBeNull();
    expect(api.testConfig).toHaveBeenCalledWith(
      expect.objectContaining({
        remote_host: "backup.example.com",
        remote_path: "/srv/aerisun/backup",
        remote_username: "backup-user",
      }),
    );
  });

  it("saves settings and triggers the first backup from one action", async () => {
    api.state.config = {
      ...api.state.config,
      recovery_key_ready: true,
      recovery_key_acknowledged: true,
      active_recovery_key_fingerprint: "fingerprint-active",
    };
    const user = userEvent.setup();
    renderPage();

    await fillSftpFields(user);
    await user.click(screen.getByRole("button", { name: "保存并创建首次备份" }));

    await waitFor(() => {
      expect(api.ensureCredentials).toHaveBeenCalledWith({
        credential_ref: "aerisun-backup-source",
        site_slug: "aerisun",
        force: false,
      });
      expect(api.updateMutateAsync).toHaveBeenCalledWith({
        data: expect.objectContaining({
          enabled: true,
          transport_mode: "sftp",
          credential_ref: "aerisun-backup-source",
          site_slug: "aerisun",
          remote_host: "backup.example.com",
          remote_path: "/srv/aerisun/backup",
          remote_username: "backup-user",
        }),
      });
      expect(api.triggerMutateAsync).toHaveBeenCalledTimes(1);
    });
  });

  it("asks for confirmation before restoring a backup commit", async () => {
    api.state.commits = [
      {
        id: "commit-1",
        transport: "sftp",
        trigger_kind: "manual",
        site_slug: "aerisun",
        remote_commit_id: "remote-commit-1",
        manifest_digest: "manifest-digest",
        backup_path: "/srv/aerisun/backup/manifest.json",
        datasets: {},
        stats_json: {},
        snapshot_started_at: "2026-07-02T00:00:00+08:00",
        snapshot_finished_at: "2026-07-02T00:01:00+08:00",
        restored_at: null,
        created_at: "2026-07-02T00:00:00+08:00",
        updated_at: "2026-07-02T00:01:00+08:00",
      },
    ];
    const user = userEvent.setup();
    renderPage();

    await user.click(buttonContainingText("记录"));
    await user.click(buttonContainingText("提交记录"));
    vi.mocked(window.confirm).mockReturnValueOnce(false);
    await user.click(screen.getByRole("button", { name: "恢复" }));
    expect(api.restoreMutate).not.toHaveBeenCalled();

    vi.mocked(window.confirm).mockReturnValueOnce(true);
    await user.click(screen.getByRole("button", { name: "恢复" }));
    expect(api.restoreMutate).toHaveBeenCalledWith({ commitId: "commit-1" });
  });
});
