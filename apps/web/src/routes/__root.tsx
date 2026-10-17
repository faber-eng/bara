import { createRootRoute, Outlet } from "@tanstack/react-router";
import { AppBar } from "../components/AppBar";
import { HealthFooter } from "../components/HealthFooter";
import { NotFound } from "../components/NotFound";

function RootLayout() {
  return (
    <div className="shell">
      <AppBar />
      <main className="shell-main">
        <Outlet />
      </main>
      <HealthFooter />
    </div>
  );
}

export const Route = createRootRoute({ component: RootLayout, notFoundComponent: NotFound });
