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

const COPY = {
  zh: {
    eyebrow: "Storage",
    title: "OSS 加速",
    description: "保持媒体链接不变，启用后优先用缤纷云加速分发，并异步镜像回本地。",
    enabled: "启用 OSS 加速",
    enabledHint: "开启后，上传优先走 OSS，下载优先由媒体网关临时分发到 OSS/CDN。",
    provider: "服务商",
    bucket: "Bucket",
    endpoint: "Endpoint",
    region: "Region",
    publicBaseUrl: "媒体域名 / CDN 域名",
    accessKey: "Access Key",
    secretKey: "Secret Key",
    secretConfigured: "已配置，留空则保持不变",
    cdnTokenKey: "CDN 防盗链密钥",
    cdnTokenConfigured: "已配置，留空则保持不变",
    healthCheckEnabled: "启用健康检查",
    healthCheckHint: "开启后，媒体网关分发前会优先确认 OSS 当前可用。",
    advanced: "高级配置",
    uploadExpire: "上传签名时效（秒）",
    downloadExpire: "下载签名时效（秒）",
    mirrorBandwidth: "回源带宽限制（字节/秒）",
    mirrorRetry: "回源重试次数",
    test: "连通性测试",
    testing: "测试中...",
    saveSuccess: "OSS 配置已保存",
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
    description: "Keep media links stable while preferring Bitiful for delivery and asynchronously mirroring objects back locally.",
    enabled: "Enable OSS acceleration",
    enabledHint: "When enabled, uploads prefer OSS first and downloads are redirected by the media gateway.",
    provider: "Provider",
    bucket: "Bucket",
    endpoint: "Endpoint",
    region: "Region",
    publicBaseUrl: "Media / CDN Domain",
    accessKey: "Access Key",
    secretKey: "Secret Key",
    secretConfigured: "Already configured. Leave blank to keep the current secret.",
    cdnTokenKey: "CDN Token Key",
    cdnTokenConfigured: "Already configured. Leave blank to keep the current key.",
    healthCheckEnabled: "Enable health checks",
    healthCheckHint: "When enabled, the media gateway verifies OSS availability before redirecting traffic.",
    advanced: "Advanced settings",
    uploadExpire: "Upload signature TTL (seconds)",
    downloadExpire: "Download signature TTL (seconds)",
    mirrorBandwidth: "Mirror bandwidth cap (bytes/sec)",
    mirrorRetry: "Mirror retry count",
    test: "Connectivity test",
    testing: "Testing...",
    saveSuccess: "OSS configuration saved",
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
    secret_key: "",
    cdn_token_key: "",
    health_check_enabled: config.health_check_enabled,
    upload_expire_seconds: String(config.upload_expire_seconds),
    public_download_expire_seconds: String(config.public_download_expire_seconds),
    mirror_bandwidth_limit_bps: String(config.mirror_bandwidth_limit_bps),
    mirror_retry_count: String(config.mirror_retry_count),
  };
}

function buildPayload(form: FormState): ObjectStorageConfigUpdate {
  return {
    enabled: form.enabled,
    provider: form.provider,
    bucket: form.bucket.trim(),
    endpoint: form.endpoint.trim(),
    region: form.region.trim(),
    public_base_url: form.public_base_url.trim(),
    access_key: form.access_key.trim(),
    secret_key: form.secret_key.trim() || undefined,
    cdn_token_key: form.cdn_token_key.trim() || undefined,
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
            summary: data.last_health_error || (data.last_health_ok ? copy.statusAvailable : copy.statusInvalid),
            details: {},
          },
    );
  }, [copy.statusAvailable, copy.statusInvalid, data]);

  const save = useMutation({
    mutationFn: (payload: ObjectStorageConfigUpdate) => updateObjectStorageConfig(payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: QUERY_KEY });
      toast.success(copy.saveSuccess);
      setForm((current) => ({ ...current, secret_key: "", cdn_token_key: "" }));
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const test = useMutation({
    mutationFn: (payload: ObjectStorageConfigUpdate) => testObjectStorageConfig(payload),
    onSuccess: (result) => {
      setHealth(result);
      toast[result.ok ? "success" : "error"](result.ok ? copy.testSuccess : copy.testFailed);
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const savedForm = useMemo(() => (data ? toForm(data) : EMPTY_FORM), [data]);
  const dirty = useMemo(() => JSON.stringify(form) !== JSON.stringify(savedForm), [form, savedForm]);
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
  }, [copy.statusAvailable, copy.statusDisabled, copy.statusInvalid, copy.statusPending, copy.testing, form.enabled, health, test.isPending]);

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
          {test.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Database className="mr-2 h-4 w-4" />}
          {copy.test}
        </Button>
      }
    >
      <div className="space-y-4">
        <AppleSwitch
          checked={form.enabled}
          onCheckedChange={(checked) => setForm((current) => ({ ...current, enabled: checked }))}
          label={
            <LabelWithHelp
              label={copy.enabled}
              title={copy.enabled}
              description={copy.enabledHint}
              className="gap-1.5"
            />
          }
          switchLeading={<span className="text-sm font-medium text-muted-foreground">{form.enabled ? copy.statusEnabled : copy.statusDisabled}</span>}
        />

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={copy.provider} value={form.provider} disabled />
          <Field label={copy.bucket} value={form.bucket} onChange={(value) => setForm((current) => ({ ...current, bucket: value }))} />
          <Field label={copy.endpoint} value={form.endpoint} onChange={(value) => setForm((current) => ({ ...current, endpoint: value }))} />
          <Field label={copy.region} value={form.region} onChange={(value) => setForm((current) => ({ ...current, region: value }))} />
          <Field label={copy.publicBaseUrl} value={form.public_base_url} onChange={(value) => setForm((current) => ({ ...current, public_base_url: value }))} />
          <Field label={copy.accessKey} value={form.access_key} onChange={(value) => setForm((current) => ({ ...current, access_key: value }))} />
          <Field
            label={copy.secretKey}
            value={form.secret_key}
            placeholder={data.secret_key_configured ? copy.secretConfigured : ""}
            type="password"
            onChange={(value) => setForm((current) => ({ ...current, secret_key: value }))}
          />
        </div>

        <AppleSwitch
          checked={form.health_check_enabled}
          onCheckedChange={(checked) => setForm((current) => ({ ...current, health_check_enabled: checked }))}
          label={
            <LabelWithHelp
              label={copy.healthCheckEnabled}
              title={copy.healthCheckEnabled}
              description={copy.healthCheckHint}
              className="gap-1.5"
            />
          }
        />

        <CollapsibleSection title={copy.advanced}>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field
              label={copy.cdnTokenKey}
              value={form.cdn_token_key}
              placeholder={data.cdn_token_key_configured ? copy.cdnTokenConfigured : ""}
              type="password"
              onChange={(value) => setForm((current) => ({ ...current, cdn_token_key: value }))}
            />
            <Field
              label={copy.uploadExpire}
              value={form.upload_expire_seconds}
              onChange={(value) => setForm((current) => ({ ...current, upload_expire_seconds: value }))}
            />
            <Field
              label={copy.downloadExpire}
              value={form.public_download_expire_seconds}
              onChange={(value) => setForm((current) => ({ ...current, public_download_expire_seconds: value }))}
            />
            <Field
              label={copy.mirrorBandwidth}
              value={form.mirror_bandwidth_limit_bps}
              onChange={(value) => setForm((current) => ({ ...current, mirror_bandwidth_limit_bps: value }))}
            />
            <Field
              label={copy.mirrorRetry}
              value={form.mirror_retry_count}
              onChange={(value) => setForm((current) => ({ ...current, mirror_retry_count: value }))}
            />
          </div>
        </CollapsibleSection>

        {health ? <p className="text-sm text-muted-foreground">{health.summary}</p> : null}
      </div>
    </ConfigSettingsCard>
  );
}

function Field({
  label,
  value,
  onChange,
  disabled = false,
  placeholder,
  type = "text",
}: {
  label: string;
  value: string;
  onChange?: (value: string) => void;
  disabled?: boolean;
  placeholder?: string;
  type?: string;
}) {
  return (
    <label className="grid gap-2">
      <span className="text-sm font-medium text-foreground/90">{label}</span>
      <Input
        value={value}
        onChange={(event) => onChange?.(event.target.value)}
        disabled={disabled}
        placeholder={placeholder}
        type={type}
      />
    </label>
  );
}
