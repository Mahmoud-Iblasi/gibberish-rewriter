"""Mirrors the HookWatchdogTests class in csharp/tests/GibberishRewriter.App.Tests/HookTests.cs, and adds the
checks the C# leaves to the running app: what Check does with a stale reading and with a failing one."""

from __future__ import annotations

import pytest

from gibberish_rewriter.win import hook_watchdog
from gibberish_rewriter.win.hook_watchdog import HookActivity, HookWatchdog


@pytest.mark.parametrize(
    ("last_input", "last_hook", "blocked", "expected"),
    [
        (12_001, 10_000, False, True),
        (12_000, 10_000, False, False),
        (12_001, 10_000, True, False),
        (10_000, 12_001, False, False),
        (0x0000_0800, 0xFFFF_FF00, False, True),
    ],
)
def test_is_stale_needs_input_more_than_2_s_after_the_last_hook_event(
    last_input, last_hook, blocked, expected
):
    assert hook_watchdog.is_stale(last_input, last_hook, blocked) is expected


def test_is_stale_treats_a_gap_of_half_the_range_as_a_wrapped_clock():
    """The tick count wraps after 49.7 days, so half the range apart means the reading went backwards."""
    assert hook_watchdog.is_stale(0x7FFF_FFFF, 0, False)
    assert not hook_watchdog.is_stale(0x8000_0000, 0, False)


def test_hook_activity_starts_at_zero_and_keeps_times_above_int_maxvalue():
    activity = HookActivity()
    assert activity.last_event_time == 0
    activity.note(0xFFFF_FF00)
    assert activity.last_event_time == 0xFFFF_FF00


def test_hook_activity_keeps_only_the_low_32_bits():
    """The C# field is an int written with an unchecked cast, so a wider value wraps rather than growing."""
    activity = HookActivity()
    activity.note(0x1_0000_0005)
    assert activity.last_event_time == 5


def test_the_interval_and_the_stale_window_are_the_numbers_the_spec_names():
    assert hook_watchdog.INTERVAL_MS == 5000
    assert hook_watchdog.STALE_AFTER_MS == 2000


def test_last_input_time_reads_a_tick_count_from_windows():
    """A read-only call: GetLastInputInfo changes nothing, so it needs no desktop and no integration flag."""
    time = hook_watchdog.last_input_time()
    assert time is not None
    assert 0 <= time <= 0xFFFF_FFFF


def make(monkeypatch, last_input, last_hook, blocked=False):
    """A watchdog whose clock is fixed, with the lists its reinstall and log write into."""
    monkeypatch.setattr(hook_watchdog, "last_input_time", lambda: last_input)
    activity = HookActivity()
    activity.note(last_hook)
    reinstalls: list[int] = []
    lines: list[str] = []
    watchdog = HookWatchdog(activity, lambda: blocked, lambda: reinstalls.append(1), lines.append)
    return watchdog, activity, reinstalls, lines


def test_a_stale_reading_reinstalls_the_hooks_and_says_so(monkeypatch):
    watchdog, activity, reinstalls, lines = make(monkeypatch, 12_001, 10_000)
    try:
        watchdog._check()
    finally:
        watchdog.close()
    assert reinstalls == [1]
    assert lines == ["The hooks missed input for 2001 ms (foreground: unknown); reinstalling them"]
    assert activity.last_event_time == 12_001, "the reading is noted so the next check starts fresh"


def test_a_fresh_reading_does_nothing(monkeypatch):
    watchdog, _, reinstalls, lines = make(monkeypatch, 10_500, 10_000)
    try:
        watchdog._check()
    finally:
        watchdog.close()
    assert reinstalls == []
    assert lines == []


def test_an_elevated_foreground_window_is_never_stale(monkeypatch):
    """Windows doesn't pass that window's input to the hooks, so the gap means nothing."""
    watchdog, _, reinstalls, lines = make(monkeypatch, 12_001, 10_000, blocked=True)
    try:
        watchdog._check()
    finally:
        watchdog.close()
    assert reinstalls == []
    assert lines == []


def test_a_failed_getlastinputinfo_does_nothing(monkeypatch):
    monkeypatch.setattr(hook_watchdog, "last_input_time", lambda: None)
    activity = HookActivity()
    reinstalls: list[int] = []
    lines: list[str] = []
    watchdog = HookWatchdog(activity, lambda: False, lambda: reinstalls.append(1), lines.append)
    try:
        watchdog._check()
    finally:
        watchdog.close()
    assert reinstalls == []
    assert lines == []


def test_an_error_in_the_check_is_logged_and_the_watchdog_lives_on(monkeypatch):
    monkeypatch.setattr(hook_watchdog, "last_input_time", lambda: 12_001)
    activity = HookActivity()
    lines: list[str] = []

    def boom() -> None:
        raise OSError("hook thread gone")

    watchdog = HookWatchdog(activity, lambda: False, boom, lines.append)
    try:
        watchdog._check()
        assert watchdog._thread.is_alive(), "the error stayed inside the check"
        # The first check noted 12_001, so the second sees a gap of 0 and has nothing to say.
        watchdog._check()
    finally:
        watchdog.close()
    assert lines == [
        "The hooks missed input for 12001 ms (foreground: unknown); reinstalling them",
        "Hook watchdog error: OSError",
    ]


def test_close_stops_the_checking_thread(monkeypatch):
    watchdog, _, reinstalls, _ = make(monkeypatch, 10_000, 10_000)
    assert watchdog._thread.is_alive()
    watchdog.close()
    assert not watchdog._thread.is_alive()
    assert reinstalls == []


def test_the_watchdog_can_be_used_as_a_context_manager(monkeypatch):
    monkeypatch.setattr(hook_watchdog, "last_input_time", lambda: 0)
    with HookWatchdog(HookActivity(), lambda: False, lambda: None, lambda _: None) as watchdog:
        assert watchdog._thread.is_alive()
    assert not watchdog._thread.is_alive()
