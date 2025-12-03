"""Tests for fara state I/O — message round-trip serialization + trim integration."""

from __future__ import annotations

import json

import pytest
from PIL import Image

from magentic_ui.agents.web_surfer.fara._fara_qwen3 import (
    FaraQwen3Agent,
    FaraQwen3AgentConfig,
    FaraQwen3AgentState,
)
from magentic_ui.agents.web_surfer.fara._state_io import (
    message_from_dict,
    message_to_dict,
)
from magentic_ui.agents.web_surfer.fara._types import ImageObj, LLMMessage


def _img(color: str = "red") -> ImageObj:
    return ImageObj.from_pil(Image.new("RGB", (8, 8), color))


def test_text_only_message_round_trips():
    msg = LLMMessage(role="user", content="hello world", metadata={"k": "v"})
    out = message_from_dict(message_to_dict(msg))
    assert out.role == "user"
    assert out.content == "hello world"
    assert out.metadata == {"k": "v"}


def test_assistant_text_message_no_metadata():
    msg = LLMMessage(role="assistant", content="reply")
    out = message_from_dict(message_to_dict(msg))
    assert out.role == "assistant"
    assert out.content == "reply"
    assert out.metadata is None


def test_system_message_round_trips():
    msg = LLMMessage(role="system", content="you are a helpful agent")
    out = message_from_dict(message_to_dict(msg))
    assert out.role == "system"
    assert out.content == "you are a helpful agent"


def test_image_plus_text_round_trips():
    img = _img("blue")
    msg = LLMMessage(
        role="user",
        content=[img, "describe this"],
        metadata={"is_original": True},
    )
    out = message_from_dict(message_to_dict(msg))

    assert out.role == "user"
    assert out.metadata == {"is_original": True}
    assert isinstance(out.content, list)
    assert len(out.content) == 2

    restored_img, restored_text = out.content
    assert isinstance(restored_img, ImageObj)
    assert restored_img.image.size == (8, 8)
    # Pixel data preserved
    assert restored_img.image.getpixel((0, 0)) == (0, 0, 255)
    assert restored_text == "describe this"


def test_multiple_images_in_one_message():
    msg = LLMMessage(
        role="user",
        content=[_img("red"), "first", _img("green"), "second"],
    )
    out = message_from_dict(message_to_dict(msg))

    assert isinstance(out.content, list)
    assert len(out.content) == 4
    assert isinstance(out.content[0], ImageObj)
    assert out.content[1] == "first"
    assert isinstance(out.content[2], ImageObj)
    assert out.content[3] == "second"
    # Distinct pixel values prove we didn't share encoded bytes
    assert out.content[0].image.getpixel((0, 0)) == (255, 0, 0)
    assert out.content[2].image.getpixel((0, 0)) == (0, 128, 0)


def test_dict_form_is_json_serializable():
    msg = LLMMessage(role="user", content=[_img(), "x"], metadata={"a": 1})
    encoded = message_to_dict(msg)
    # Round-trip through json.dumps to confirm no non-serializable bits leaked
    text = json.dumps(encoded)
    decoded = json.loads(text)
    out = message_from_dict(decoded)
    assert isinstance(out.content, list)
    assert isinstance(out.content[0], ImageObj)
    assert out.content[1] == "x"


def test_unknown_part_type_is_skipped():
    payload = {
        "role": "user",
        "content": [
            {"type": "text", "text": "ok"},
            {"type": "wat", "data": "ignored"},
        ],
        "metadata": None,
    }
    out = message_from_dict(payload)
    assert isinstance(out.content, list)
    assert out.content == ["ok"]


def test_missing_content_falls_back_to_empty_string():
    out = message_from_dict({"role": "assistant"})
    assert out.role == "assistant"
    assert out.content == ""


def test_missing_role_defaults_to_user():
    out = message_from_dict({"content": "hi"})
    assert out.role == "user"
    assert out.content == "hi"


def test_image_b64_part_without_data_is_skipped():
    payload = {
        "role": "user",
        "content": [{"type": "image_b64"}, {"type": "text", "text": "kept"}],
    }
    out = message_from_dict(payload)
    assert isinstance(out.content, list)
    assert out.content == ["kept"]


@pytest.mark.parametrize("role", ["user", "assistant", "system"])
def test_round_trip_preserves_role(role):
    msg = LLMMessage(role=role, content="x")  # type: ignore[arg-type]
    assert message_from_dict(message_to_dict(msg)).role == role


# ---------------------------------------------------------------------------
# Integration with FaraQwen3Agent.maybe_remove_old_screenshots
# ---------------------------------------------------------------------------


def _agent(max_n_images: int = 3) -> FaraQwen3Agent:
    """Construct an agent without initialize() — only the trim helpers are used."""
    cfg = FaraQwen3AgentConfig(
        client_config={"model": "x", "base_url": "http://localhost:0/v1"},
        max_n_images=max_n_images,
    )
    a = FaraQwen3Agent(cfg)
    a._state = FaraQwen3AgentState()
    return a


def _user_with_screenshot(text: str, color: str, **meta) -> LLMMessage:
    return LLMMessage(
        role="user",
        content=[_img(color), text],
        metadata=meta or None,
    )


def _build_long_history() -> list[LLMMessage]:
    """5 turns of [user(screenshot), assistant(text)] + a system header."""
    history: list[LLMMessage] = [
        LLMMessage(role="system", content="you are an agent"),
        _user_with_screenshot("first task", "red", is_original=True),
    ]
    for i in range(4):
        history.append(LLMMessage(role="assistant", content=f"step {i}"))
        history.append(_user_with_screenshot(f"obs {i}", "blue"))
    return history


def _count_images(history: list[LLMMessage]) -> int:
    n = 0
    for m in history:
        if isinstance(m.content, list):
            n += sum(1 for c in m.content if isinstance(c, ImageObj))
    return n


def test_trim_then_round_trip_preserves_image_count():
    agent = _agent(max_n_images=3)
    history = _build_long_history()
    assert _count_images(history) == 5  # before trim

    trimmed = agent.maybe_remove_old_screenshots(history, includes_current=True)
    assert _count_images(trimmed) == 3  # max_n_images cap

    encoded = [message_to_dict(m) for m in trimmed]
    decoded = [message_from_dict(d) for d in encoded]

    assert _count_images(decoded) == 3
    assert len(decoded) == len(trimmed)
    # Roles preserved in order
    assert [m.role for m in decoded] == [m.role for m in trimmed]


def test_trim_preserves_original_user_text_after_trim_and_round_trip():
    """Old user message marked is_original keeps its text even when image is trimmed."""
    agent = _agent(max_n_images=2)
    history = _build_long_history()  # is_original on the first user message

    trimmed = agent.maybe_remove_old_screenshots(history, includes_current=True)
    decoded = [message_from_dict(message_to_dict(m)) for m in trimmed]

    # Find the is_original message in the decoded history
    originals = [m for m in decoded if (m.metadata or {}).get("is_original") is True]
    assert originals, "is_original user message must survive trim+round-trip"
    msg = originals[0]
    # Image was stripped (it's old), but text remains
    assert isinstance(msg.content, list)
    assert all(not isinstance(c, ImageObj) for c in msg.content)
    assert "first task" in msg.content


def test_round_trip_then_trim_matches_trim_then_round_trip():
    """Order independence: trim and serialization commute for our test history."""
    agent = _agent(max_n_images=3)
    history = _build_long_history()

    a = agent.maybe_remove_old_screenshots(
        [message_from_dict(message_to_dict(m)) for m in history],
        includes_current=True,
    )
    b = [
        message_from_dict(message_to_dict(m))
        for m in agent.maybe_remove_old_screenshots(history, includes_current=True)
    ]

    assert _count_images(a) == _count_images(b) == 3
    assert [m.role for m in a] == [m.role for m in b]


def test_full_state_file_shape_and_size():
    """Encoded shape is JSON-serializable and structurally well-formed."""
    agent = _agent(max_n_images=3)
    trimmed = agent.maybe_remove_old_screenshots(
        _build_long_history(), includes_current=True
    )

    payload = {
        "last_url": "https://example.com/page",
        "scroll": [0, 1234],
        "chat_history": [message_to_dict(m) for m in trimmed],
        "facts": ["fact A", "fact B"],
    }
    blob = json.dumps(payload)
    parsed = json.loads(blob)

    assert parsed["last_url"] == "https://example.com/page"
    assert parsed["scroll"] == [0, 1234]
    assert isinstance(parsed["chat_history"], list)
    assert parsed["facts"] == ["fact A", "fact B"]

    restored = [message_from_dict(d) for d in parsed["chat_history"]]
    assert _count_images(restored) == 3
