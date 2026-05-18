import orjson
import pytest

from zlm.utils.entries import deserialize_entry, serialize_entry, validate_entry


@pytest.mark.parametrize(
    "entry",
    [
        {"type": "verdict", "body": "retry"},
        {"type": "flag", "body": True},
        {"type": "score", "body": 0.91},
        {"type": "decision", "body": {"mode": "fallback", "reason": "timeout"}},
        {"type": "noop", "body": None},
        {"type": "tags", "body": ["stale", "temporary"]},
    ],
)
def test_validate_entry_accepts_supported_shapes(entry: dict[str, object]) -> None:
    assert validate_entry(entry) == entry


@pytest.mark.parametrize(
    ("entry", "error_type", "message"),
    [
        ("bad", TypeError, "entry must be a dict"),
        ({"body": 1}, ValueError, "'type'"),
        ({"type": "score"}, ValueError, "'body'"),
        ({"type": 1, "body": 1}, TypeError, "must be a string"),
    ],
)
def test_validate_entry_rejects_invalid_shapes(entry: object, error_type: type[Exception], message: str) -> None:
    with pytest.raises(error_type, match=message):
        validate_entry(entry)


def test_serialize_and_deserialize_entry_round_trip() -> None:
    entry = {"type": "tags", "body": ["stale", "temporary"]}

    payload = serialize_entry(entry)

    assert isinstance(payload, bytes)
    assert deserialize_entry(payload) == entry


def test_serialize_entry_raises_for_non_json_body() -> None:
    with pytest.raises(orjson.JSONEncodeError, match="not JSON serializable"):
        serialize_entry({"type": "score", "body": object()})


def test_deserialize_entry_rejects_invalid_decoded_shape() -> None:
    payload = orjson.dumps({"body": "retry"})

    with pytest.raises(ValueError, match="'type'"):
        deserialize_entry(payload)


def test_deserialize_entry_raises_for_invalid_json() -> None:
    with pytest.raises(orjson.JSONDecodeError):
        deserialize_entry(b"not-json")