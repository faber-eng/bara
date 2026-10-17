import { createFileRoute } from "@tanstack/react-router";
import { EmptyScreen } from "../components/EmptyScreen";

function LandingScreen() {
  return <EmptyScreen title="Landing and tour" path="/" />;
}

export const Route = createFileRoute("/")({ component: LandingScreen });
