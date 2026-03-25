import { createRoot } from "react-dom/client";
import App from "./App.tsx";
import "./index.css";
import { initSentry } from "@serino/utils";
import { initPublicClient } from "@serino/api-client";

const envApiBaseUrl =
  (typeof __AERISUN_API_BASE_URL__ === "string" ? __AERISUN_API_BASE_URL__ : "").replace(
    /\/+$/,
    "",
  );

initPublicClient({ baseUrl: envApiBaseUrl });
initSentry();

createRoot(document.getElementById("root")!).render(<App />);
