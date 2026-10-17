from contracts import Channels, Contact

DEFAULT_ORG = "Brigade"
DEFAULT_REGION = "riau"


def contact_name(display_name: str | None, email: str) -> str:
    if display_name is not None and display_name.strip() != "":
        return display_name.strip()
    return email.partition("@")[0]


def build_brigade_contact(
    uid: str, display_name: str | None, email: str, org: str, region: str
) -> Contact:
    return Contact(
        id=uid,
        name=contact_name(display_name, email),
        org=org,
        channels=Channels(web=True, whatsapp=None),
        region=region,
        example=False,
    )
