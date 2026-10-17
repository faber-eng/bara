import { createRootRoute, Outlet } from "@tanstack/react-router";
import { AppBar } from "../components/AppBar";
import { HealthFooter } from "../components/HealthFooter";
import { JudgeGate } from "../components/judge/JudgeGate";
import { NotFound } from "../components/NotFound";

function RootLayout() {
  return (
    <div className="shell">
      <AppBar />
      <JudgeGate>
        <main className="shell-main">
          <Outlet />
        </main>
      </JudgeGate>
      <HealthFooter />
    </div>
  );
}

export const Route = createRootRoute({ component: RootLayout, notFoundComponent: NotFound });
