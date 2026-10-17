export type JudgeRole = "ops" | "volunteer" | "brigade";

export type JudgePerson = {
  key: string;
  label: string;
  role: JudgeRole;
  path: string;
};

export const JUDGE_PEOPLE: readonly JudgePerson[] = [
  { key: "ops", label: "Ops", role: "ops", path: "/ops" },
  { key: "vol-ari", label: "Volunteer Ari (example)", role: "volunteer", path: "/v/vol-ari" },
  {
    key: "team-sari",
    label: "Repair team Sari (example)",
    role: "volunteer",
    path: "/v/team-sari",
  },
  { key: "vol-dedi", label: "Patrol Dedi (example)", role: "volunteer", path: "/v/vol-dedi" },
  {
    key: "contact-daops-pekanbaru",
    label: "Brigade Pekanbaru (example)",
    role: "brigade",
    path: "/brigade",
  },
];

export const DEFAULT_PERSON_KEY = "ops";

export function personFor(key: string): JudgePerson | undefined {
  return JUDGE_PEOPLE.find((person) => person.key === key);
}
