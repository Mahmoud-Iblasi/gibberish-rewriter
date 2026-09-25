"""Layouts and bindings in win/win32.py. Mirrors the size assertion in InputBuilderTests.cs and adds the offsets
every downstream module depends on."""

from __future__ import annotations

import ctypes
import threading

import pytest

from gibberish_rewriter.win import win32

POINTER_SIZE = ctypes.sizeof(ctypes.c_void_p)
IS_64_BIT = POINTER_SIZE == 8

needs_64_bit = pytest.mark.skipif(not IS_64_BIT, reason="The offsets below are the x64 ones.")


def test_input_has_the_size_sendinput_expects():
    assert ctypes.sizeof(win32.INPUT) == (40 if IS_64_BIT else 28)
    assert win32.INPUT_SIZE == ctypes.sizeof(win32.INPUT)


def test_mouseinput_sets_the_size_of_the_union():
    assert ctypes.sizeof(win32.InputUnion) == ctypes.sizeof(win32.MOUSEINPUT)
    assert ctypes.sizeof(win32.MOUSEINPUT) > ctypes.sizeof(win32.KEYBDINPUT)
    assert win32.InputUnion.mi.offset == 0
    assert win32.InputUnion.ki.offset == 0


@needs_64_bit
@pytest.mark.parametrize(
    ("structure", "size"),
    [
        (win32.POINT, 8),
        (win32.KBDLLHOOKSTRUCT, 24),
        (win32.MSLLHOOKSTRUCT, 32),
        (win32.MSG, 48),
        (win32.KEYBDINPUT, 24),
        (win32.MOUSEINPUT, 32),
        (win32.InputUnion, 32),
        (win32.INPUT, 40),
        (win32.LASTINPUTINFO, 8),
    ],
)
def test_structures_have_the_sizes_the_c_sharp_has(structure, size):
    assert ctypes.sizeof(structure) == size


@needs_64_bit
@pytest.mark.parametrize(
    ("structure", "field", "offset"),
    [
        (win32.INPUT, "type", 0),
        (win32.INPUT, "u", 8),
        (win32.KEYBDINPUT, "wVk", 0),
        (win32.KEYBDINPUT, "wScan", 2),
        (win32.KEYBDINPUT, "dwFlags", 4),
        (win32.KEYBDINPUT, "time", 8),
        (win32.KEYBDINPUT, "dwExtraInfo", 16),
        (win32.MOUSEINPUT, "dwExtraInfo", 24),
        (win32.KBDLLHOOKSTRUCT, "dwExtraInfo", 16),
        (win32.MSLLHOOKSTRUCT, "dwExtraInfo", 24),
        (win32.MSG, "hwnd", 0),
        (win32.MSG, "message", 8),
        (win32.MSG, "wParam", 16),
        (win32.MSG, "lParam", 24),
        (win32.MSG, "time", 32),
        (win32.MSG, "pt", 36),
        (win32.MSG, "lPrivate", 44),
    ],
)
def test_fields_sit_where_the_c_sharp_puts_them(structure, field, offset):
    assert getattr(structure, field).offset == offset


def test_extra_info_is_pointer_sized_and_unsigned():
    assert ctypes.sizeof(win32.ULONG_PTR) == POINTER_SIZE
    marker = win32.KEYBDINPUT(dwExtraInfo=0x47525752)
    assert marker.dwExtraInfo == 0x47525752
    widest = win32.KEYBDINPUT(dwExtraInfo=(1 << (POINTER_SIZE * 8)) - 1)
    assert widest.dwExtraInfo == (1 << (POINTER_SIZE * 8)) - 1


def test_field_widths_match_the_c_sharp_types():
    assert win32.KEYBDINPUT.wVk.size == 2
    assert win32.KEYBDINPUT.wScan.size == 2
    assert win32.KEYBDINPUT.dwFlags.size == 4
    assert win32.KBDLLHOOKSTRUCT.vkCode.size == 4
    assert win32.MSLLHOOKSTRUCT.mouseData.size == 4
    assert win32.POINT.x.size == 4


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("WH_KEYBOARD_LL", 13),
        ("WH_MOUSE_LL", 14),
        ("HC_ACTION", 0),
        ("WM_KEYDOWN", 0x0100),
        ("WM_KEYUP", 0x0101),
        ("WM_SYSKEYDOWN", 0x0104),
        ("WM_SYSKEYUP", 0x0105),
        ("WM_LBUTTONDOWN", 0x0201),
        ("WM_RBUTTONDOWN", 0x0204),
        ("WM_MBUTTONDOWN", 0x0207),
        ("WM_XBUTTONDOWN", 0x020B),
        ("WM_QUIT", 0x0012),
        ("WM_APP", 0x8000),
        ("WM_USER", 0x0400),
        ("WM_INPUTLANGCHANGEREQUEST", 0x0050),
        ("LLKHF_INJECTED", 0x10),
        ("PM_NOREMOVE", 0x0000),
        ("MAPVK_VK_TO_VSC", 0),
        ("MAPVK_VK_TO_VSC_EX", 4),
        ("INPUT_KEYBOARD", 1),
        ("KEYEVENTF_EXTENDEDKEY", 0x0001),
        ("KEYEVENTF_KEYUP", 0x0002),
        ("KEYEVENTF_UNICODE", 0x0004),
        ("CF_UNICODETEXT", 13),
        ("GMEM_MOVEABLE", 0x0002),
        ("PROCESS_QUERY_LIMITED_INFORMATION", 0x1000),
        ("TOKEN_QUERY", 0x0008),
        ("TokenElevation", 20),
        ("KEY_STATE_SIZE", 256),
    ],
)
def test_constants_match_nativemethods_cs(name, value):
    assert getattr(win32, name) == value


def _bound_functions():
    return {
        name: value
        for name, value in vars(win32).items()
        if not isinstance(value, type) and hasattr(value, "restype") and hasattr(value, "argtypes")
    }


def test_every_declaration_in_nativemethods_cs_is_bound():
    expected = {
        "SetWindowsHookEx", "UnhookWindowsHookEx", "CallNextHookEx", "GetMessage", "PeekMessage",
        "PostThreadMessage", "PostMessage", "GetCurrentThreadId", "GetModuleHandle",
        "GetAsyncKeyState", "GetKeyState", "GetForegroundWindow", "GetWindowThreadProcessId",
        "GetKeyboardLayout", "GetKeyboardLayoutList", "GetClassName", "MapVirtualKey",
        "MapVirtualKeyEx", "ToUnicodeEx", "SendInput", "OpenClipboard", "CloseClipboard",
        "EmptyClipboard", "EnumClipboardFormats", "GetClipboardData", "SetClipboardData",
        "IsClipboardFormatAvailable", "RegisterClipboardFormat", "GetClipboardSequenceNumber",
        "GlobalAlloc", "GlobalLock", "GlobalUnlock", "GlobalSize", "GlobalFree",
        "GetLastInputInfo", "OpenProcess", "CloseHandle", "OpenProcessToken", "GetTokenInformation",
    }
    assert expected <= set(_bound_functions())


@pytest.mark.parametrize("name", sorted(_bound_functions()))
def test_every_binding_declares_its_signature(name):
    function = getattr(win32, name)
    assert function.restype is not None, "a missing restype truncates 64-bit handles to 32 bits"
    assert function.argtypes is not None


@pytest.mark.parametrize(
    "name",
    [
        "SetWindowsHookEx", "CallNextHookEx", "GetForegroundWindow", "GetKeyboardLayout",
        "GetModuleHandle", "GetClipboardData", "SetClipboardData", "GlobalAlloc", "GlobalLock",
        "GlobalFree", "OpenProcess", "GlobalSize",
    ],
)
def test_handle_returning_bindings_are_pointer_sized(name):
    assert ctypes.sizeof(getattr(win32, name).restype) == POINTER_SIZE


def test_sendinput_takes_an_input_array_and_a_byte_count():
    assert win32.SendInput.argtypes[1] == ctypes.POINTER(win32.INPUT)
    assert len(win32.SendInput.argtypes) == 3


def test_tounicodeex_fills_a_utf16_buffer():
    from ctypes import wintypes

    assert win32.ToUnicodeEx.argtypes[3] is wintypes.LPWSTR
    buffer = ctypes.create_unicode_buffer(8)
    assert ctypes.sizeof(buffer) == 8 * ctypes.sizeof(ctypes.c_wchar) == 16
    assert len(win32.key_state_buffer()) == 256
    assert set(win32.key_state_buffer()) == {0}


def test_the_bindings_reach_windows():
    """Read-only calls: they change nothing, so they need no desktop and no integration flag."""
    assert win32.GetModuleHandle(None)
    assert win32.GetCurrentThreadId() == threading.get_native_id()
    assert win32.MapVirtualKey(0x08, win32.MAPVK_VK_TO_VSC) == 0x0E
