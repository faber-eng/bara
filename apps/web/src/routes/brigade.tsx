import { createFileRoute } from "@tanstack/react-router";
import { BrigadeInbox } from "../components/brigade/BrigadeInbox";

export const Route = createFileRoute("/brigade")({ component: BrigadeInbox });
