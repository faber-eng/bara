import { createRootRoute, Outlet, useLocation } from "@tanstack/react-router";
import { AppBar } from "../components/AppBar";
import { HealthFooter } from "../components/HealthFooter";
import { JudgeGate } from "../components/judge/JudgeGate";
import { NotFound } from "../components/NotFound";
import { TourDock } from "../components/tour/TourDock";

const SIGN_IN_FREE_PATH = "/public";
const LANDING_PATH = "/";

function isSignInFree(pathname: string): boolean {
  if (pathname === LANDING_PATH) return true;
  return pathname === SIGN_IN_FREE_PATH || pathname.startsWith(`${SIGN_IN_FREE_PATH}/`);
}

function RootLayout() {
  const pathname = useLocation({ select: (location) => location.pathname });
  const needsGate = !isSignInFree(pathname);
  const page = (
    <main className="shell-main">
      <Outlet />
    </main>
  );
  return (
    <div className="shell">
      <AppBar />
      {needsGate ? <JudgeGate>{page}</JudgeGate> : page}
      <TourDock />
      <HealthFooter />
    </div>
  );
}

export const Route = createRootRoute({ component: RootLayout, notFoundComponent: NotFound });
