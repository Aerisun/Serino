import { Component, type ErrorInfo, type ReactNode } from "react";
import { frontendTranslations, type FrontendLang } from "@/i18n/translations";
import { getFrontendLang } from "@/i18n";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
}

class ErrorBoundary extends Component<Props, State> {
  private copy(lang: FrontendLang) {
    return {
      title: frontendTranslations[lang]["errorBoundary.title"],
      description: frontendTranslations[lang]["errorBoundary.description"],
      reload: frontendTranslations[lang]["errorBoundary.reload"],
    };
  }

  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("ErrorBoundary caught an error:", error, info);
    import("@sentry/react")
      .then((Sentry) => Sentry.captureException(error))
      .catch(() => {});
  }

  render(): ReactNode {
    if (this.state.hasError) {
      const copy = this.copy(getFrontendLang());
      return (
        <div className="flex min-h-screen items-center justify-center">
          <div className="text-center">
            <h1 className="mb-4 text-2xl font-bold">{copy.title}</h1>
            <p className="mb-6 text-gray-600 dark:text-gray-400">{copy.description}</p>
            <button
              className="rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700"
              onClick={() => window.location.reload()}
            >
              {copy.reload}
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
