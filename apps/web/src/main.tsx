import "./styles/kit.css";
import "./styles/app.css";
import "./styles/map-views.css";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createAppRouter } from "./router";
import { registerServiceWorker } from "./sw/register";

const queryClient = new QueryClient();
const router = createAppRouter();

const rootElement = document.getElementById("root");
if (rootElement === null) throw new Error("index.html has no #root element");

createRoot(rootElement).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
);

registerServiceWorker();
