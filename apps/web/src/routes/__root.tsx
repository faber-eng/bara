import { createRootRoute, Outlet, useLocation } from "@tanstack/react-router";
import { AppBar } from "../components/AppBar";
import { HealthFooter } from "../components/HealthFooter";
import { JudgeGate } from "../components/judge/JudgeGate";
import { NotFound } from "../components/NotFound";

const SIGN_IN_FREE_PREFIX = "/public";

function RootLayout() {
  const pathname = useLocation({ select: (location) => location.pathname });
  const needsGate = !pathname.startsWith(SIGN_IN_FREE_PREFIX);
  const page = (
    <main className="shell-main">
      <Outlet />
    </main>
  );
  return (
    <div className="shell">
      <AppBar />
      {needsGate ? <JudgeGate>{page}</JudgeGate> : page}
      <HealthFooter />
    </div>
  );
}

export const Route = createRootRoute({ component: RootLayout, notFoundComponent: NotFound });
