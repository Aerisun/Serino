import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  getListContentCategoriesQueryKey,
  useCreateContentCategory,
  useListContentCategories,
} from "@serino/api-client/admin";
import type { ContentCategoryCreate } from "@serino/api-client/models";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import { useI18n } from "@/i18n";
import { CONTENT_CATEGORY_LABEL_KEYS, type ContentCategoryType } from "@/lib/contentCategories";
import { toast } from "sonner";

const EMPTY_VALUE = "__none__";
const CREATE_VALUE = "__create__";

interface ContentCategoryFieldProps {
  contentType: ContentCategoryType;
  label: string;
  value: string;
  placeholder?: string;
  onChange: (value: string) => void;
}

export function ContentCategoryField({
  contentType,
  label,
  value,
  placeholder,
  onChange,
}: ContentCategoryFieldProps) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [newCategoryName, setNewCategoryName] = useState("");

  const { data, isLoading } = useListContentCategories(
    { content_type: contentType },
    { query: { staleTime: 60_000 } },
  );
  const effectiveOptions = useMemo(() => {
    const options = data?.data ?? [];
    if (!value || options.some((item) => item.name === value)) {
      return options;
    }
    return [
      {
        id: "__legacy__",
        content_type: contentType,
        name: value,
        usage_count: 0,
      },
      ...options,
    ];
  }, [contentType, data?.data, value]);

  const normalizedValue = useMemo(() => {
    if (!value) {
      return EMPTY_VALUE;
    }
    return value;
  }, [value]);

  const createCategory = useCreateContentCategory({
    mutation: {
      onSuccess: async (response) => {
        await queryClient.invalidateQueries({
          queryKey: getListContentCategoriesQueryKey({ content_type: contentType }),
        });
        await queryClient.invalidateQueries({
          queryKey: getListContentCategoriesQueryKey(),
        });
        onChange(response.data.name);
        setNewCategoryName("");
        setCreateOpen(false);
        toast.success(t("contentCategories.createSuccess"));
      },
      onError: (error: any) => {
        const message = error?.response?.data?.detail || t("common.operationFailed");
        toast.error(message);
      },
    },
  });

  const handleSelectChange = (nextValue: string) => {
    if (nextValue === CREATE_VALUE) {
      setCreateOpen(true);
      return;
    }

    onChange(nextValue === EMPTY_VALUE ? "" : nextValue);
  };

  const handleCreate = async () => {
    const name = newCategoryName.trim();
    if (!name) {
      toast.error(t("contentCategories.nameRequired"));
      return;
    }

    await createCategory.mutateAsync({
      data: {
        content_type: contentType as ContentCategoryCreate["content_type"],
        name,
      },
    });
  };

  return (
    <div className="space-y-2">
      <Label>{label}</Label>
      <Select
        value={normalizedValue}
        onValueChange={handleSelectChange}
      >
        <SelectTrigger className="h-11 rounded-xl border-border/50 bg-background/70">
          <SelectValue
            placeholder={
              isLoading ? t("common.loading") : placeholder || t("contentCategories.selectPlaceholder")
            }
          />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={EMPTY_VALUE}>{t("contentCategories.none")}</SelectItem>
          {effectiveOptions.map((option) => (
            <SelectItem key={option.id} value={option.name}>
              {option.name}
            </SelectItem>
          ))}
          <SelectItem value={CREATE_VALUE}>{t("contentCategories.createOption")}</SelectItem>
        </SelectContent>
      </Select>

      <Dialog
        open={createOpen}
        onOpenChange={(open) => {
          setCreateOpen(open);
          if (!open) {
            setNewCategoryName("");
          }
        }}
      >
        <DialogContent className="max-w-md rounded-2xl">
          <DialogHeader className="text-left">
            <DialogTitle>{t("contentCategories.createTitle")}</DialogTitle>
            <DialogDescription>
              {t(CONTENT_CATEGORY_LABEL_KEYS[contentType])}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>{t("contentCategories.nameLabel")}</Label>
              <Input
                value={newCategoryName}
                onChange={(event) => setNewCategoryName(event.target.value)}
                placeholder={t("contentCategories.namePlaceholder")}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    void handleCreate();
                  }
                }}
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button
                variant="ghost"
                type="button"
                onClick={() => setCreateOpen(false)}
              >
                {t("common.cancel")}
              </Button>
              <Button
                type="button"
                onClick={() => void handleCreate()}
                disabled={createCategory.isPending}
              >
                {createCategory.isPending ? t("common.saving") : t("contentCategories.createAction")}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
