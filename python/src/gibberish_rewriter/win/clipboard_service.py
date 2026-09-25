"""Saves, reads, writes and restores the clipboard. Called on the action thread; the owner window lives on the UI thread.

Mirrors ``csharp/src/GibberishRewriter.App/Win/ClipboardService.cs``.
"""

from __future__ import annotations

import contextlib
import ctypes
from collections.abc import Callable, Iterator
from dataclasses import dataclass

from gibberish_rewriter.core.platform import ClipboardUnavailableError

from gibberish_rewriter.win import win32

OPEN_ATTEMPTS = 10
OPEN_RETRY_MS = 20

_GDI_FORMATS = frozenset({2, 3, 9, 14, 0x80, 0x82, 0x83, 0x8E})
"""CF_BITMAP, CF_METAFILEPICT, CF_PALETTE, CF_ENHMETAFILE, CF_OWNERDISPLAY, CF_DSPBITMAP, CF_DSPMETAFILEPICT,
CF_DSPENHMETAFILE: their data is a GDI handle, not memory."""

_EXCLUSION_FORMAT_NAMES = (
    "ExcludeClipboardContentFromMonitorProcessing",
    "CanIncludeInClipboardHistory",
    "CanUploadToCloudClipboard",
)
"""Keeps this app's writes out of clipboard history and cloud sync."""

_INT_MAX = 0x7FFFFFFF


@dataclass(frozen=True)
class SavedClipboard:
    """Every memory-backed format the clipboard held, in EnumClipboardFormats order."""

    formats: tuple[tuple[int, bytes], ...] = ()


class ClipboardService:
    """Saves, restores, reads and writes the clipboard, retrying while another app holds it."""

    OPEN_ATTEMPTS = OPEN_ATTEMPTS
    OPEN_RETRY_MS = OPEN_RETRY_MS

    def __init__(
        self,
        owner: Callable[[], int],
        log: Callable[[str], None],
        sleep: Callable[[int], None],
    ) -> None:
        self._owner = owner
        self._log = log
        self._sleep = sleep
        self._exclusion_formats = tuple(
            win32.RegisterClipboardFormat(name) for name in _EXCLUSION_FORMAT_NAMES
        )

    @staticmethod
    def is_memory_format(clipboard_format: int) -> bool:
        """False for GDI formats and CF_PRIVATEFIRST-CF_GDIOBJLAST, whose data can't be copied as memory."""
        return clipboard_format not in _GDI_FORMATS and not 0x200 <= clipboard_format <= 0x3FF

    def sequence(self) -> int:
        return win32.GetClipboardSequenceNumber()

    def save(self) -> object:
        formats: list[tuple[int, bytes]] = []
        with self._open():
            clipboard_format = win32.EnumClipboardFormats(0)
            while clipboard_format != 0:
                if not ClipboardService.is_memory_format(clipboard_format):
                    self._log(f"Clipboard format {clipboard_format} is not saved (GDI or private data)")
                else:
                    data = _read_bytes(clipboard_format)
                    if data is not None:
                        formats.append((clipboard_format, data))
                clipboard_format = win32.EnumClipboardFormats(clipboard_format)
        return SavedClipboard(tuple(formats))

    def restore(self, saved: object) -> None:
        assert isinstance(saved, SavedClipboard), "restore takes what save returned."
        with self._open():
            win32.EmptyClipboard()
            if not saved.formats:
                return
            for clipboard_format, data in saved.formats:
                self._write_bytes(clipboard_format, data)
            self._write_exclusion_markers()

    def read_text(self) -> str | None:
        with self._open():
            data = _read_bytes(win32.CF_UNICODETEXT)
            if data is None:
                return None
            text = _decode_utf16(data)
            end = text.find("\0")
            return text[:end] if end >= 0 else text

    def set_text(self, text: str) -> None:
        with self._open():
            win32.EmptyClipboard()
            if not self._write_bytes(win32.CF_UNICODETEXT, _encode_utf16(text + "\0")):
                raise ClipboardUnavailableError("SetClipboardData failed for the converted text.")
            self._write_exclusion_markers()

    @contextlib.contextmanager
    def _open(self) -> Iterator[None]:
        """OpenClipboard, retried OPEN_ATTEMPTS times OPEN_RETRY_MS apart, and always closed again."""
        attempt = 1
        while not win32.OpenClipboard(self._owner()):
            if attempt == OPEN_ATTEMPTS:
                raise ClipboardUnavailableError(
                    f"OpenClipboard failed {OPEN_ATTEMPTS} times (error {ctypes.get_last_error()})."
                )
            self._sleep(OPEN_RETRY_MS)
            attempt += 1
        try:
            yield
        finally:
            win32.CloseClipboard()

    def _write_bytes(self, clipboard_format: int, data: bytes) -> bool:
        """Copies the bytes into a new global block and hands it to the clipboard. False if that failed."""
        handle = win32.GlobalAlloc(win32.GMEM_MOVEABLE, max(len(data), 1))
        pointer = win32.GlobalLock(handle) if handle else None
        if not pointer:
            if handle:
                win32.GlobalFree(handle)
            self._log(f"Couldn't allocate {len(data)} bytes for clipboard format {clipboard_format}")
            return False
        if data:
            ctypes.memmove(pointer, data, len(data))
        win32.GlobalUnlock(handle)
        if not win32.SetClipboardData(clipboard_format, handle):
            win32.GlobalFree(handle)
            self._log(
                f"SetClipboardData failed for format {clipboard_format} (error {ctypes.get_last_error()})"
            )
            return False
        return True

    def _write_exclusion_markers(self) -> None:
        for clipboard_format in self._exclusion_formats:
            self._write_bytes(clipboard_format, (0).to_bytes(4, "little"))


def _read_bytes(clipboard_format: int) -> bytes | None:
    handle = win32.GetClipboardData(clipboard_format)
    if not handle:
        return None
    size = win32.GlobalSize(handle)
    pointer = win32.GlobalLock(handle)
    if not pointer:
        return None
    try:
        return None if size > _INT_MAX else ctypes.string_at(pointer, size)
    finally:
        win32.GlobalUnlock(handle)


def _decode_utf16(data: bytes) -> str:
    """UTF-16 as C#'s Encoding.Unicode reads it: a lone surrogate is kept, a trailing odd byte is dropped."""
    return data[: len(data) - len(data) % 2].decode("utf-16-le", "surrogatepass")


def _encode_utf16(text: str) -> bytes:
    return text.encode("utf-16-le", "surrogatepass")
