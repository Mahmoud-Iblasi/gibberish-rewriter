"""Mirrors csharp/tests/GibberishRewriter.App.Tests/ClipboardServiceTests.cs and its ClipboardTestThreads.cs.

The round trip needs the real clipboard, so it runs only with GIBBERISH_INTEGRATION=1, exactly as the C#
[IntegrationFact] does; a normal run never touches what the user copied. Everything that can be decided without
Windows -- which formats are memory-backed, and how the text is encoded -- is an ordinary test.
"""

from __future__ import annotations

import ctypes
import os
import threading
import time

import pytest

from gibberish_rewriter.win import clipboard_service, win32
from gibberish_rewriter.win.clipboard_owner_window import ClipboardOwnerWindow
from gibberish_rewriter.win.clipboard_service import ClipboardService

INTEGRATION_VARIABLE = "GIBBERISH_INTEGRATION"
integration = pytest.mark.skipif(
    os.environ.get(INTEGRATION_VARIABLE) != "1",
    reason=f"Windows integration test. Set {INTEGRATION_VARIABLE}=1 to run it.",
)

TEST_TEXT = "Gibberish Rewriter clipboard test"
TEST_HTML = b"<b>Gibberish Rewriter</b>\0"


@pytest.mark.parametrize(
    ("clipboard_format", "expected"),
    [
        (13, True),  # CF_UNICODETEXT
        (8, True),  # CF_DIB
        (15, True),  # CF_HDROP (file lists)
        (0xC0F0, True),  # a registered format, such as "HTML Format"
        (2, False),  # CF_BITMAP
        (3, False),  # CF_METAFILEPICT
        (9, False),  # CF_PALETTE
        (14, False),  # CF_ENHMETAFILE
        (0x80, False),  # CF_OWNERDISPLAY
        (0x8E, False),  # CF_DSPENHMETAFILE
        (0x200, False),  # CF_PRIVATEFIRST
        (0x3FF, False),  # CF_GDIOBJLAST
    ],
)
def test_is_memory_format_skips_gdi_and_private_formats(clipboard_format, expected):
    assert ClipboardService.is_memory_format(clipboard_format) is expected


def test_clipboard_text_is_utf16_the_way_encoding_unicode_writes_it():
    """CF_UNICODETEXT is NUL-terminated UTF-16, and set_text appends the terminator itself."""
    assert clipboard_service._encode_utf16("ab\0") == b"a\x00b\x00\x00\x00"
    assert clipboard_service._decode_utf16(b"a\x00b\x00\x00\x00") == "ab\0"


def test_a_lone_surrogate_and_a_stray_byte_read_the_way_csharp_reads_them():
    """C#'s string keeps an unpaired surrogate, and Encoding.Unicode ignores a trailing half code unit."""
    assert clipboard_service._decode_utf16(b"\x00\xd8") == "\ud800"
    assert clipboard_service._decode_utf16(b"a\x00b") == "a"


def test_the_three_exclusion_formats_are_registered_and_distinct():
    """This app's own writes stay out of clipboard history and cloud sync."""
    service = ClipboardService(lambda: 0, lambda _message: None, lambda _ms: None)
    formats = service._exclusion_formats
    assert len(formats) == 3
    assert all(value != 0 for value in formats)
    assert len(set(formats)) == 3


@integration
def test_text_and_another_format_survive_save_set_text_and_restore():
    owner = OwnerThread()
    logged: list[str] = []
    service = ClipboardService(lambda: owner.handle, logged.append, _sleep_ms)
    users_clipboard = service.save()
    try:
        html = win32.RegisterClipboardFormat("HTML Format")
        _put_on_clipboard(
            owner.handle,
            [
                (win32.CF_UNICODETEXT, (TEST_TEXT + "\0").encode("utf-16-le")),
                (html, TEST_HTML),
            ],
        )
        saved = service.save()
        before = service.sequence()

        service.set_text("converted")
        assert service.read_text() == "converted"
        assert service.sequence() != before
        assert win32.IsClipboardFormatAvailable(
            win32.RegisterClipboardFormat("CanIncludeInClipboardHistory")
        )

        service.restore(saved)
        assert service.read_text() == TEST_TEXT
        assert _read_from_clipboard(owner.handle, html) == TEST_HTML
    finally:
        service.restore(users_clipboard)
        owner.close()


def _sleep_ms(milliseconds: int) -> None:
    time.sleep(milliseconds / 1000)


class OwnerThread:
    """A clipboard owner window on its own thread with a message loop, like the app's UI thread."""

    def __init__(self) -> None:
        self._ready = threading.Event()
        self._thread_id = 0
        self._window: ClipboardOwnerWindow | None = None
        self._thread = threading.Thread(target=self._run, name="ClipboardOwner", daemon=True)
        self._thread.start()
        self._ready.wait(5)

    @property
    def handle(self) -> int:
        assert self._window is not None, "the owner thread did not create its window."
        return self._window.handle

    def close(self) -> None:
        win32.PostThreadMessage(self._thread_id, win32.WM_QUIT, 0, 0)
        self._thread.join(5)

    def _run(self) -> None:
        self._thread_id = win32.GetCurrentThreadId()
        message = win32.MSG()
        # Creates the thread's message queue, so PostThreadMessage works from the first moment.
        win32.PeekMessage(ctypes.byref(message), None, win32.WM_USER, win32.WM_USER, win32.PM_NOREMOVE)
        self._window = ClipboardOwnerWindow()
        self._ready.set()
        while win32.GetMessage(ctypes.byref(message), None, 0, 0) > 0:
            pass
        self._window.close()


def _put_on_clipboard(owner: int, formats: list[tuple[int, bytes]]) -> None:
    """The other app's side of the test: the same Win32 sequence, written out rather than called through the
    service, so a bug in the service can't make the test set up what it then asserts."""
    assert win32.OpenClipboard(owner), "OpenClipboard failed while setting the test clipboard up."
    try:
        win32.EmptyClipboard()
        for clipboard_format, data in formats:
            handle = win32.GlobalAlloc(win32.GMEM_MOVEABLE, len(data))
            pointer = win32.GlobalLock(handle)
            ctypes.memmove(pointer, data, len(data))
            win32.GlobalUnlock(handle)
            assert win32.SetClipboardData(clipboard_format, handle), "SetClipboardData failed in the test."
    finally:
        win32.CloseClipboard()


def _read_from_clipboard(owner: int, clipboard_format: int) -> bytes | None:
    assert win32.OpenClipboard(owner), "OpenClipboard failed while reading the test clipboard."
    try:
        handle = win32.GetClipboardData(clipboard_format)
        if not handle:
            return None
        size = win32.GlobalSize(handle)
        pointer = win32.GlobalLock(handle)
        try:
            return ctypes.string_at(pointer, size)
        finally:
            win32.GlobalUnlock(handle)
    finally:
        win32.CloseClipboard()
