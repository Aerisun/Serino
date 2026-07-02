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
    encrypt_runtime_data: true,
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
      remote_path: "/srv/serino-backups",
      remote_username: "serino-backup",
    },
    created_at: "2026-07-02T00:00:00+08:00",
    updated_at: "2026-07-02T00:00:00+08:00",
  });
  const defaultTestResponse = () => ({
    ok: true,
    summary: "SFTP 连接正常，远端目录可写。",
    latency_ms: 37,
    remote_path_preview: "/srv/serino-backups",
    recovery_key_ready: true,
    recovery_key_acknowledged: true,
    remote_history_state: "empty",
    remote_history_summary: "备份机可连接，未发现历史备份。",
    remote_repo_id: null,
    local_repo_id: null,
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
      testResponse: defaultTestResponse(),
      bootstrapClaim: null as any,
    },
    resetState() {
      this.state.config = defaultConfig();
      this.state.queue = [];
      this.state.runs = [];
      this.state.commits = [];
      this.state.bootstrapClaim = null;
      this.state.testResponse = defaultTestResponse();
    },
    invalidateQueries: vi.fn(),
    ensureCredentials: vi.fn(),
    exportRecoveryKey: vi.fn(),
    acknowledgeRecoveryKey: vi.fn(),
    probeConnection: vi.fn(),
    testConfig: vi.fn(),
    adminApiRequest: vi.fn(),
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

vi.mock("@/lib/adminApi", () => ({
  adminApiRequest: (...args: unknown[]) => api.adminApiRequest(...args),
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

function pageElement(queryClient: QueryClient) {
  return (
    <MemoryRouter future={{ v7_relativeSplatPath: true, v7_startTransition: true }}>
      <QueryClientProvider client={queryClient}>
        <LanguageProvider>
          <BackupsPage />
        </LanguageProvider>
      </QueryClientProvider>
    </MemoryRouter>
  );
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  const view = render(pageElement(queryClient));
  return {
    ...view,
    rerenderPage: () => view.rerender(pageElement(queryClient)),
  };
}

async function fillBackupMachineAddress(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByPlaceholderText(/10\.129\./), "backup.example.com");
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
  api.adminApiRequest.mockImplementation((path: string, init?: { method?: string; body?: any }) => {
    if (path === "/api/v1/admin/system/backup-sync/connection/probe" && init?.method === "POST") {
      api.probeConnection(init.body);
      return Promise.resolve(api.state.testResponse);
    }
    if (path === "/api/v1/admin/system/backup-sync/bootstrap-claims" && init?.method === "POST") {
      api.state.bootstrapClaim = {
        id: "claim-1",
        status: "pending",
        remote_host: init.body.remote_host,
        remote_port: init.body.remote_port ?? 22,
        remote_path: init.body.remote_path ?? "/srv/serino-backups",
        remote_username: init.body.remote_username ?? "serino-backup",
        site_slug: init.body.site_slug ?? "aerisun",
        credential_ref: init.body.credential_ref ?? "aerisun-backup-source",
        public_key_fingerprint: "SHA256:fixture",
        expires_at: new Date(Date.now() + 10 * 60 * 1000).toISOString(),
        used_at: null,
        completed_at: null,
        revoked_at: null,
        last_error: null,
        setup_url: "http://testserver/api/v1/backup/setup/claim-token.sh",
        setup_command: "curl -fsSL http://testserver/api/v1/backup/setup/claim-token.sh | sudo bash",
        created_at: "2026-07-02T00:00:00+08:00",
        updated_at: "2026-07-02T00:00:00+08:00",
      };
      return Promise.resolve(api.state.bootstrapClaim);
    }
    if (path === "/api/v1/admin/system/backup-sync/bootstrap-claims/claim-1/revoke") {
      api.state.bootstrapClaim = {
        ...api.state.bootstrapClaim,
        status: "revoked",
        revoked_at: "2026-07-02T00:03:00+08:00",
      };
      return Promise.resolve(api.state.bootstrapClaim);
    }
    if (path === "/api/v1/admin/system/backup-sync/bootstrap-claims/claim-1") {
      return Promise.resolve(api.state.bootstrapClaim);
    }
    if (path === "/api/v1/admin/system/backup-sync/remote-history/overwrite") {
      return Promise.resolve({
        ...api.state.testResponse,
        remote_history_state: "current",
        remote_history_summary: "当前站点的新备份历史已准备好。",
      });
    }
    if (path === "/api/v1/admin/system/backup-sync/reset") {
      return Promise.resolve({
        config: api.state.config,
        remote_cleanup_command: "sudo bash -c 'rm -rf /srv/serino-backups'",
      });
    }
    return Promise.reject(new Error(`Unhandled adminApiRequest: ${path}`));
  });
});

afterEach(() => {
  cleanup();
});

describe("BackupsPage usability", () => {
  it("asks for the recovery password before starting backup", async () => {
    const user = userEvent.setup();
    renderPage();

    await fillBackupMachineAddress(user);

    await user.click(screen.getByRole("button", { name: "启动备份" }));
    const dialog = await screen.findByRole("dialog");
    expect(api.triggerMutateAsync).not.toHaveBeenCalled();

    const passwordInputs = within(dialog).getAllByPlaceholderText("********");
    await user.type(passwordInputs[0], "super-safe-passphrase");
    await user.type(passwordInputs[1], "super-safe-passphrase");
    await user.click(within(dialog).getByRole("button", { name: "确认设置" }));

    await waitFor(() => {
      expect(screen.queryByRole("dialog")).toBeNull();
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
    api.state.config = {
      ...api.state.config,
      recovery_key_ready: true,
      recovery_key_acknowledged: true,
      active_recovery_key_fingerprint: "fingerprint-active",
    };
    const user = userEvent.setup();
    renderPage();

    await fillBackupMachineAddress(user);
    await user.click(screen.getByRole("button", { name: "检测" }));

    await waitFor(() => expect(screen.getAllByText("可连接").length).toBeGreaterThan(0));
    expect(screen.getByText("/srv/serino-backups")).not.toBeNull();
    expect(screen.getByText("37 ms")).not.toBeNull();
    expect(api.probeConnection).toHaveBeenCalledWith(
      expect.objectContaining({
        remote_host: "backup.example.com",
        remote_path: "/srv/serino-backups",
        remote_username: "serino-backup",
      }),
    );
    expect(api.testConfig).not.toHaveBeenCalled();
  });

  it("keeps the typed backup machine address when config refreshes", async () => {
    const user = userEvent.setup();
    const page = renderPage();

    await fillBackupMachineAddress(user);
    api.state.config = {
      ...api.state.config,
      updated_at: "2026-07-02T00:01:00+08:00",
    };
    page.rerenderPage();

    expect((screen.getByPlaceholderText(/10\.129\./) as HTMLInputElement).value).toBe("backup.example.com");
  });

  it("generates and copies a temporary backup machine command from the simple setup", async () => {
    const user = userEvent.setup();
    const clipboardWrite = vi.spyOn(navigator.clipboard, "writeText").mockResolvedValue(undefined);
    const rawSshError = "ssh: connect to host 0.18.201.127 port 22: Connection timed out Connection closed";
    api.state.testResponse = {
      ...api.state.testResponse,
      ok: false,
      summary: rawSshError,
      remote_history_state: "unreachable",
      remote_history_summary: rawSshError,
    };
    renderPage();

    await fillBackupMachineAddress(user);
    await user.click(screen.getByRole("button", { name: "检测" }));
    await screen.findByText("请生成临时命令，并在备份机终端上执行");
    expect(screen.getByText("未接入")).not.toBeNull();
    expect(screen.queryByText("固定备份目录")).toBeNull();
    expect(screen.queryByText("/srv/serino-backups")).toBeNull();
    expect(screen.queryByText(rawSshError)).toBeNull();
    expect(screen.queryByText("备份配置测试失败")).toBeNull();
    await user.click(screen.getByRole("button", { name: "生成临时命令" }));

    await waitFor(() => {
      expect(screen.getByText("curl -fsSL http://testserver/api/v1/backup/setup/claim-token.sh | sudo bash")).not.toBeNull();
    });
    expect(api.adminApiRequest).toHaveBeenCalledWith(
      "/api/v1/admin/system/backup-sync/bootstrap-claims",
      expect.objectContaining({
        method: "POST",
        body: expect.objectContaining({
          remote_host: "backup.example.com",
          remote_port: 22,
          remote_path: "/srv/serino-backups",
          remote_username: "serino-backup",
          ttl_minutes: 10,
        }),
      }),
    );

    await user.click(screen.getByRole("button", { name: "复制命令" }));
    expect(clipboardWrite).toHaveBeenCalledWith(
      "curl -fsSL http://testserver/api/v1/backup/setup/claim-token.sh | sudo bash",
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

    await fillBackupMachineAddress(user);
    await user.click(screen.getByRole("button", { name: "检测" }));
    await waitFor(() => expectButtonDisabled("启动备份", false));
    await user.click(screen.getByRole("button", { name: "启动备份" }));

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
          remote_path: "/srv/serino-backups",
          remote_username: "serino-backup",
        }),
      });
      expect(api.testConfig).toHaveBeenCalledTimes(1);
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
    expect(screen.getAllByText("提交记录").length).toBeGreaterThan(0);
    expect(screen.getByText("运行记录")).not.toBeNull();
    expect(screen.queryByText("远端提交 ID")).toBeNull();
    expect(screen.queryByText("remote-commit-1")).toBeNull();

    vi.mocked(window.confirm).mockReturnValueOnce(false);
    await user.click(screen.getByRole("button", { name: "恢复" }));
    expect(api.restoreMutate).not.toHaveBeenCalled();

    vi.mocked(window.confirm).mockReturnValueOnce(true);
    await user.click(screen.getByRole("button", { name: "恢复" }));
    expect(api.restoreMutate).toHaveBeenCalledWith({ commitId: "commit-1" });
  });
});
