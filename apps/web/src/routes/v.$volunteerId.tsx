import { createFileRoute } from "@tanstack/react-router";
import { VolunteerScreen } from "../components/volunteer/VolunteerScreen";

function VolunteerRoute() {
  const { volunteerId } = Route.useParams();
  return <VolunteerScreen volunteerId={volunteerId} />;
}

export const Route = createFileRoute("/v/$volunteerId")({ component: VolunteerRoute });
