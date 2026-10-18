import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { saveHome } from "../../lib/api/volunteer";
import type { GeoPoint } from "../../lib/contracts";
import { joinCopy } from "../../lib/copy/join";
import { useCopyLanguage } from "../../lib/copy/language";
import type { VolunteerCopy } from "../../lib/copy/volunteer";
import { HomePicker } from "../join/HomePicker";
import { inboxKey } from "./inboxQuery";

type HomeEditorProps = { copy: VolunteerCopy; volunteerId: string; onClose: () => void };

function SaveStatus({
  copy,
  saved,
  failed,
}: {
  copy: VolunteerCopy;
  saved: boolean;
  failed: boolean;
}) {
  if (failed) return <p role="alert">{copy.home.saveFailed}</p>;
  if (saved) return <p role="status">{copy.home.saved}</p>;
  return null;
}

export function HomeEditor({ copy, volunteerId, onClose }: HomeEditorProps) {
  const language = useCopyLanguage();
  const queryClient = useQueryClient();
  const [pin, setPin] = useState<GeoPoint | null>(null);
  const save = useMutation({
    mutationFn: (point: GeoPoint) => saveHome(volunteerId, point),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: inboxKey(volunteerId) }),
  });

  function choose(point: GeoPoint) {
    save.reset();
    setPin(point);
  }

  return (
    <div className="home-editor">
      <HomePicker copy={joinCopy(language)} value={pin} invalid={false} onChange={choose} />
      <button
        type="button"
        className="btn btn-primary btn-sm"
        disabled={pin === null || save.isPending}
        onClick={() => pin !== null && save.mutate(pin)}
      >
        {save.isPending ? copy.home.saving : copy.home.save}
      </button>
      <SaveStatus copy={copy} saved={save.isSuccess} failed={save.isError} />
      <button type="button" className="btn btn-secondary btn-sm" onClick={onClose}>
        {copy.cancel}
      </button>
    </div>
  );
}
