import importlib.util
import io
import subprocess
import sys
from pathlib import Path

import pytest

from adapters.firestore_repos import ContactRepository
from adapters.identity import IdentityUnavailable
from contracts import Contact
from tests.fakes import FakeClaimsAdmin, InMemoryCollection

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "grant_role.py"
ENV = {"PROJECT": "example-project"}


def load_script():
    spec = importlib.util.spec_from_file_location("grant_role_script", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = load_script()


def new_contacts():
    return ContactRepository(InMemoryCollection(Contact))


def run(argv, admin=None, environ=None, contacts=None):
    admin = admin or FakeClaimsAdmin(
        {"u1": {"role": "volunteer", "locale": "id"}}, {"a@b.test": "u1"}
    )
    out, err = io.StringIO(), io.StringIO()
    projects = []

    def factory(project):
        projects.append(project)
        return admin

    store = contacts if contacts is not None else new_contacts()
    code = script.main(
        argv,
        environ=ENV if environ is None else environ,
        admin_factory=factory,
        contacts_factory=lambda project: store,
        out=out,
        err=err,
    )
    return code, out.getvalue(), err.getvalue(), admin, projects


@pytest.mark.parametrize("role", ["ops", "brigade"])
def test_a_grant_merges_the_role_prints_uid_and_role_and_exits_0(role):
    code, out, _, admin, _ = run(["a@b.test", role])

    assert code == 0
    assert out == f"u1 {role}\n"
    assert admin.claims_by_uid["u1"] == {"role": role, "locale": "id"}


@pytest.mark.parametrize("role", ["volunteer", "judge", "root"])
def test_a_role_outside_ops_and_brigade_is_a_usage_error(role):
    code, out, _, admin, _ = run(["a@b.test", role])

    assert code == 2
    assert out == ""
    assert admin.writes == []


def test_no_arguments_is_a_usage_error():
    code, out, err, _, _ = run([])

    assert code == 2
    assert out == ""
    assert "usage" in err.lower()


def test_a_wrong_flag_is_a_usage_error():
    code, _, _, admin, _ = run(["a@b.test", "ops", "--nope"])

    assert code == 2
    assert admin.writes == []


def test_help_exits_0_and_lists_the_flags():
    code, out, _, _, _ = run(["--help"])

    assert code == 0
    for flag in ("--project", "--dry-run"):
        assert flag in out


def test_an_unknown_email_exits_3_and_says_to_sign_in_once():
    code, out, err, _, _ = run(["who@b.test", "ops"])

    assert code == 3
    assert out == ""
    assert "sign in with Google once first" in err


def test_a_firebase_error_exits_4():
    admin = FakeClaimsAdmin(uid_by_email={"a@b.test": "u1"})
    admin.fail_with = IdentityUnavailable("permission denied")

    code, out, err, _, _ = run(["a@b.test", "ops"], admin=admin)

    assert code == 4
    assert out == ""
    assert "permission denied" in err


def test_any_other_failure_exits_1():
    admin = FakeClaimsAdmin(uid_by_email={"a@b.test": "u1"})
    admin.fail_with = RuntimeError("boom")

    code, _, err, _, _ = run(["a@b.test", "ops"], admin=admin)

    assert code == 1
    assert "boom" in err


def test_dry_run_prints_the_same_line_and_writes_nothing():
    code, out, _, admin, _ = run(["a@b.test", "ops", "--dry-run"])

    assert code == 0
    assert out == "u1 ops\n"
    assert admin.writes == []


def test_a_missing_project_exits_2_and_names_the_flag(tmp_path):
    code, out, err, _, _ = run(
        ["a@b.test", "ops"], environ={"BARA_ENV": str(tmp_path / "none.env")}
    )

    assert code == 2
    assert out == ""
    assert "--project" in err


def test_the_project_flag_beats_the_environment():
    _, _, _, _, projects = run(["a@b.test", "ops", "--project", "flag-project"])

    assert projects == ["flag-project"]


def test_the_project_falls_back_to_the_environment():
    _, _, _, _, projects = run(["a@b.test", "ops"])

    assert projects == ["example-project"]


def test_the_project_falls_back_to_the_secrets_file(tmp_path):
    env_file = tmp_path / "bara.env"
    env_file.write_text('OTHER=1\nPROJECT="file-project"\n')

    _, _, _, _, projects = run(["a@b.test", "ops"], environ={"BARA_ENV": str(env_file)})

    assert projects == ["file-project"]


def test_the_real_entry_point_prints_help_and_exits_0():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--dry-run" in result.stdout


def test_the_real_entry_point_with_no_arguments_exits_2():
    result = subprocess.run(
        [sys.executable, str(SCRIPT)], check=False, capture_output=True, text=True
    )

    assert result.returncode == 2
    assert result.stdout == ""


def test_granting_brigade_creates_the_contact_for_the_uid():
    admin = FakeClaimsAdmin(
        uid_by_email={"b@b.test": "u7"}, names_by_uid={"u7": "Bu Rina"}
    )
    contacts = new_contacts()

    code, out, err, _, _ = run(["b@b.test", "brigade"], admin=admin, contacts=contacts)

    assert code == 0
    assert out == "u7 brigade\n"
    contact = contacts.get("u7")
    assert (contact.name, contact.region, contact.example) == ("Bu Rina", "riau", False)
    assert contact.channels.web is True
    assert "contacts/u7 created" in err


def test_the_name_falls_back_to_the_email_name_and_the_flags_set_org_and_region():
    admin = FakeClaimsAdmin(uid_by_email={"rina@b.test": "u7"})
    contacts = new_contacts()

    run(
        ["rina@b.test", "brigade", "--org", "Manggala Agni", "--region", "riau"],
        admin=admin,
        contacts=contacts,
    )

    contact = contacts.get("u7")
    assert (contact.name, contact.org) == ("rina", "Manggala Agni")


def test_an_existing_contact_is_left_as_it_is():
    admin = FakeClaimsAdmin(
        uid_by_email={"b@b.test": "u7"}, names_by_uid={"u7": "New Name"}
    )
    contacts = new_contacts()
    first_code, *_ = run(["b@b.test", "brigade"], admin=admin, contacts=contacts)
    admin.names_by_uid["u7"] = "Changed"

    code, _, err, _, _ = run(["b@b.test", "brigade"], admin=admin, contacts=contacts)

    assert (first_code, code) == (0, 0)
    assert contacts.get("u7").name == "New Name"
    assert "contacts/u7 exists" in err


def test_granting_ops_creates_no_contact():
    contacts = new_contacts()

    run(["a@b.test", "ops"], contacts=contacts)

    assert contacts.get("u1") is None


def test_brigade_dry_run_creates_no_contact_and_says_so():
    contacts = new_contacts()

    code, out, err, admin, _ = run(
        ["a@b.test", "brigade", "--dry-run"], contacts=contacts
    )

    assert code == 0
    assert out == "u1 brigade\n"
    assert contacts.get("u1") is None
    assert admin.writes == []
    assert "would create contacts/u1" in err


def test_a_firestore_error_exits_5_and_says_the_claim_is_set():
    from google.api_core.exceptions import PermissionDenied

    class Refusing(InMemoryCollection):
        def create_if_absent(self, doc_id, item):
            raise PermissionDenied("no datastore.user")

    contacts = ContactRepository(Refusing(Contact))

    code, out, err, _, _ = run(["a@b.test", "brigade"], contacts=contacts)

    assert code == 5
    assert out == ""
    assert "claim is set" in err


def test_help_lists_the_contact_flags():
    _, out, _, _, _ = run(["--help"])

    assert "--region" in out
    assert "--org" in out
