import { useNavigate } from "@tanstack/react-router";
import { joinCopy } from "../../lib/copy/join";
import { useCopyLanguage } from "../../lib/copy/language";
import { type AuthState, useAuthUser } from "../../lib/useAuthUser";
import { LanguageToggle } from "../LanguageToggle";
import { JoinForm } from "./JoinForm";
import { SignInPanel } from "./SignInPanel";

function JoinBody({ auth, onJoined }: { auth: AuthState; onJoined: (id: string) => void }) {
  const copy = joinCopy(useCopyLanguage());
  if (auth.status === "loading") return <p role="status">{copy.checkingSignIn}</p>;
  if (auth.status === "failed") return <p role="alert">{copy.signInFailed}</p>;
  if (auth.user === null || auth.user.isAnonymous) return <SignInPanel copy={copy} />;
  return (
    <>
      <p>{copy.signedInAs(auth.user.displayName)}</p>
      <JoinForm copy={copy} onJoined={onJoined} />
    </>
  );
}

export function JoinScreen() {
  const copy = joinCopy(useCopyLanguage());
  const auth = useAuthUser();
  const navigate = useNavigate();

  function handleJoined(volunteerId: string) {
    void navigate({ to: "/v/$volunteerId", params: { volunteerId } });
  }

  return (
    <section className="screen-center join">
      <LanguageToggle label={copy.toggleLabel} />
      <h1 className="screen-title">{copy.title}</h1>
      <p className="lede">{copy.lede}</p>
      <JoinBody auth={auth} onJoined={handleJoined} />
    </section>
  );
}
