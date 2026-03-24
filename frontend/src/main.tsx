import { createRoot } from "react-dom/client";
import App from "./App.tsx";
import "./index.css";
import { initSentry } from "@serino/utils";

initSentry();

createRoot(document.getElementById("root")!).render(<App />);
