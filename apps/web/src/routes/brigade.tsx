import { createFileRoute } from "@tanstack/react-router";
import { EmptyScreen } from "../components/EmptyScreen";

function BrigadeScreen() {
  return <EmptyScreen title="Brigade inbox" path="/brigade" />;
}

export const Route = createFileRoute("/brigade")({ component: BrigadeScreen });
