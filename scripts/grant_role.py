import argparse
import contextlib
import os
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TextIO

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "services" / "api"))

from google.api_core.exceptions import GoogleAPICallError

from adapters.firestore_repos import ContactRepository
from adapters.identity import (
    ClaimsAdmin,
    IdentityUnavailable,
    UserNotFound,
    grant_role,
)
from domain.brigade_contact import DEFAULT_ORG, DEFAULT_REGION, build_brigade_contact

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_USAGE = 2
EXIT_NO_USER = 3
EXIT_FIREBASE = 4
EXIT_FIRESTORE = 5
GRANTABLE = ("ops", "brigade")
DESCRIPTION = (
    "Give a signed-in user the ops or brigade role. Prints '<uid> <role>'. "
    "The user must have signed in with Google once first. Granting brigade also "
    "creates contacts/<uid> if it is absent, so the brigade inbox opens for that user."
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="grant_role.py", description=DESCRIPTION)
    parser.add_argument("email")
    parser.add_argument("role", choices=GRANTABLE)
    parser.add_argument(
        "--project", help="GCP project; else PROJECT or .secrets/bara.env"
    )
    parser.add_argument(
        "--region", default=DEFAULT_REGION, help="region of the brigade contact"
    )
    parser.add_argument(
        "--org", default=DEFAULT_ORG, help="organisation of the brigade contact"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="look the user up, write nothing"
    )
    return parser


def read_env_file(path: Path, key: str) -> str | None:
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return None
    found = None
    for line in lines:
        name, separator, value = line.partition("=")
        if separator and name.strip() == key:
            found = value.strip().strip('"').strip("'")
    return found or None


def resolve_project(flag: str | None, environ: Mapping[str, str]) -> str | None:
    if flag:
        return flag
    if environ.get("PROJECT"):
        return environ["PROJECT"]
    env_file = Path(environ.get("BARA_ENV") or REPO / ".secrets" / "bara.env")
    return read_env_file(env_file, "PROJECT")


def build_admin(project: str) -> ClaimsAdmin:
    import firebase_admin

    from adapters.identity import FirebaseClaimsAdmin

    firebase_admin.initialize_app(options={"projectId": project})
    return FirebaseClaimsAdmin()


def build_contacts(project: str) -> ContactRepository:
    from google.cloud import firestore

    from adapters.store import FirestoreCollection
    from contracts import Contact

    client = firestore.Client(project=project)
    return ContactRepository(FirestoreCollection(client, "contacts", Contact))


def ensure_contact(
    args: argparse.Namespace,
    admin: ClaimsAdmin,
    contacts: ContactRepository,
    uid: str,
    err: TextIO,
) -> None:
    exists = contacts.get(uid) is not None
    if exists:
        print(f"contacts/{uid} exists", file=err)
        return
    if args.dry_run:
        print(f"dry run: would create contacts/{uid}", file=err)
        return
    contact = build_brigade_contact(
        uid, admin.display_name(uid), args.email, args.org, args.region
    )
    created = contacts.create_if_absent(contact)
    print(f"contacts/{uid} {'created' if created else 'exists'}", file=err)


def parse(argv: list[str], out: TextIO, err: TextIO) -> argparse.Namespace | int:
    parser = build_parser()
    if not argv:
        parser.print_help(err)
        return EXIT_USAGE
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            return parser.parse_args(argv)
        except SystemExit as stop:
            return int(stop.code or 0)


def main(
    argv: list[str],
    environ: Mapping[str, str] = os.environ,
    admin_factory: Callable[[str], ClaimsAdmin] = build_admin,
    contacts_factory: Callable[[str], ContactRepository] = build_contacts,
    out: TextIO = sys.stdout,
    err: TextIO = sys.stderr,
) -> int:
    args = parse(argv, out, err)
    if isinstance(args, int):
        return args
    project = resolve_project(args.project, environ)
    if project is None:
        print(
            "no project set\npass --project <id>, set PROJECT, "
            "or put PROJECT=<id> in .secrets/bara.env",
            file=err,
        )
        return EXIT_USAGE
    return run(args, admin_factory(project), contacts_factory(project), out, err)


def run(
    args: argparse.Namespace,
    admin: ClaimsAdmin,
    contacts: ContactRepository,
    out: TextIO,
    err: TextIO,
) -> int:
    try:
        result = grant_role(admin, args.email, args.role, args.dry_run)
        if args.role == "brigade":
            ensure_contact(args, admin, contacts, result.uid, err)
    except UserNotFound:
        print(
            f"no user with email {args.email}\n"
            "ask them to sign in with Google once first, then run this again",
            file=err,
        )
        return EXIT_NO_USER
    except IdentityUnavailable as error:
        print(
            f"Firebase refused the request: {error}\n"
            "check the project, your ADC login and roles/firebaseauth.admin",
            file=err,
        )
        return EXIT_FIREBASE
    except GoogleAPICallError as error:
        print(
            f"Firestore refused the request: {type(error).__name__}: {error}\n"
            "the claim is set; check roles/datastore.user and run this again",
            file=err,
        )
        return EXIT_FIRESTORE
    except (OSError, RuntimeError, ValueError) as error:
        print(f"failed: {type(error).__name__}: {error}", file=err)
        return EXIT_FAILURE
    if args.dry_run:
        print("dry run: no claim written", file=err)
    print(f"{result.uid} {result.role}", file=out)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
