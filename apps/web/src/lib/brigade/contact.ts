import { getIdToken } from "../auth";
import { JUDGE_PEOPLE } from "../judge/people";
import { getJudgeSnapshot } from "../judge/store";
import { sourceFor } from "../sources";
import { isRealUser, readTokenIdentity, type TokenIdentity } from "../tokenIdentity";

const BRIGADE_ROLE = "brigade";

export function judgeBrigadeContactId(): string {
  const person = JUDGE_PEOPLE.find((candidate) => candidate.role === BRIGADE_ROLE);
  if (person === undefined) throw new Error("No brigade contact in the judge people");
  return person.key;
}

function anonymousContactId(identity: TokenIdentity | null): string {
  if (getJudgeSnapshot().judgeMode) return judgeBrigadeContactId();
  if (identity === null) throw new Error("The sign-in token has no user id");
  return identity.uid;
}

export async function brigadeContactId(): Promise<string> {
  const identity = readTokenIdentity(await getIdToken());
  if (isRealUser(identity)) return identity.uid;
  return anonymousContactId(identity);
}

export function isExampleContact(contactId: string | undefined): boolean {
  if (sourceFor("escalations") === "fixture") return true;
  return contactId === judgeBrigadeContactId();
}
