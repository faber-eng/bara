import { createFileRoute } from "@tanstack/react-router";
import { EmptyScreen } from "../components/EmptyScreen";

function OpsScreen() {
  return <EmptyScreen title="Ops dashboard" path="/ops" />;
}

export const Route = createFileRoute("/ops")({ component: OpsScreen });
