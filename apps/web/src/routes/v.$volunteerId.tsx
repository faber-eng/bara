import { createFileRoute } from "@tanstack/react-router";
import { EmptyScreen } from "../components/EmptyScreen";

function VolunteerScreen() {
  const { volunteerId } = Route.useParams();
  return <EmptyScreen title="Volunteer PWA" path={`/v/${volunteerId}`} />;
}

export const Route = createFileRoute("/v/$volunteerId")({ component: VolunteerScreen });
