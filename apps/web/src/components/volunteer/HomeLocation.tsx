import { useState } from "react";
import type { GeoPoint, VolunteerRole } from "../../lib/contracts";
import type { VolunteerCopy } from "../../lib/copy/volunteer";
import { MiniMap } from "../brigade/MiniMap";

const HOME_DIGITS = 5;

type HomeLocationProps = {
  copy: VolunteerCopy;
  home: GeoPoint | null | undefined;
  name: string | null | undefined;
  volunteerRole: VolunteerRole | null | undefined;
};

function homeMapUrl(home: GeoPoint): string {
  return `https://www.google.com/maps/search/?api=1&query=${home.lat},${home.lon}`;
}

function whoText(
  copy: VolunteerCopy,
  name: string | null | undefined,
  volunteerRole: VolunteerRole | null | undefined,
) {
  const parts = [name, volunteerRole ? copy.home.roles[volunteerRole] : null];
  return parts.filter((part) => part).join(", ");
}

export function HomeLocation({ copy, home, name, volunteerRole }: HomeLocationProps) {
  const [opened, setOpened] = useState(false);
  if (!home) return null;
  return (
    <details className="home-location" onToggle={(event) => setOpened(event.currentTarget.open)}>
      <summary>{copy.home.title}</summary>
      {opened && (
        <div className="home-location-body">
          <p className="ops-meta">{whoText(copy, name, volunteerRole)}</p>
          <MiniMap
            mapUrl={homeMapUrl(home)}
            digits={HOME_DIGITS}
            labels={{ unavailable: copy.home.mapUnavailable, open: copy.home.openInMaps }}
          />
        </div>
      )}
    </details>
  );
}
