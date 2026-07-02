// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, render, screen, waitFor, within } from "@testing-library/react";
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
    remotePreviewError: null as any,
  },
    resetState() {
      this.state.config = defaultConfig();
      this.state.queue = [];
      this.state.runs = [];
      this.state.commits = [];
      this.state.bootstrapClaim = null;
      this.state.remotePreviewError = null;
      this.state.testResponse = defaultTestResponse();
    },
    invalidateQueries: vi.fn(),
    setQueryData: vi.fn(),
    ensureCredentials: vi.fn(),
    exportRecoveryKey: vi.fn(),
    acknowledgeRecoveryKey: vi.fn(),
    probeConnection: vi.fn(),
    testConfig: vi.fn(),
    overwriteRemoteHistory: vi.fn(),
    previewRemoteHistoryImport: vi.fn(),
    restoreRemoteHistoryImport: vi.fn(),
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
  probeBackupMachineConnectionApiV1AdminSystemBackupSyncConnectionProbePost: (payload: unknown) => {
    api.probeConnection(payload);
    return Promise.resolve({ data: api.state.testResponse });
  },
  testBackupSyncConfigApiV1AdminSystemBackupSyncConfigTestPost: (payload: unknown) => {
    api.testConfig(payload);
    return Promise.resolve({ data: api.state.testResponse });
  },
  overwriteRemoteBackupHistoryApiV1AdminSystemBackupSyncRemoteHistoryOverwritePost: (payload: unknown) => {
    api.overwriteRemoteHistory(payload);
    return Promise.resolve({
      data: {
        ...api.state.testResponse,
        remote_history_state: "current",
        remote_history_summary: "当前站点的新备份历史已准备好。",
      },
    });
  },
  previewRemoteBackupHistoryImportApiV1AdminSystemBackupSyncRemoteHistoryImportPreviewPost: (payload: unknown) => {
    api.previewRemoteHistoryImport(payload);
    if (api.state.remotePreviewError) {
      return Promise.reject(api.state.remotePreviewError);
    }
    return Promise.resolve({
      data: {
        remote_repo_id: "remote-repo-1",
        site_slug: "aerisun",
        credential_ref: "aerisun-backup-source",
        key_fingerprints: ["fingerprint-active"],
        commits: [
          {
            id: "commit-remote-1",
            remote_commit_id: "commit-remote-1",
            manifest_digest: "manifest-digest",
            backup_path: "/srv/serino-backups/current/commits/commit-remote-1/manifest.json",
            created_at: "2026-07-02T00:00:00+08:00",
          },
        ],
      },
    });
  },
  restoreRemoteBackupHistoryApiV1AdminSystemBackupSyncRemoteHistoryImportRestorePost: (payload: any) => {
    api.restoreRemoteHistoryImport(payload);
    return Promise.resolve({
      data: {
        id: payload.commit_id,
        transport: "sftp",
        trigger_kind: "manual",
        site_slug: "aerisun",
        remote_commit_id: payload.commit_id,
        manifest_digest: "manifest-digest",
        backup_path: "/srv/serino-backups/current/commits/commit-remote-1/manifest.json",
        datasets: {},
        stats_json: {},
        snapshot_started_at: "2026-07-02T00:00:00+08:00",
        snapshot_finished_at: "2026-07-02T00:01:00+08:00",
        restored_at: "2026-07-02T00:02:00+08:00",
        created_at: "2026-07-02T00:00:00+08:00",
        updated_at: "2026-07-02T00:02:00+08:00",
      },
    });
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
      setQueryData: api.setQueryData,
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
  Object.defineProperty(document, "execCommand", {
    configurable: true,
    value: vi.fn().mockReturnValue(true),
  });
  window.confirm = vi.fn();
  api.updateMutateAsync.mockResolvedValue({ data: api.state.config });
  api.triggerMutateAsync.mockResolvedValue({ data: { id: "run-1", status: "completed" } });
  api.adminApiRequest.mockImplementation((path: string, init?: { method?: string; body?: any }) => {
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
  vi.useRealTimers();
  cleanup();
});

describe("BackupsPage usability", () => {
  it("keeps recovery password disabled until backup machine detection is safe", async () => {
    const user = userEvent.setup();
    renderPage();

    expectButtonDisabled("设置恢复密码", true);

    await fillBackupMachineAddress(user);
    await user.click(screen.getByRole("button", { name: "检测" }));

    await waitFor(() => expectButtonDisabled("设置恢复密码", false));
  });

  it("does not scroll the page back to the section tabs during status refreshes", async () => {
    const scrollIntoView = vi.mocked(HTMLElement.prototype.scrollIntoView);
    const page = renderPage();

    await act(async () => {
      await new Promise((resolve) => window.requestAnimationFrame(resolve));
    });
    scrollIntoView.mockClear();

    api.state.queue = [
      {
        id: "queue-1",
        status: "running",
        transport: "sftp",
        trigger_kind: "manual",
        dataset_versions: {},
        verified_chunks: [],
        retry_count: 0,
        next_retry_at: null,
        last_error: null,
        created_at: "2026-07-02T00:00:00+08:00",
        updated_at: "2026-07-02T00:00:01+08:00",
      },
    ];
    page.rerenderPage();

    await act(async () => {
      await new Promise((resolve) => window.requestAnimationFrame(resolve));
    });
    expect(scrollIntoView).not.toHaveBeenCalled();
  });

  it("allows replacing the recovery password when local history exists but the remote backup machine is empty", async () => {
    api.state.config = {
      ...api.state.config,
      recovery_key_ready: true,
      recovery_key_acknowledged: true,
      active_recovery_key_fingerprint: "fingerprint-active",
    };
    api.state.commits = [
      {
        id: "commit-local-1",
        transport: "sftp",
        trigger_kind: "manual",
        site_slug: "aerisun",
        remote_commit_id: "commit-local-1",
        manifest_digest: "manifest-digest",
        backup_path: "/srv/serino-backups/current/commits/commit-local-1/manifest.json",
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

    await fillBackupMachineAddress(user);
    await user.click(screen.getByRole("button", { name: "检测" }));
    const resetButton = await screen.findByRole("button", {
      name: "重新设置恢复密码",
    });
    expect((resetButton as HTMLButtonElement).disabled).toBe(false);

    await user.click(resetButton);
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("重新设置恢复密码")).not.toBeNull();
    const passwordInputs = within(dialog).getAllByPlaceholderText("********");
    await user.type(passwordInputs[0], "new-safe-passphrase");
    await user.type(passwordInputs[1], "new-safe-passphrase");
    await user.click(within(dialog).getByRole("button", { name: "确认重新设置" }));

    await waitFor(() => {
      expect(api.exportRecoveryKey).toHaveBeenCalledWith({
        credential_ref: "aerisun-backup-source",
        site_slug: "aerisun",
        passphrase: "new-safe-passphrase",
        rotate: true,
      });
      expect(api.overwriteRemoteHistory).toHaveBeenCalledWith(
        expect.objectContaining({
          remote_host: "backup.example.com",
        }),
      );
      expect(api.setQueryData).toHaveBeenCalledWith(["backup-queue"], expect.any(Function));
      expect(api.setQueryData).toHaveBeenCalledWith(["backup-runs"], expect.any(Function));
      expect(api.setQueryData).toHaveBeenCalledWith(["backup-commits"], expect.any(Function));
    });
  });

  it("requires a new recovery password before overwriting foreign remote history", async () => {
    api.state.config = {
      ...api.state.config,
      recovery_key_ready: true,
      recovery_key_acknowledged: true,
      active_recovery_key_fingerprint: "fingerprint-active",
    };
    api.state.testResponse = {
      ...api.state.testResponse,
      ok: true,
      summary: "这台备份机上已有另一套备份历史。",
      remote_history_state: "foreign",
      remote_history_summary: "这台备份机上已有另一套备份历史。为避免数据混乱，不能直接继续写入。",
      remote_repo_id: "remote-repo-1",
      local_repo_id: "local-repo-2",
    };
    window.confirm = vi.fn(() => true) as any;
    const user = userEvent.setup();
    renderPage();

    await fillBackupMachineAddress(user);
    await user.click(screen.getByRole("button", { name: "检测" }));
    await user.click(await screen.findByRole("button", { name: "覆盖远端历史" }));
    const resetButton = await screen.findByRole("button", {
      name: "重新设置恢复密码",
    });

    await user.click(resetButton);
    const dialog = await screen.findByRole("dialog");
    const passwordInputs = within(dialog).getAllByPlaceholderText("********");
    await user.type(passwordInputs[0], "overwrite-passphrase");
    await user.type(passwordInputs[1], "overwrite-passphrase");
    await user.click(within(dialog).getByRole("button", { name: "确认重新设置" }));

    await waitFor(() => {
      expect(api.exportRecoveryKey).toHaveBeenCalledWith({
        credential_ref: "aerisun-backup-source",
        site_slug: "aerisun",
        passphrase: "overwrite-passphrase",
        rotate: true,
      });
      expect(api.overwriteRemoteHistory).toHaveBeenCalledWith(
        expect.objectContaining({
          remote_host: "backup.example.com",
        }),
      );
      expect(api.setQueryData).toHaveBeenCalledWith(["backup-queue"], expect.any(Function));
      expect(api.setQueryData).toHaveBeenCalledWith(["backup-runs"], expect.any(Function));
      expect(api.setQueryData).toHaveBeenCalledWith(["backup-commits"], expect.any(Function));
    });
  });

  it("requires an explicit overwrite choice before setting a password for foreign history", async () => {
    api.state.testResponse = {
      ...api.state.testResponse,
      ok: true,
      summary: "这台备份机上已有另一套备份历史。",
      remote_history_state: "foreign",
      remote_history_summary: "这台备份机上已有另一套备份历史。为避免数据混乱，不能直接继续写入。",
      remote_repo_id: "remote-repo-1",
      local_repo_id: "local-repo-2",
    };
    window.confirm = vi.fn(() => true) as any;
    const user = userEvent.setup();
    renderPage();

    await fillBackupMachineAddress(user);
    await user.click(screen.getByRole("button", { name: "检测" }));
    await screen.findByRole("button", { name: "覆盖远端历史" });
    expect(screen.getByText("无效")).not.toBeNull();
    expectButtonDisabled("设置恢复密码", true);

    await user.click(screen.getByRole("button", { name: "覆盖远端历史" }));

    expect(window.confirm).toHaveBeenCalled();
    await waitFor(() => expectButtonDisabled("设置恢复密码", false));
  });

  it("runs a full backup machine test after bootstrap succeeds", async () => {
    const user = userEvent.setup();
    const rawSshError = "ssh: connect to host backup.example.com port 22: Connection timed out";
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
    expect(screen.getByText("请生成临时命令，并在备份机终端上执行")).not.toBeNull();
    await user.click(screen.getByRole("button", { name: "生成临时命令" }));
    api.state.testResponse = {
      ...api.state.testResponse,
      ok: true,
      summary: "SFTP 连接正常，远端目录可写。",
      remote_history_state: "empty",
      remote_history_summary: "备份机可连接，未发现历史备份。",
    };
    api.state.bootstrapClaim = {
      ...api.state.bootstrapClaim,
      status: "succeeded",
      completed_at: "2026-07-02T00:04:00+08:00",
    };

    await act(async () => {
      await new Promise((resolve) => window.setTimeout(resolve, 3200));
    });

    expect(api.testConfig).toHaveBeenCalledWith(
      expect.objectContaining({
        remote_host: "backup.example.com",
        remote_path: "/srv/serino-backups",
      }),
    );
    expectButtonDisabled("设置恢复密码", false);
  }, 8000);

  it("blocks backup start when the required recovery password is not set", async () => {
    const user = userEvent.setup();
    renderPage();

    await fillBackupMachineAddress(user);

    await user.click(screen.getByRole("button", { name: "启动备份" }));

    await waitFor(() => {
      expect(api.toastError).toHaveBeenCalledWith(
        "第一次建立备份前，必须先设置恢复密码。完成这一步之后才能保存备份配置。",
      );
    });
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(api.exportRecoveryKey).not.toHaveBeenCalled();
    expect(api.updateMutateAsync).not.toHaveBeenCalled();
    expect(api.triggerMutateAsync).not.toHaveBeenCalled();
  });

  it("blocks saving when the required recovery password is not set", async () => {
    const user = userEvent.setup();
    renderPage();

    await fillBackupMachineAddress(user);
    await user.click(screen.getByRole("button", { name: "测试并保存" }));

    await waitFor(() => {
      expect(api.toastError).toHaveBeenCalledWith(
        "第一次建立备份前，必须先设置恢复密码。完成这一步之后才能保存备份配置。",
      );
    });
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(api.exportRecoveryKey).not.toHaveBeenCalled();
    expect(api.updateMutateAsync).not.toHaveBeenCalled();
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

  it("copies the temporary command when the Clipboard API is blocked", async () => {
    const user = userEvent.setup();
    vi.spyOn(navigator.clipboard, "writeText").mockRejectedValue(new Error("Clipboard blocked"));
    const execCommand = vi.spyOn(document, "execCommand").mockReturnValue(true);
    api.state.testResponse = {
      ...api.state.testResponse,
      ok: false,
      summary: "ssh refused",
      remote_history_state: "unreachable",
      remote_history_summary: "ssh refused",
    };
    renderPage();

    await fillBackupMachineAddress(user);
    await user.click(screen.getByRole("button", { name: "检测" }));
    await user.click(await screen.findByRole("button", { name: "生成临时命令" }));
    await screen.findByText("curl -fsSL http://testserver/api/v1/backup/setup/claim-token.sh | sudo bash");
    await user.click(screen.getByRole("button", { name: "复制命令" }));

    expect(execCommand).toHaveBeenCalledWith("copy");
    expect(api.toastSuccess).toHaveBeenCalledWith("命令已复制");
  });

  it("restores a foreign remote history after recovery password verification", async () => {
    api.state.testResponse = {
      ...api.state.testResponse,
      ok: true,
      summary: "这台备份机上已有另一套备份历史。",
      remote_history_state: "foreign",
      remote_history_summary: "这台备份机上已有另一套备份历史。为避免数据混乱，不能直接继续写入。",
      remote_repo_id: "remote-repo-1",
      local_repo_id: "local-repo-2",
    };
    const user = userEvent.setup();
    renderPage();

    await fillBackupMachineAddress(user);
    await user.click(screen.getByRole("button", { name: "检测" }));
    expect(
      await screen.findAllByText("这台备份机上已有另一套备份历史。为避免数据混乱，不能直接继续写入。"),
    ).toHaveLength(2);
    await user.click(screen.getByRole("button", { name: "从备份机历史恢复数据" }));

    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByPlaceholderText("********"), "super-safe-passphrase");
    await user.click(within(dialog).getByRole("button", { name: "验证恢复密码" }));
    await within(dialog).findByText(/commit-r/);
    await user.click(within(dialog).getByRole("button", { name: "恢复所选版本" }));

    await waitFor(() => {
      expect(api.previewRemoteHistoryImport).toHaveBeenCalledWith(
        expect.objectContaining({
          passphrase: "super-safe-passphrase",
          config: expect.objectContaining({ remote_host: "backup.example.com" }),
        }),
      );
      expect(api.restoreRemoteHistoryImport).toHaveBeenCalledWith(
        expect.objectContaining({
          passphrase: "super-safe-passphrase",
          commit_id: "commit-remote-1",
        }),
      );
    });
    expect(api.toastSuccess).toHaveBeenCalledWith("已从远端备份历史恢复");
  });

  it("shows a recover-specific error when remote history has no keyring", async () => {
    api.state.testResponse = {
      ...api.state.testResponse,
      ok: true,
      summary: "这台备份机上已有另一套备份历史。",
      remote_history_state: "foreign",
      remote_history_summary: "这台备份机上已有另一套备份历史。为避免数据混乱，不能直接继续写入。",
      remote_repo_id: "remote-repo-1",
      local_repo_id: "local-repo-2",
    };
    api.state.remotePreviewError = {
      response: {
        data: {
          detail:
            "远端备份历史缺少恢复钥匙包，当前机器也没有这批备份的恢复钥匙记录，不能仅凭密码恢复。",
        },
      },
    };
    const user = userEvent.setup();
    renderPage();

    await fillBackupMachineAddress(user);
    await user.click(screen.getByRole("button", { name: "检测" }));
    await user.click(await screen.findByRole("button", { name: "从备份机历史恢复数据" }));

    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByPlaceholderText("********"), "super-safe-passphrase");
    await user.click(within(dialog).getByRole("button", { name: "验证恢复密码" }));

    await waitFor(() => {
      expect(api.toastError).toHaveBeenCalledWith(
        "远端备份历史缺少恢复钥匙包，当前机器也没有这批备份的恢复钥匙记录，不能仅凭密码恢复。",
      );
    });
    expect(within(dialog).queryByText("选择备份版本")).toBeNull();
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
    expect(screen.getByText("存档点")).not.toBeNull();
    expect(screen.queryByText("远端提交 ID")).toBeNull();
    expect(screen.queryByText("remote-commit-1")).toBeNull();

    vi.mocked(window.confirm).mockReturnValueOnce(false);
    await user.click(screen.getByRole("button", { name: "恢复" }));
    expect(api.restoreMutate).not.toHaveBeenCalled();

    vi.mocked(window.confirm).mockReturnValueOnce(true);
    await user.click(screen.getByRole("button", { name: "恢复" }));
    expect(api.restoreMutate).toHaveBeenCalledWith({ commitId: "commit-1" });
  });

  it("shows archive points without an actions column", async () => {
    api.state.runs = [
      {
        id: "run-failed-1",
        job_name: "backup_sync",
        status: "failed",
        transport: "sftp",
        trigger_kind: "manual",
        queue_item_id: "queue-1",
        commit_id: null,
        stats_json: {},
        retry_count: 1,
        next_retry_at: null,
        last_error: "network error",
        started_at: "2026-07-02T00:00:00+08:00",
        finished_at: "2026-07-02T00:01:00+08:00",
        message: "failed",
        created_at: "2026-07-02T00:00:00+08:00",
        updated_at: "2026-07-02T00:01:00+08:00",
      },
    ];
    const user = userEvent.setup();
    renderPage();

    await user.click(buttonContainingText("记录"));
    await user.click(screen.getByRole("button", { name: "存档点" }));

    expect(screen.getAllByText("存档点").length).toBeGreaterThan(0);
    expect(screen.queryByText("运行记录")).toBeNull();
    expect(screen.getByText("network error")).not.toBeNull();
    expect(screen.queryByText("操作")).toBeNull();
    expect(screen.queryByRole("button", { name: "重试" })).toBeNull();
  });

  it("hides the internal runtime restore interruption message", async () => {
    api.state.runs = [
      {
        id: "run-restored-1",
        job_name: "backup_sync",
        status: "failed",
        transport: "sftp",
        trigger_kind: "manual",
        queue_item_id: "queue-1",
        commit_id: null,
        stats_json: {},
        retry_count: 0,
        next_retry_at: null,
        last_error: "Backup run was interrupted by a runtime restore",
        started_at: "2026-07-02T00:00:00+08:00",
        finished_at: "2026-07-02T00:01:00+08:00",
        message: "Backup run was interrupted by a runtime restore",
        created_at: "2026-07-02T00:00:00+08:00",
        updated_at: "2026-07-02T00:01:00+08:00",
      },
    ];
    const user = userEvent.setup();
    renderPage();

    await user.click(buttonContainingText("记录"));
    await user.click(screen.getByRole("button", { name: "存档点" }));
    await user.click(screen.getByRole("button", { name: "展开" }));

    expect(screen.queryByText("Backup run was interrupted by a runtime restore")).toBeNull();
  });
});
