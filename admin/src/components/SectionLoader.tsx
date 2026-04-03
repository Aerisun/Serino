interface SectionLoaderProps {
  label?: string;
}

export function SectionLoader({ label = "Loading..." }: SectionLoaderProps) {
  return (
    <div className="flex min-h-[12rem] items-center justify-center text-sm text-muted-foreground">
      <div className="flex items-center gap-3">
        <div className="h-5 w-5 animate-spin rounded-full border-2 border-current border-t-transparent" />
        <span>{label}</span>
      </div>
    </div>
  );
}
