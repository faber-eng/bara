import { createFileRoute } from "@tanstack/react-router";
import { EmptyScreen } from "../components/EmptyScreen";

function DrawAreaScreen() {
  return <EmptyScreen title="Draw an area" path="/area/new" />;
}

export const Route = createFileRoute("/area/new")({ component: DrawAreaScreen });
