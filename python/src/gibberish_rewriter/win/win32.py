"""The Win32 declarations the platform modules use, as ctypes.

Mirrors ``csharp/src/GibberishRewriter.App/Win/NativeMethods.cs`` declaration for declaration and keeps the C# names,
so the two files can be read side by side. Widths and layouts must match the C# exactly: ``SendInput`` rejects any
``cbSize`` other than ``sizeof(INPUT)``, which is 40 bytes on x64 and 28 on x86.

Every entry point is bound with explicit ``argtypes`` and ``restype``. Without a ``restype`` ctypes assumes ``int``
and silently truncates the top 32 bits of every handle a function returns.

Where the C# says ``CharSet = CharSet.Unicode`` the Unicode export is bound here (``GetClassNameW``,
``RegisterClipboardFormatW``, ``GetModuleHandleW``, and the UTF-16 buffer ``ToUnicodeEx`` fills). The C# marshaller
picks the ``A`` export for the declarations that leave ``CharSet`` at its default; the Unicode export is bound for
those too, because none of them passes text and the hook thread's loop uses ``GetMessageW``.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from typing import Any

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)

ULONG_PTR = wintypes.WPARAM
"""C#'s ``UIntPtr``: pointer-sized and unsigned, 8 bytes on x64."""

LRESULT = wintypes.LPARAM
"""What a hook procedure returns; C# declares it ``IntPtr``."""


def _bind(library: ctypes.WinDLL, export: str, restype: Any, argtypes: list[Any]) -> Any:
    """Binds one export with its signature. The name assigned to on the left is the C# name."""
    function = getattr(library, export)
    function.restype = restype
    function.argtypes = argtypes
    return function


# ---- Hooks and messages ----
WH_KEYBOARD_LL = 13
WH_MOUSE_LL = 14
HC_ACTION = 0
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_LBUTTONDOWN = 0x0201
WM_RBUTTONDOWN = 0x0204
WM_MBUTTONDOWN = 0x0207
WM_XBUTTONDOWN = 0x020B
WM_QUIT = 0x0012
WM_APP = 0x8000
WM_INPUTLANGCHANGEREQUEST = 0x0050
LLKHF_INJECTED = 0x10

LowLevelHookProc = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
"""``nCode``, ``wParam``, ``lParam``. C# declares both parameters ``IntPtr``; ``wParam`` is unsigned here so a
message id compares directly against ``WM_KEYDOWN`` and friends. The bit patterns are identical."""


class KBDLLHOOKSTRUCT(ctypes.Structure):
    """24 bytes on x64."""

    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class MSLLHOOKSTRUCT(ctypes.Structure):
    """32 bytes on x64: four bytes of padding sit before ``dwExtraInfo``."""

    _fields_ = [
        ("pt", POINT),
        ("mouseData", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class MSG(ctypes.Structure):
    """48 bytes on x64. Declared here rather than taken from ``ctypes.wintypes`` because the C# carries
    ``lPrivate``, the undocumented trailing field of the real ``MSG``."""

    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", POINT),
        ("lPrivate", wintypes.DWORD),
    ]


SetWindowsHookEx = _bind(
    user32,
    "SetWindowsHookExW",
    wintypes.HHOOK,
    [ctypes.c_int, LowLevelHookProc, wintypes.HMODULE, wintypes.DWORD],
)

UnhookWindowsHookEx = _bind(user32, "UnhookWindowsHookEx", wintypes.BOOL, [wintypes.HHOOK])

CallNextHookEx = _bind(
    user32,
    "CallNextHookEx",
    LRESULT,
    [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM],
)

GetMessage = _bind(
    user32,
    "GetMessageW",
    ctypes.c_int,
    [ctypes.POINTER(MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT],
)

WM_USER = 0x0400
PM_NOREMOVE = 0x0000

PeekMessage = _bind(
    user32,
    "PeekMessageW",
    wintypes.BOOL,
    [ctypes.POINTER(MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT],
)

PostThreadMessage = _bind(
    user32,
    "PostThreadMessageW",
    wintypes.BOOL,
    [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM],
)

PostMessage = _bind(
    user32,
    "PostMessageW",
    wintypes.BOOL,
    [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM],
)

GetCurrentThreadId = _bind(kernel32, "GetCurrentThreadId", wintypes.DWORD, [])

GetModuleHandle = _bind(kernel32, "GetModuleHandleW", wintypes.HMODULE, [wintypes.LPCWSTR])

# ---- Keys, windows and layouts ----
MAPVK_VK_TO_VSC = 0
MAPVK_VK_TO_VSC_EX = 4

GetAsyncKeyState = _bind(user32, "GetAsyncKeyState", ctypes.c_short, [ctypes.c_int])

GetKeyState = _bind(user32, "GetKeyState", ctypes.c_short, [ctypes.c_int])

GetForegroundWindow = _bind(user32, "GetForegroundWindow", wintypes.HWND, [])

GetWindowThreadProcessId = _bind(
    user32,
    "GetWindowThreadProcessId",
    wintypes.DWORD,
    [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)],
)

GetKeyboardLayout = _bind(user32, "GetKeyboardLayout", wintypes.HKL, [wintypes.DWORD])

GetKeyboardLayoutList = _bind(
    user32, "GetKeyboardLayoutList", ctypes.c_int, [ctypes.c_int, ctypes.POINTER(wintypes.HKL)]
)

GetClassName = _bind(
    user32, "GetClassNameW", ctypes.c_int, [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
)

MapVirtualKey = _bind(user32, "MapVirtualKeyW", wintypes.UINT, [wintypes.UINT, wintypes.UINT])

MapVirtualKeyEx = _bind(
    user32, "MapVirtualKeyExW", wintypes.UINT, [wintypes.UINT, wintypes.UINT, wintypes.HKL]
)

ToUnicodeEx = _bind(
    user32,
    "ToUnicodeEx",
    ctypes.c_int,
    [
        wintypes.UINT,
        wintypes.UINT,
        ctypes.POINTER(ctypes.c_ubyte),
        wintypes.LPWSTR,
        ctypes.c_int,
        wintypes.UINT,
        wintypes.HKL,
    ],
)
"""``lpKeyState`` is a 256-byte array and ``pwszBuff`` a UTF-16 buffer of ``cchBuff`` units. The C# marks this
declaration ``CharSet = CharSet.Unicode`` so its ``char[]`` marshals as UTF-16 rather than ANSI;
``ctypes.create_unicode_buffer`` is the same thing here, and ``ToUnicodeEx`` has no ANSI export to confuse it with."""

KEY_STATE_SIZE = 256
"""Length of the ``lpKeyState`` array ``ToUnicodeEx`` reads; the C# passes a ``byte[]`` of this size."""


def key_state_buffer() -> ctypes.Array[ctypes.c_ubyte]:
    """A zeroed 256-byte key state array for ToUnicodeEx."""
    return (ctypes.c_ubyte * KEY_STATE_SIZE)()


# ---- SendInput ----
INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004


class KEYBDINPUT(ctypes.Structure):
    """24 bytes on x64: ``dwExtraInfo`` is pointer-aligned at offset 16."""

    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class MOUSEINPUT(ctypes.Structure):
    """32 bytes on x64, the largest member of the union."""

    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class InputUnion(ctypes.Union):
    """The INPUT union. MOUSEINPUT is the largest member, so it sets the size (40 bytes for INPUT on x64)."""

    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", InputUnion)]


SendInput = _bind(
    user32, "SendInput", wintypes.UINT, [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
)

INPUT_SIZE = ctypes.sizeof(INPUT)
"""``cbSize`` for every SendInput call; the C# reads it from ``Marshal.SizeOf<INPUT>()``."""

# ---- Clipboard ----
CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002

OpenClipboard = _bind(user32, "OpenClipboard", wintypes.BOOL, [wintypes.HWND])

CloseClipboard = _bind(user32, "CloseClipboard", wintypes.BOOL, [])

EmptyClipboard = _bind(user32, "EmptyClipboard", wintypes.BOOL, [])

EnumClipboardFormats = _bind(user32, "EnumClipboardFormats", wintypes.UINT, [wintypes.UINT])

GetClipboardData = _bind(user32, "GetClipboardData", wintypes.HANDLE, [wintypes.UINT])

SetClipboardData = _bind(user32, "SetClipboardData", wintypes.HANDLE, [wintypes.UINT, wintypes.HANDLE])

IsClipboardFormatAvailable = _bind(user32, "IsClipboardFormatAvailable", wintypes.BOOL, [wintypes.UINT])

RegisterClipboardFormat = _bind(user32, "RegisterClipboardFormatW", wintypes.UINT, [wintypes.LPCWSTR])

GetClipboardSequenceNumber = _bind(user32, "GetClipboardSequenceNumber", wintypes.DWORD, [])

GlobalAlloc = _bind(kernel32, "GlobalAlloc", wintypes.HGLOBAL, [wintypes.UINT, ctypes.c_size_t])

GlobalLock = _bind(kernel32, "GlobalLock", wintypes.LPVOID, [wintypes.HGLOBAL])

GlobalUnlock = _bind(kernel32, "GlobalUnlock", wintypes.BOOL, [wintypes.HGLOBAL])

GlobalSize = _bind(kernel32, "GlobalSize", ctypes.c_size_t, [wintypes.HGLOBAL])

GlobalFree = _bind(kernel32, "GlobalFree", wintypes.HGLOBAL, [wintypes.HGLOBAL])

# ---- Idle time and elevation ----
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
TOKEN_QUERY = 0x0008
TokenElevation = 20


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


GetLastInputInfo = _bind(user32, "GetLastInputInfo", wintypes.BOOL, [ctypes.POINTER(LASTINPUTINFO)])

# ---- The start notification ----
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
QUNS_ACCEPTS_NOTIFICATIONS = 5

FindWindow = _bind(user32, "FindWindowW", wintypes.HWND, [wintypes.LPCWSTR, wintypes.LPCWSTR])
SHQueryUserNotificationState = _bind(shell32, "SHQueryUserNotificationState", ctypes.c_long, [ctypes.POINTER(ctypes.c_int)])

OpenProcess = _bind(
    kernel32, "OpenProcess", wintypes.HANDLE, [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
)

CloseHandle = _bind(kernel32, "CloseHandle", wintypes.BOOL, [wintypes.HANDLE])

OpenProcessToken = _bind(
    advapi32,
    "OpenProcessToken",
    wintypes.BOOL,
    [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)],
)

GetTokenInformation = _bind(
    advapi32,
    "GetTokenInformation",
    wintypes.BOOL,
    [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.POINTER(wintypes.DWORD),
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ],
)
