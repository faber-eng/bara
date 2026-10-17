import { createFileRoute } from "@tanstack/react-router";
import { EmptyScreen } from "../components/EmptyScreen";

function PublicScreen() {
  return <EmptyScreen title="Public dashboard" path="/public" />;
}

export const Route = createFileRoute("/public")({ component: PublicScreen });
