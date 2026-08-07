import { useEffect, useState } from "react";
import { FileQuestion, LoaderCircle } from "lucide-react";
import { useParams } from "react-router-dom";
import { createAssetOpenUrlEndpointApiV1AdminAssetsAssetIdOpenUrlPost } from "@serino/api-client/admin";
import { useI18n } from "@/i18n";
import { replaceBrowserLocation } from "@/lib/browserNavigation";

export default function AssetPreviewPage() {
  const { assetId = "" } = useParams();
  const { t } = useI18n();
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void createAssetOpenUrlEndpointApiV1AdminAssetsAssetIdOpenUrlPost(assetId)
      .then((response) => {
        if (cancelled) return;
        if (!("url" in response.data)) throw new Error("Asset open URL response is invalid");
        replaceBrowserLocation(response.data.url);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [assetId]);

  return (
    <main className="flex h-dvh min-h-screen items-center justify-center bg-background px-6 text-center text-muted-foreground">
      {failed ? (
        <div className="flex flex-col items-center gap-3">
          <FileQuestion className="h-9 w-9" />
          <p>{t("common.operationFailed")}</p>
        </div>
      ) : (
        <LoaderCircle className="h-7 w-7 animate-spin" aria-label={t("common.loading")} />
      )}
    </main>
  );
}
