"""Mirrors csharp/tests/GibberishRewriter.App.Tests/StartNoticeTests.cs."""

import os

import pytest

from gibberish_rewriter.win import start_notice

ACCEPTS = 5
BUSY = 2


def test_shows_at_once_when_the_taskbar_exists_and_windows_accepts_notifications():
    assert start_notice.should_show(True, ACCEPTS, 0)


@pytest.mark.parametrize(("taskbar_exists", "state"), [(False, ACCEPTS), (True, BUSY), (True, 0)])
def test_waits_while_the_taskbar_is_missing_or_windows_holds_notifications_back(taskbar_exists, state):
    waited = start_notice.MAX_WAIT_MS - start_notice.POLL_INTERVAL_MS
    assert not start_notice.should_show(taskbar_exists, state, waited)


def test_shows_anyway_once_the_longest_wait_has_passed():
    assert start_notice.should_show(False, BUSY, start_notice.MAX_WAIT_MS)


@pytest.mark.skipif(
    os.environ.get("GIBBERISH_INTEGRATION") != "1",
    reason="Windows integration test. Set GIBBERISH_INTEGRATION=1 to run it.",
)
def test_windows_reports_the_taskbar_and_a_notification_state_on_this_desktop():
    assert start_notice.taskbar_exists()
    assert 1 <= start_notice.notification_state() <= 7
