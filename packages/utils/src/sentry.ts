export function initSentry() {
  const dsn = import.meta.env.VITE_SENTRY_DSN;
  if (dsn) {
    import("@sentry/react").then((Sentry) => {
      Sentry.init({
        dsn,
        environment: import.meta.env.MODE,
        tracesSampleRate: 0.1,
      });
    });
  }
}
