from collections.abc import Mapping

ToolResult = dict[str, object]


def tool_error(message: str) -> ToolResult:
    return {"error": message}


def count_label(count: int, singular: str, plural: str) -> str:
    if count == 1:
        return f"1 {singular}"
    return f"{count} {plural}"


def entries(result: Mapping[str, object], key: str) -> list[Mapping[str, object]]:
    value = result.get(key)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]
