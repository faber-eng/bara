import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "@tanstack/react-router";
import { type ChangeEvent, useSyncExternalStore } from "react";
import { invalidateWorld } from "../../lib/judge/invalidate";
import { JUDGE_PEOPLE, personFor } from "../../lib/judge/people";
import { getJudgeSnapshot, selectPerson, subscribeJudge } from "../../lib/judge/store";

export function RoleSwitcher() {
  const queryClient = useQueryClient();
  const router = useRouter();
  const { personKey } = useSyncExternalStore(subscribeJudge, getJudgeSnapshot);

  function handleChange(event: ChangeEvent<HTMLSelectElement>) {
    const person = personFor(event.target.value);
    if (person === undefined) return;
    selectPerson(person.key);
    router.history.push(person.path);
    void invalidateWorld(queryClient);
  }

  return (
    <>
      <label className="visually-hidden" htmlFor="judge-role">
        Role
      </label>
      <select className="select" id="judge-role" value={personKey} onChange={handleChange}>
        {JUDGE_PEOPLE.map((person) => (
          <option key={person.key} value={person.key}>
            {person.label}
          </option>
        ))}
      </select>
    </>
  );
}
