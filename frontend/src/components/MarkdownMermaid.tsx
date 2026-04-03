import { LoaderCircle, Minus, Plus, RotateCcw, TriangleAlert } from "lucide-react";
import { useTheme } from "@serino/theme";
import { useEffect, useId, useRef, useState } from "react";
import { useFrontendI18n } from "@/i18n";

interface MarkdownMermaidProps {
  chart: string;
}

type MermaidRenderState = "loading" | "ready" | "error";
const MIN_ZOOM = 0.7;
const MAX_ZOOM = 2.2;
const ZOOM_STEP = 0.15;

export default function MarkdownMermaid({ chart }: MarkdownMermaidProps) {
  const { resolvedTheme } = useTheme();
  const { t } = useFrontendI18n();
  const renderId = useId().replace(/:/g, "");
  const containerRef = useRef<HTMLDivElement>(null);
  const [state, setState] = useState<MermaidRenderState>("loading");
  const [errorMessage, setErrorMessage] = useState("");
  const [zoom, setZoom] = useState(1);

  useEffect(() => {
    let cancelled = false;
    const cleanupContainer = () => {
      if (containerRef.current) {
        containerRef.current.innerHTML = "";
      }
    };

    const renderDiagram = async () => {
      const container = containerRef.current;
      if (!container) {
        return;
      }

      setState("loading");
      setErrorMessage("");
      setZoom(1);
      container.innerHTML = "";

      try {
        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: "strict",
          theme: "base",
          htmlLabels: false,
          themeVariables: resolvedTheme === "dark"
            ? {
                background: "#1b151a",
                primaryColor: "#232326",
                primaryBorderColor: "#cfd4dc",
                primaryTextColor: "#f5f7fa",
                lineColor: "#d6dce5",
                textColor: "#f5f7fa",
                mainBkg: "#232326",
                nodeBorder: "#d6dce5",
                edgeLabelBackground: "transparent",
            }
            : {
                background: "#f8f7f4",
                primaryColor: "#ffffff",
                primaryBorderColor: "#334155",
                primaryTextColor: "#1f2937",
                lineColor: "#475569",
                textColor: "#1f2937",
                mainBkg: "#ffffff",
                nodeBorder: "#475569",
                edgeLabelBackground: "transparent",
              },
          fontFamily: "Barlow, 'Noto Sans SC', 'PingFang SC', sans-serif",
          flowchart: {
            useMaxWidth: false,
            htmlLabels: false,
          },
        });

        const { svg, bindFunctions } = await mermaid.render(`markdown-mermaid-${renderId}`, chart);

        if (cancelled) {
          return;
        }

        container.innerHTML = svg;
        bindFunctions?.(container);
        setState("ready");
      } catch (error) {
        if (cancelled) {
          return;
        }

        setState("error");
        setErrorMessage(error instanceof Error ? error.message : t("mermaid.errorHint"));
        container.innerHTML = "";
      }
    };

    void renderDiagram();

    return () => {
      cancelled = true;
      cleanupContainer();
    };
  }, [chart, renderId, resolvedTheme, t]);

  return (
    <div className="markdown-mermaid-block">
      <div className="markdown-mermaid-surface" aria-busy={state === "loading"}>
        {state === "loading" ? (
          <div className="markdown-mermaid-placeholder">
            <LoaderCircle className="h-4 w-4 animate-spin" aria-label={t("mermaid.loading")} />
          </div>
        ) : null}

        {state === "error" ? (
          <div className="markdown-mermaid-error" role="status">
            <div className="markdown-mermaid-error-title">
              <TriangleAlert className="h-4 w-4" />
              <span>{t("mermaid.errorTitle")}</span>
            </div>
            <p>{errorMessage || t("mermaid.errorHint")}</p>
          </div>
        ) : null}

        <div className="markdown-mermaid-viewport">
          <div
            className={`markdown-mermaid-stage ${state === "ready" ? "is-ready" : ""}`}
            style={{ transform: `scale(${zoom})` }}
          >
            <div
              ref={containerRef}
              className={`markdown-mermaid-canvas ${state === "ready" ? "is-ready" : ""}`}
              aria-hidden={state !== "ready"}
            />
          </div>
        </div>

        {state === "ready" ? (
          <div className="markdown-mermaid-controls">
            <button
              type="button"
              className="markdown-mermaid-control"
              aria-label={t("mermaid.zoomOut")}
              title={t("mermaid.zoomOut")}
              onClick={() => setZoom((value) => Math.max(MIN_ZOOM, Number((value - ZOOM_STEP).toFixed(2))))}
            >
              <Minus className="h-3.5 w-3.5" />
            </button>
            <button
              type="button"
              className="markdown-mermaid-control"
              aria-label={t("mermaid.resetZoom")}
              title={t("mermaid.resetZoom")}
              onClick={() => setZoom(1)}
            >
              <RotateCcw className="h-3.5 w-3.5" />
            </button>
            <button
              type="button"
              className="markdown-mermaid-control"
              aria-label={t("mermaid.zoomIn")}
              title={t("mermaid.zoomIn")}
              onClick={() => setZoom((value) => Math.min(MAX_ZOOM, Number((value + ZOOM_STEP).toFixed(2))))}
            >
              <Plus className="h-3.5 w-3.5" />
            </button>
          </div>
        ) : null}
      </div>

      {state === "error" ? (
        <pre className="markdown-mermaid-source">
          <code>{chart}</code>
        </pre>
      ) : null}
    </div>
  );
}
