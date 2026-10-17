import { getUid } from "../auth";
import { JUDGE_PEOPLE } from "../judge/people";
import { getJudgeSnapshot } from "../judge/store";

const BRIGADE_ROLE = "brigade";

export async function brigadeContactId(): Promise<string> {
  if (getJudgeSnapshot().judgeMode) return judgeBrigadeContactId();
  return getUid();
}

function judgeBrigadeContactId(): string {
  const person = JUDGE_PEOPLE.find((candidate) => candidate.role === BRIGADE_ROLE);
  if (person === undefined) throw new Error("No brigade contact in the judge people");
  return person.key;
}
