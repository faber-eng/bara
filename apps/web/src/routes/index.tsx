import { createFileRoute } from "@tanstack/react-router";
import { LandingScreen } from "../components/landing/LandingScreen";

export const Route = createFileRoute("/")({ component: LandingScreen });
