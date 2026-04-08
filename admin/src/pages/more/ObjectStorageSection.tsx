import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Database, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { ConfigSettingsCard } from "@/components/ConfigSettingsCard";
import { AppleSwitch } from "@/components/ui/AppleSwitch";
import { Button } from "@/components/ui/Button";
import { CollapsibleSection } from "@/components/ui/CollapsibleSection";
import { Input } from "@/components/ui/Input";
import { LabelWithHelp } from "@/components/ui/LabelWithHelp";
import { useI18n } from "@/i18n";
import {
  getObjectStorageConfig,
  testObjectStorageConfig,
  type ObjectStorageConfigRead,
  type ObjectStorageConfigUpdate,
  type ObjectStorageHealthRead,
  updateObjectStorageConfig,
} from "./objectStorageApi";

const QUERY_KEY = ["admin", "object-storage-config"] as const;
const DEFAULT_ENDPOINT = "https://s3.bitiful.net";
const DEFAULT_REGION = "cn-east-1";
const MASKED_SECRET = "********";

const COPY = {
  zh: {
    eyebrow: "Storage",
    title: "OSS 加速",
    description: "😴🤔 目前只是先支持了滨纷云",
    enabled: "启用 OSS 加速",
    enabledHint:
      "开启后，收获存粹的速度提升，资源文件上传/下载优先使用 OSS，但是服务器本地仍然会存有这些文件，您放心！",
    bucket: "Bucket",
    bucketHelp: "缤纷云中实际存放资源的桶名称。",
    endpoint: "Endpoint",
    endpointHelp: "缤纷云 S3 兼容访问地址，用于上传、签名和回源。",
    endpointPlaceholder: DEFAULT_ENDPOINT,
    region: "Region",
    regionHelp: "对象存储使用的区域标识，通常按服务商提供的值填写。",
    regionPlaceholder: DEFAULT_REGION,
    publicBaseUrl: "媒体域名 / CDN 域名",
    publicBaseUrlHelp: "给用户访问资源时使用的媒体域名或 CDN 域名。",
    accessKey: "Access Key",
    accessKeyHelp: "用于访问当前 Bucket 的 Access Key。",
    secretKey: "Secret Key",
    secretKeyHelp: "与 Access Key 配套的密钥，仅服务端保存和使用。",
    secretConfigured: "********",
    cdnTokenKey: "CDN 防盗链密钥",
    cdnTokenKeyHelp:
      "给媒体域名生成短时效防盗链链接时使用，不填则回退到普通预签名下载。",
    cdnTokenConfigured: "********",
    healthCheckEnabled: "启用健康检查",
    healthCheckHint: "开启后，媒体网关分发前会优先确认 OSS 当前可用。",
    advanced: "高级配置",
    uploadExpire: "上传签名时效（秒）",
    uploadExpireHelp: "浏览器直传 OSS 的上传地址有效期，默认 300 秒。",
    downloadExpire: "下载签名时效（秒）",
    downloadExpireHelp: "用户访问资源时拿到的临时下载地址有效期，默认 600 秒。",
    mirrorBandwidth: "回源带宽限制（字节/秒）",
    mirrorBandwidthHelp:
      "OSS 异步同步回本地时的单任务带宽上限，避免占满服务器带宽。",
    mirrorRetry: "回源重试次数",
    mirrorRetryHelp: "回源失败后的自动重试次数，超过后任务会停在失败状态。",
    test: "连通性测试",
    testing: "测试中...",
    saveSuccess: "OSS 配置已保存",
    saveSuccessDisabled: "OSS 配置已保存，当前未启用加速",
    saveSyncChecked: "已开始检查本地资源同步状态",
    saveSyncQueued: "已开始补同步本地资源到 OSS",
    testSuccess: "OSS 配置测试通过",
    testFailed: "OSS 配置测试失败",
    statusEnabled: "已开启",
    statusDisabled: "已关闭",
    statusAvailable: "可用",
    statusInvalid: "异常",
    statusPending: "待测试",
  },
  en: {
    eyebrow: "Storage",
    title: "OSS Acceleration",
    description:
      "Fill only the required fields to enable it. Media usage stays the same for admins and end users.",
    enabled: "Enable OSS acceleration",
    enabledHint:
      "When enabled, uploads go to OSS first and downloads are redirected by the media gateway.",
    bucket: "Bucket",
    bucketHelp: "The Bitiful bucket that stores your managed media objects.",
    endpoint: "Endpoint",
    endpointHelp:
      "The S3-compatible Bitiful endpoint used for upload, signing, and mirroring.",
    endpointPlaceholder: DEFAULT_ENDPOINT,
    region: "Region",
    regionHelp:
      "The storage region identifier, usually the value provided by the vendor.",
    regionPlaceholder: DEFAULT_REGION,
    publicBaseUrl: "Media / CDN Domain",
    publicBaseUrlHelp:
      "The media or CDN domain end users will hit for asset delivery.",
    accessKey: "Access Key",
    accessKeyHelp:
      "The access key allowed to operate on the configured bucket.",
    secretKey: "Secret Key",
    secretKeyHelp:
      "The secret paired with the access key. It is stored server-side only.",
    secretConfigured: "********",
    cdnTokenKey: "CDN Token Key",
    cdnTokenKeyHelp:
      "Used to issue short-lived anti-leech CDN links. Falls back to standard presigned download if empty.",
    cdnTokenConfigured: "********",
    healthCheckEnabled: "Enable health checks",
    healthCheckHint:
      "When enabled, the media gateway verifies OSS availability before redirecting traffic.",
    advanced: "Advanced settings",
    uploadExpire: "Upload signature TTL (seconds)",
    uploadExpireHelp:
      "How long the browser upload URL stays valid for direct OSS upload. Default is 300 seconds.",
    downloadExpire: "Download signature TTL (seconds)",
    downloadExpireHelp:
      "How long the temporary download URL stays valid for end users. Default is 600 seconds.",
    mirrorBandwidth: "Mirror bandwidth cap (bytes/sec)",
    mirrorBandwidthHelp:
      "Per-task bandwidth cap when mirroring files back from OSS to the local server.",
    mirrorRetry: "Mirror retry count",
    mirrorRetryHelp:
      "How many times failed mirror jobs are retried before staying failed.",
    test: "Connectivity test",
    testing: "Testing...",
    saveSuccess: "OSS configuration saved",
    saveSuccessDisabled:
      "OSS configuration saved, acceleration is still disabled",
    saveSyncChecked: "Started checking local asset sync state",
    saveSyncQueued: "Started syncing local-only assets to OSS",
    testSuccess: "OSS configuration test passed",
    testFailed: "OSS configuration test failed",
    statusEnabled: "Enabled",
    statusDisabled: "Disabled",
    statusAvailable: "Available",
    statusInvalid: "Invalid",
    statusPending: "Pending",
  },
} as const;

type FormState = {
  enabled: boolean;
  provider: "bitiful";
  bucket: string;
  endpoint: string;
  region: string;
  public_base_url: string;
  access_key: string;
  secret_key: string;
  cdn_token_key: string;
  health_check_enabled: boolean;
  upload_expire_seconds: string;
  public_download_expire_seconds: string;
  mirror_bandwidth_limit_bps: string;
  mirror_retry_count: string;
};

const EMPTY_FORM: FormState = {
  enabled: false,
  provider: "bitiful",
  bucket: "",
  endpoint: "",
  region: "",
  public_base_url: "",
  access_key: "",
  secret_key: "",
  cdn_token_key: "",
  health_check_enabled: true,
  upload_expire_seconds: "300",
  public_download_expire_seconds: "600",
  mirror_bandwidth_limit_bps: String(2 * 1024 * 1024),
  mirror_retry_count: "3",
};

function toForm(config: ObjectStorageConfigRead): FormState {
  return {
    enabled: config.enabled,
    provider: config.provider,
    bucket: config.bucket,
    endpoint: config.endpoint,
    region: config.region,
    public_base_url: config.public_base_url,
    access_key: config.access_key,
    secret_key: config.secret_key_configured ? MASKED_SECRET : "",
    cdn_token_key: config.cdn_token_key_configured ? MASKED_SECRET : "",
    health_check_enabled: config.health_check_enabled,
    upload_expire_seconds: String(config.upload_expire_seconds),
    public_download_expire_seconds: String(
      config.public_download_expire_seconds,
    ),
    mirror_bandwidth_limit_bps: String(config.mirror_bandwidth_limit_bps),
    mirror_retry_count: String(config.mirror_retry_count),
  };
}

function buildPayload(form: FormState): ObjectStorageConfigUpdate {
  return {
    enabled: form.enabled,
    provider: form.provider,
    bucket: form.bucket.trim(),
    endpoint: form.endpoint.trim() || DEFAULT_ENDPOINT,
    region: form.region.trim() || DEFAULT_REGION,
    public_base_url: form.public_base_url.trim(),
    access_key: form.access_key.trim(),
    secret_key:
      form.secret_key.trim() && form.secret_key.trim() !== MASKED_SECRET
        ? form.secret_key.trim()
        : undefined,
    cdn_token_key:
      form.cdn_token_key.trim() && form.cdn_token_key.trim() !== MASKED_SECRET
        ? form.cdn_token_key.trim()
        : undefined,
    health_check_enabled: form.health_check_enabled,
    upload_expire_seconds: Number(form.upload_expire_seconds),
    public_download_expire_seconds: Number(form.public_download_expire_seconds),
    mirror_bandwidth_limit_bps: Number(form.mirror_bandwidth_limit_bps),
    mirror_retry_count: Number(form.mirror_retry_count),
  };
}

export function ObjectStorageSection() {
  const { lang } = useI18n();
  const copy = COPY[lang];
  const queryClient = useQueryClient();
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [health, setHealth] = useState<ObjectStorageHealthRead | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: QUERY_KEY,
    queryFn: getObjectStorageConfig,
    refetchOnWindowFocus: false,
  });

  useEffect(() => {
    if (!data) {
      return;
    }
    setForm(toForm(data));
    setHealth(
      data.last_health_ok == null
        ? null
        : {
            ok: data.last_health_ok,
            summary:
              data.last_health_error ||
              (data.last_health_ok ? copy.statusAvailable : copy.statusInvalid),
            details: {},
          },
    );
  }, [copy.statusAvailable, copy.statusInvalid, data]);

  const save = useMutation({
    mutationFn: (payload: ObjectStorageConfigUpdate) =>
      updateObjectStorageConfig(payload),
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: QUERY_KEY });
      toast[result.enabled ? "success" : "info"](
        result.enabled ? copy.saveSuccess : copy.saveSuccessDisabled,
      );
      if (result.enabled && result.last_health_ok) {
        if ((result.remote_sync_enqueued_count ?? 0) > 0) {
          toast.info(
            `${copy.saveSyncQueued}（${result.remote_sync_enqueued_count}）`,
          );
        } else {
          toast.info(copy.saveSyncChecked);
        }
      }
      setForm((current) => ({
        ...current,
        secret_key: result.secret_key_configured ? MASKED_SECRET : "",
        cdn_token_key: result.cdn_token_key_configured ? MASKED_SECRET : "",
      }));
      setHealth(
        result.last_health_ok == null
          ? null
          : {
              ok: result.last_health_ok,
              summary:
                result.last_health_error ||
                (result.last_health_ok
                  ? copy.statusAvailable
                  : copy.statusInvalid),
              details: {},
            },
      );
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const test = useMutation({
    mutationFn: (payload: ObjectStorageConfigUpdate) =>
      testObjectStorageConfig(payload),
    onSuccess: (result) => {
      setHealth(result);
      toast[result.ok ? "success" : "error"](
        result.ok ? copy.testSuccess : copy.testFailed,
      );
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const savedForm = useMemo(() => (data ? toForm(data) : EMPTY_FORM), [data]);
  const dirty = useMemo(
    () => JSON.stringify(form) !== JSON.stringify(savedForm),
    [form, savedForm],
  );
  const statusIndicator = useMemo(() => {
    if (test.isPending) {
      return { label: copy.testing, tone: "checking" as const };
    }
    if (!form.enabled) {
      return { label: copy.statusDisabled, tone: "pending" as const };
    }
    if (health?.ok) {
      return { label: copy.statusAvailable, tone: "available" as const };
    }
    if (health?.ok === false) {
      return { label: copy.statusInvalid, tone: "invalid" as const };
    }
    return { label: copy.statusPending, tone: "pending" as const };
  }, [
    copy.statusAvailable,
    copy.statusDisabled,
    copy.statusInvalid,
    copy.statusPending,
    copy.testing,
    form.enabled,
    health,
    test.isPending,
  ]);

  if (isLoading || !data) {
    return <p className="py-4 text-sm text-muted-foreground">{copy.testing}</p>;
  }

  return (
    <ConfigSettingsCard
      eyebrow={copy.eyebrow}
      title={copy.title}
      description={copy.description}
      dirty={dirty}
      saving={save.isPending}
      saveDisabled={save.isPending}
      onSave={() => void save.mutateAsync(buildPayload(form))}
      statusIndicator={statusIndicator}
      testAction={
        <Button
          type="button"
          variant="outline"
          onClick={() => void test.mutateAsync(buildPayload(form))}
          disabled={test.isPending}
        >
          {test.isPending ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Database className="mr-2 h-4 w-4" />
          )}
          {copy.test}
        </Button>
      }
    >
      <form
        className="space-y-4"
        onSubmit={(event) => {
          event.preventDefault();
          if (save.isPending) {
            return;
          }
          void save.mutateAsync(buildPayload(form));
        }}
      >
        <AppleSwitch
          checked={form.enabled}
          onCheckedChange={(checked) =>
            setForm((current) => ({ ...current, enabled: checked }))
          }
          label={
            <LabelWithHelp
              label={copy.enabled}
              title={copy.enabled}
              description={copy.enabledHint}
              className="gap-1.5"
            />
          }
          switchLeading={
            <span className="text-sm font-medium text-muted-foreground">
              {form.enabled ? copy.statusEnabled : copy.statusDisabled}
            </span>
          }
        />

        <div className="grid gap-4 sm:grid-cols-2">
          <Field
            label={copy.bucket}
            helpTitle={copy.bucket}
            helpDescription={copy.bucketHelp}
            value={form.bucket}
            onChange={(value) =>
              setForm((current) => ({ ...current, bucket: value }))
            }
          />
          <Field
            label={copy.endpoint}
            helpTitle={copy.endpoint}
            helpDescription={copy.endpointHelp}
            value={form.endpoint}
            placeholder={copy.endpointPlaceholder}
            onChange={(value) =>
              setForm((current) => ({ ...current, endpoint: value }))
            }
          />
          <Field
            label={copy.region}
            helpTitle={copy.region}
            helpDescription={copy.regionHelp}
            value={form.region}
            placeholder={copy.regionPlaceholder}
            onChange={(value) =>
              setForm((current) => ({ ...current, region: value }))
            }
          />
          <Field
            label={copy.publicBaseUrl}
            helpTitle={copy.publicBaseUrl}
            helpDescription={copy.publicBaseUrlHelp}
            value={form.public_base_url}
            onChange={(value) =>
              setForm((current) => ({ ...current, public_base_url: value }))
            }
          />
          <Field
            label={copy.accessKey}
            helpTitle={copy.accessKey}
            helpDescription={copy.accessKeyHelp}
            value={form.access_key}
            onChange={(value) =>
              setForm((current) => ({ ...current, access_key: value }))
            }
          />
          <Field
            label={copy.secretKey}
            helpTitle={copy.secretKey}
            helpDescription={copy.secretKeyHelp}
            value={form.secret_key}
            type={form.secret_key === MASKED_SECRET ? "text" : "password"}
            onFocus={() => {
              if (form.secret_key === MASKED_SECRET) {
                setForm((current) => ({ ...current, secret_key: "" }));
              }
            }}
            onChange={(value) =>
              setForm((current) => ({ ...current, secret_key: value }))
            }
          />
          <Field
            label={copy.cdnTokenKey}
            helpTitle={copy.cdnTokenKey}
            helpDescription={copy.cdnTokenKeyHelp}
            value={form.cdn_token_key}
            type={form.cdn_token_key === MASKED_SECRET ? "text" : "password"}
            onFocus={() => {
              if (form.cdn_token_key === MASKED_SECRET) {
                setForm((current) => ({ ...current, cdn_token_key: "" }));
              }
            }}
            onChange={(value) =>
              setForm((current) => ({ ...current, cdn_token_key: value }))
            }
          />
        </div>

        <CollapsibleSection title={copy.advanced} defaultOpen={false}>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field
              label={copy.uploadExpire}
              helpTitle={copy.uploadExpire}
              helpDescription={copy.uploadExpireHelp}
              value={form.upload_expire_seconds}
              onChange={(value) =>
                setForm((current) => ({
                  ...current,
                  upload_expire_seconds: value,
                }))
              }
            />
            <Field
              label={copy.downloadExpire}
              helpTitle={copy.downloadExpire}
              helpDescription={copy.downloadExpireHelp}
              value={form.public_download_expire_seconds}
              onChange={(value) =>
                setForm((current) => ({
                  ...current,
                  public_download_expire_seconds: value,
                }))
              }
            />
            <Field
              label={copy.mirrorBandwidth}
              helpTitle={copy.mirrorBandwidth}
              helpDescription={copy.mirrorBandwidthHelp}
              value={form.mirror_bandwidth_limit_bps}
              onChange={(value) =>
                setForm((current) => ({
                  ...current,
                  mirror_bandwidth_limit_bps: value,
                }))
              }
            />
            <Field
              label={copy.mirrorRetry}
              helpTitle={copy.mirrorRetry}
              helpDescription={copy.mirrorRetryHelp}
              value={form.mirror_retry_count}
              onChange={(value) =>
                setForm((current) => ({
                  ...current,
                  mirror_retry_count: value,
                }))
              }
            />
          </div>
          <div className="mt-4">
            <AppleSwitch
              checked={form.health_check_enabled}
              onCheckedChange={(checked) =>
                setForm((current) => ({
                  ...current,
                  health_check_enabled: checked,
                }))
              }
              label={
                <LabelWithHelp
                  label={copy.healthCheckEnabled}
                  title={copy.healthCheckEnabled}
                  description={copy.healthCheckHint}
                  className="gap-1.5"
                />
              }
            />
          </div>
        </CollapsibleSection>

        {health ? (
          <p className="text-sm text-muted-foreground">{health.summary}</p>
        ) : null}
      </form>
    </ConfigSettingsCard>
  );
}

function Field({
  label,
  helpTitle,
  helpDescription,
  value,
  onChange,
  onFocus,
  disabled = false,
  placeholder,
  type = "text",
}: {
  label: string;
  helpTitle?: string;
  helpDescription?: string;
  value: string;
  onChange?: (value: string) => void;
  onFocus?: () => void;
  disabled?: boolean;
  placeholder?: string;
  type?: string;
}) {
  return (
    <label className="grid gap-2">
      {helpTitle && helpDescription ? (
        <LabelWithHelp
          label={label}
          title={helpTitle}
          description={helpDescription}
          className="gap-1.5"
        />
      ) : (
        <span className="text-sm font-medium text-foreground/90">{label}</span>
      )}
      <Input
        value={value}
        onChange={(event) => onChange?.(event.target.value)}
        onFocus={() => onFocus?.()}
        disabled={disabled}
        placeholder={placeholder}
        type={type}
        autoComplete={type === "password" ? "new-password" : undefined}
      />
    </label>
  );
}
