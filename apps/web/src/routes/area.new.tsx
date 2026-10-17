import { createFileRoute } from "@tanstack/react-router";
import { AreaScreen } from "../components/samples/AreaScreen";

export const Route = createFileRoute("/area/new")({ component: AreaScreen });
