from google.genai import errors, types


def api_error(code: int) -> errors.APIError:
    return errors.APIError(code, {"error": {"code": code, "message": f"status {code}"}})


class FakeModels:
    def __init__(self, outcomes: list[types.GenerateContentResponse | Exception]):
        self._outcomes = list(outcomes)
        self.calls: list[str] = []

    async def generate_content(
        self,
        *,
        model: str,
        contents: types.ContentListUnion,
        config: types.GenerateContentConfigOrDict | None = None,
    ) -> types.GenerateContentResponse:
        self.calls.append(model)
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome
