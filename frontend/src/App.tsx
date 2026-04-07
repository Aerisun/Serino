import { Suspense, useEffect } from "react";
import { lazyWithPreload } from "@/lib/lazy";
import type { RuntimeConfigSnapshot } from "@/lib/runtime-config";

const AppRuntime = lazyWithPreload(() => import("./AppRuntime"));

const App = ({
  initialRuntimeConfig = null,
}: {
  initialRuntimeConfig?: RuntimeConfigSnapshot | null;
}) => {
  useEffect(() => {
    void AppRuntime.preload();
  }, []);

  return (
    <Suspense fallback={<div className="min-h-screen bg-background" />}>
      <AppRuntime initialRuntimeConfig={initialRuntimeConfig} />
    </Suspense>
  );
};

export default App;
