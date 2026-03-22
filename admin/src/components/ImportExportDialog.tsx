import { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import { useI18n } from "@/i18n";
import client from "@/api/client";

interface ImportExportDialogProps {
  open: boolean;
  onClose: () => void;
  contentType: string;
}

export function ImportExportDialog({ open, onClose, contentType }: ImportExportDialogProps) {
  const { t } = useI18n();
  const [importing, setImporting] = useState(false);

  const handleExport = async (format: "json" | "markdown_zip") => {
    try {
      const res = await client.get(`/content/export`, {
        params: { content_type: contentType, format },
        responseType: "blob",
      });
      const ext = format === "json" ? "json" : "zip";
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${contentType}-export.${ext}`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success(t("common.operationSuccess"));
    } catch {
      toast.error(t("common.operationFailed"));
    }
  };

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await client.post(`/content/import?content_type=${contentType}`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      const { created, updated, errors } = res.data;
      toast.success(`${t("importExport.imported")}: ${created} ${t("importExport.created")}, ${updated} ${t("importExport.updated")}${errors.length ? `, ${errors.length} ${t("importExport.errors")}` : ""}`);
      onClose();
    } catch {
      toast.error(t("common.operationFailed"));
    } finally {
      setImporting(false);
    }
  };

  return (
    <Dialog.Root open={open} onOpenChange={(v) => !v && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/40 z-50" />
        <Dialog.Content className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-50 w-full max-w-md rounded-lg border bg-card p-6 shadow-lg">
          <Dialog.Title className="text-lg font-semibold mb-4">{t("importExport.title")}</Dialog.Title>

          <div className="space-y-4">
            <div>
              <h4 className="text-sm font-medium mb-2">{t("importExport.export")}</h4>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={() => handleExport("json")}>
                  JSON
                </Button>
                <Button variant="outline" size="sm" onClick={() => handleExport("markdown_zip")}>
                  Markdown ZIP
                </Button>
              </div>
            </div>

            <div className="border-t pt-4">
              <h4 className="text-sm font-medium mb-2">{t("importExport.import")}</h4>
              <label className="block">
                <input
                  type="file"
                  accept=".json"
                  onChange={handleImport}
                  disabled={importing}
                  className="block w-full text-sm text-muted-foreground file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-medium file:bg-primary file:text-primary-foreground hover:file:bg-primary/90"
                />
              </label>
              {importing && <p className="text-sm text-muted-foreground mt-2">{t("common.loading")}</p>}
            </div>
          </div>

          <div className="mt-6 flex justify-end">
            <Button variant="outline" onClick={onClose}>{t("common.cancel")}</Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
