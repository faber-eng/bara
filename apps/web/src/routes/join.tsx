import { createFileRoute } from "@tanstack/react-router";
import { JoinScreen } from "../components/join/JoinScreen";

export const Route = createFileRoute("/join")({ component: JoinScreen });
