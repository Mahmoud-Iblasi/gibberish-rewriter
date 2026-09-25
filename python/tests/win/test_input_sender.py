"""win/input_sender.py against a stubbed SendInput. The C# has no InputSenderTests; a real SendInput would type
into whatever window has focus, so the Win32 call is replaced and everything around it is asserted for real."""

from __future__ import annotations

import pytest
from gibberish_rewriter.core.platform import Shortcut

from gibberish_rewriter.win import input_builder, input_sender, win32

SCAN_CODE = 0x1234
"""What the stubbed MapVirtualKey returns, so a filled-in scan code is unmistakable."""


class FakeSendInput:
    """Records each call the way SendInput sees it and reports how many events it accepted."""

    def __init__(self, accept: int | None = None) -> None:
        self.accept = accept
        self.calls: list[tuple[int, int, list[tuple[int, int, int, int]]]] = []

    def __call__(self, count, block, size):
        events = [
            (block[i].u.ki.wVk, block[i].u.ki.wScan, block[i].u.ki.dwFlags, block[i].u.ki.dwExtraInfo)
            for i in range(count)
        ]
        self.calls.append((count, size, events))
        return count if self.accept is None else self.accept


@pytest.fixture
def win32_stub(monkeypatch):
    """Replaces the two Win32 calls InputSender makes and records the map types it asked for."""
    map_types: list[tuple[int, int]] = []
    monkeypatch.setattr(
        win32, "MapVirtualKey", lambda vk, map_type: map_types.append((vk, map_type)) or SCAN_CODE
    )
    return map_types


def make() -> tuple[input_sender.InputSender, list[str]]:
    """A sender that logs into the list returned beside it."""
    lines: list[str] = []
    return input_sender.InputSender(lines.append), lines


def test_text_is_sent_in_chunks_of_fifty_with_the_right_cbsize(monkeypatch, win32_stub):
    fake = FakeSendInput()
    monkeypatch.setattr(win32, "SendInput", fake)
    sender, lines = make()
    sender.text("a" * 60)
    assert [count for count, _, _ in fake.calls] == [50, 50, 20]
    assert {size for _, size, _ in fake.calls} == {win32.INPUT_SIZE}
    assert lines == []


def test_unicode_events_keep_their_code_unit(monkeypatch, win32_stub):
    fake = FakeSendInput()
    monkeypatch.setattr(win32, "SendInput", fake)
    sender, _ = make()
    sender.text("ab")
    (_, _, events), = fake.calls
    assert [scan for _, scan, _, _ in events] == [ord("a"), ord("a"), ord("b"), ord("b")]
    assert win32_stub == []


def test_virtual_key_events_get_their_scan_code(monkeypatch, win32_stub):
    fake = FakeSendInput()
    monkeypatch.setattr(win32, "SendInput", fake)
    sender, _ = make()
    sender.backspaces(2)
    (_, _, events), = fake.calls
    assert events == [(input_builder.VK_BACK, SCAN_CODE, 0, 0x47525752),
                      (input_builder.VK_BACK, SCAN_CODE, win32.KEYEVENTF_KEYUP, 0x47525752)] * 2
    assert win32_stub == [(input_builder.VK_BACK, win32.MAPVK_VK_TO_VSC)] * 4


def test_the_scan_code_lookup_keeps_the_extended_flag(monkeypatch, win32_stub):
    fake = FakeSendInput()
    monkeypatch.setattr(win32, "SendInput", fake)
    sender, _ = make()
    sender.win_space()
    (_, _, events), = fake.calls
    assert [flags for _, _, flags, _ in events] == [
        win32.KEYEVENTF_EXTENDEDKEY,
        0,
        win32.KEYEVENTF_KEYUP,
        win32.KEYEVENTF_KEYUP | win32.KEYEVENTF_EXTENDEDKEY,
    ]


def test_a_short_send_is_logged(monkeypatch, win32_stub):
    monkeypatch.setattr(win32, "SendInput", FakeSendInput(accept=1))
    sender, lines = make()
    sender.key_press(0xE8)
    assert len(lines) == 1
    assert lines[0].startswith("SendInput sent 1 of 2 events (error ")


def test_every_public_call_reaches_sendinput(monkeypatch, win32_stub):
    fake = FakeSendInput()
    monkeypatch.setattr(win32, "SendInput", fake)
    sender, lines = make()
    sender.key_press(0x14)
    sender.backspaces(1)
    sender.text("x")
    sender.shortcut(Shortcut.PASTE, console=True)
    sender.win_space()
    assert [count for count, _, _ in fake.calls] == [2, 2, 2, 4, 4]
    assert lines == []
    for _, _, events in fake.calls:
        assert all(extra == 0x47525752 for _, _, _, extra in events)
