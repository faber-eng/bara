import { useMutation } from "@tanstack/react-query";
import { signInWithGoogle } from "../../lib/auth";
import type { JoinCopy } from "../../lib/copy/join";

export function SignInPanel({ copy }: { copy: JoinCopy }) {
  const signIn = useMutation({ mutationFn: signInWithGoogle });
  return (
    <section className="card join-card" aria-labelledby="join-signin-title">
      <h2 id="join-signin-title" className="join-heading">
        {copy.signInTitle}
      </h2>
      <p>{copy.signInHint}</p>
      <button
        type="button"
        className="btn btn-primary btn-lg btn-block"
        disabled={signIn.isPending}
        onClick={() => signIn.mutate()}
      >
        {signIn.isPending ? copy.signingIn : copy.signInButton}
      </button>
      {signIn.isError && <p role="alert">{copy.signInError}</p>}
    </section>
  );
}
