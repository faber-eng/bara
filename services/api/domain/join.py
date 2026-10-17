import hmac
from collections.abc import Mapping

from auth import Role, role_from_claim
from contracts import Channels, JoinRequest, Volunteer


def codes_match(supplied: str, expected: str) -> bool:
    if expected == "":
        return False
    return hmac.compare_digest(supplied.encode(), expected.encode())


def with_role(claims: Mapping[str, object], role: Role) -> dict[str, object]:
    return {**claims, "role": role}


def claims_after_join(claims: Mapping[str, object]) -> dict[str, object]:
    if role_from_claim(claims) is not None:
        return dict(claims)
    return with_role(claims, "volunteer")


def build_volunteer(uid: str, request: JoinRequest, region: str) -> Volunteer:
    return Volunteer(
        id=uid,
        name=request.name,
        role="volunteer",
        region=region,
        home=request.home,
        language=request.language,
        channels=Channels(web=True, whatsapp=request.whatsapp),
        available=True,
        example=False,
    )
