from __future__ import annotations

import ctypes
import os
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtGui import QImage

from pdfbread.paths import app_root

NDI_FOURCC_BGRA = ord("B") | (ord("G") << 8) | (ord("R") << 16) | (ord("A") << 24)
NDI_FRAME_FORMAT_PROGRESSIVE = 0


class NDIlib_send_create_t(ctypes.Structure):
    _fields_ = [
        ("p_ndi_name", ctypes.c_char_p),
        ("p_groups", ctypes.c_char_p),
        ("clock_video", ctypes.c_bool),
        ("clock_audio", ctypes.c_bool),
    ]


class NDIlib_video_frame_v2_t(ctypes.Structure):
    _fields_ = [
        ("xres", ctypes.c_int),
        ("yres", ctypes.c_int),
        ("FourCC", ctypes.c_int),
        ("frame_rate_N", ctypes.c_int),
        ("frame_rate_D", ctypes.c_int),
        ("picture_aspect_ratio", ctypes.c_float),
        ("frame_format_type", ctypes.c_int),
        ("timecode", ctypes.c_longlong),
        ("p_data", ctypes.POINTER(ctypes.c_uint8)),
        ("line_stride_in_bytes", ctypes.c_int),
        ("p_metadata", ctypes.c_char_p),
        ("timestamp", ctypes.c_longlong),
    ]


@dataclass(slots=True)
class NdiApplyResult:
    requested: bool
    available: bool
    active_names: list[str]
    message: str
    warning: str | None = None


class NdiLibrary:
    def __init__(self) -> None:
        self._lib = None
        self._dll_handle = None
        self._initialized = False
        self._load_error: str | None = None

    @property
    def available(self) -> bool:
        return self._ensure_loaded()

    @property
    def status_text(self) -> str:
        if self.available:
            return "NDI Runtime найден. Источники можно выводить в сеть."
        if self._load_error:
            return self._load_error
        return "NDI Runtime не найден."

    def create_sender(self, name: str) -> ctypes.c_void_p | None:
        if not self._ensure_loaded() or self._lib is None:
            return None

        create_desc = NDIlib_send_create_t(
            p_ndi_name=name.encode("utf-8"),
            p_groups=None,
            clock_video=True,
            clock_audio=False,
        )
        instance = self._lib.NDIlib_send_create(ctypes.byref(create_desc))
        if not instance:
            return None
        return ctypes.c_void_p(instance)

    def destroy_sender(self, sender: ctypes.c_void_p | None) -> None:
        if sender is None or not self._ensure_loaded() or self._lib is None:
            return
        self._lib.NDIlib_send_destroy(sender)

    def send_video(self, sender: ctypes.c_void_p | None, image: QImage) -> bool:
        if sender is None or not self._ensure_loaded() or self._lib is None or image.isNull():
            return False

        frame_image = image.convertToFormat(QImage.Format.Format_ARGB32)
        bits = frame_image.bits()
        frame_size = frame_image.sizeInBytes()
        if hasattr(bits, "setsize"):
            bits.setsize(frame_size)
            buffer_pointer = ctypes.cast(int(bits), ctypes.POINTER(ctypes.c_uint8))
        else:
            raw_buffer = memoryview(bits).cast("B")
            buffer_pointer = ctypes.cast(ctypes.addressof(ctypes.c_uint8.from_buffer(raw_buffer)), ctypes.POINTER(ctypes.c_uint8))
        frame = NDIlib_video_frame_v2_t(
            xres=frame_image.width(),
            yres=frame_image.height(),
            FourCC=NDI_FOURCC_BGRA,
            frame_rate_N=30,
            frame_rate_D=1,
            picture_aspect_ratio=0.0,
            frame_format_type=NDI_FRAME_FORMAT_PROGRESSIVE,
            timecode=0,
            p_data=buffer_pointer,
            line_stride_in_bytes=frame_image.bytesPerLine(),
            p_metadata=None,
            timestamp=0,
        )
        self._lib.NDIlib_send_send_video_v2(sender, ctypes.byref(frame))
        return True

    def shutdown(self) -> None:
        if self._lib is not None and self._initialized:
            self._lib.NDIlib_destroy()
            self._initialized = False
        self._lib = None
        if self._dll_handle is not None:
            self._dll_handle.close()
            self._dll_handle = None

    def _ensure_loaded(self) -> bool:
        if self._initialized and self._lib is not None:
            return True
        if self._load_error is not None and self._lib is None:
            return False

        library, dll_handle = self._load_library()
        if library is None:
            return False

        library.NDIlib_initialize.restype = ctypes.c_bool
        library.NDIlib_send_create.argtypes = [ctypes.POINTER(NDIlib_send_create_t)]
        library.NDIlib_send_create.restype = ctypes.c_void_p
        library.NDIlib_send_destroy.argtypes = [ctypes.c_void_p]
        library.NDIlib_send_destroy.restype = None
        library.NDIlib_send_send_video_v2.argtypes = [ctypes.c_void_p, ctypes.POINTER(NDIlib_video_frame_v2_t)]
        library.NDIlib_send_send_video_v2.restype = None
        library.NDIlib_destroy.argtypes = []
        library.NDIlib_destroy.restype = None

        if not library.NDIlib_initialize():
            self._load_error = "NDI Runtime найден, но не инициализируется."
            return False

        self._lib = library
        self._dll_handle = dll_handle
        self._initialized = True
        return True

    def _load_library(self) -> tuple[ctypes.WinDLL | None, object | None]:
        names = ["Processing.NDI.Lib.x64.dll", "Processing.NDI.Lib.dll"]
        for name in names:
            try:
                return ctypes.WinDLL(name), None
            except OSError:
                pass

        for candidate in self._candidate_paths():
            if not candidate.exists():
                continue
            dll_handle = None
            try:
                if hasattr(os, "add_dll_directory"):
                    dll_handle = os.add_dll_directory(str(candidate.parent))
                return ctypes.WinDLL(str(candidate)), dll_handle
            except OSError:
                if dll_handle is not None:
                    dll_handle.close()

        self._load_error = "NDI Runtime не найден. Установи NDI Runtime или NDI Tools."
        return None, None

    def _candidate_paths(self) -> list[Path]:
        if os.name != "nt":
            self._load_error = "NDI вывод сейчас подготовлен только для Windows."
            return []

        root = app_root()
        local_appdata = Path(os.environ.get("LOCALAPPDATA", ""))
        program_files = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        program_files_x86 = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
        install_locations = self._ndi_install_locations()

        candidates = [
            root / "Processing.NDI.Lib.x64.dll",
            root / "Processing.NDI.Lib.dll",
            local_appdata / "Programs" / "NDI" / "Runtime" / "Processing.NDI.Lib.x64.dll",
            program_files / "NDI" / "NDI 6 Runtime" / "Processing.NDI.Lib.x64.dll",
            program_files / "NDI" / "NDI 6 Runtime" / "v6" / "Processing.NDI.Lib.x64.dll",
            program_files / "NDI" / "NDI 5 Runtime" / "Processing.NDI.Lib.x64.dll",
            program_files / "NDI" / "NDI 5 Runtime" / "v5" / "Processing.NDI.Lib.x64.dll",
            program_files / "NewTek" / "NDI 5 Runtime" / "Processing.NDI.Lib.x64.dll",
            program_files / "NewTek" / "NDI 5 Runtime" / "v5" / "Processing.NDI.Lib.x64.dll",
            program_files_x86 / "NDI" / "NDI 5 Runtime" / "Processing.NDI.Lib.x64.dll",
            program_files_x86 / "NewTek" / "NDI 5 Runtime" / "Processing.NDI.Lib.x64.dll",
        ]
        for location in install_locations:
            candidates.extend(
                [
                    location / "Processing.NDI.Lib.x64.dll",
                    location / "Processing.NDI.Lib.dll",
                    location / "Runtime" / "Processing.NDI.Lib.x64.dll",
                    location / "Runtime" / "Processing.NDI.Lib.dll",
                    location / "Router" / "Processing.NDI.Lib.x64.dll",
                    location / "Router" / "Processing.NDI.Lib.dll",
                ]
            )
        return candidates

    def _ndi_install_locations(self) -> list[Path]:
        if os.name != "nt":
            return []

        try:
            import winreg
        except ImportError:
            return []

        uninstall_roots = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]

        results: list[Path] = []
        seen: set[str] = set()
        for hive, subkey in uninstall_roots:
            try:
                root = winreg.OpenKey(hive, subkey)
            except OSError:
                continue

            with root:
                count = winreg.QueryInfoKey(root)[0]
                for index in range(count):
                    try:
                        child_name = winreg.EnumKey(root, index)
                        child = winreg.OpenKey(root, child_name)
                    except OSError:
                        continue

                    with child:
                        try:
                            display_name = str(winreg.QueryValueEx(child, "DisplayName")[0])
                        except OSError:
                            continue
                        if "NDI" not in display_name and "NewTek" not in display_name:
                            continue
                        try:
                            install_location = str(winreg.QueryValueEx(child, "InstallLocation")[0]).strip()
                        except OSError:
                            continue
                        if not install_location:
                            continue

                        path = Path(install_location)
                        key = str(path).lower()
                        if key in seen:
                            continue
                        seen.add(key)
                        results.append(path)

        return results


class NdiVideoSender:
    def __init__(self, library: NdiLibrary) -> None:
        self._library = library
        self._sender: ctypes.c_void_p | None = None
        self._name: str | None = None

    @property
    def active(self) -> bool:
        return self._sender is not None

    @property
    def name(self) -> str | None:
        return self._name

    def configure(self, name: str | None) -> bool:
        clean_name = (name or "").strip()
        if not clean_name:
            self.stop()
            return False
        if self._sender is not None and self._name == clean_name:
            return True

        self.stop()
        sender = self._library.create_sender(clean_name)
        if sender is None:
            self._name = None
            return False

        self._sender = sender
        self._name = clean_name
        return True

    def stop(self) -> None:
        if self._sender is not None:
            self._library.destroy_sender(self._sender)
        self._sender = None
        self._name = None

    def send_image(self, image: QImage) -> bool:
        return self._library.send_video(self._sender, image)


class NdiOutputController:
    def __init__(self) -> None:
        self.library = NdiLibrary()
        self.main_sender = NdiVideoSender(self.library)
        self.teleprompter_sender = NdiVideoSender(self.library)

    @property
    def has_active_outputs(self) -> bool:
        return self.main_sender.active or self.teleprompter_sender.active

    def apply(self, main_name: str | None, teleprompter_name: str | None) -> NdiApplyResult:
        requested = bool((main_name or "").strip() or (teleprompter_name or "").strip())
        if not requested:
            self.stop()
            return NdiApplyResult(
                requested=False,
                available=self.library.available,
                active_names=[],
                message="NDI выключен для этой вкладки.",
            )

        if not self.library.available:
            self.stop()
            return NdiApplyResult(
                requested=True,
                available=False,
                active_names=[],
                message=self.library.status_text,
                warning=self.library.status_text,
            )

        active_names: list[str] = []
        if self.main_sender.configure(main_name):
            if self.main_sender.name:
                active_names.append(self.main_sender.name)
        else:
            self.main_sender.stop()

        if self.teleprompter_sender.configure(teleprompter_name):
            if self.teleprompter_sender.name:
                active_names.append(self.teleprompter_sender.name)
        else:
            self.teleprompter_sender.stop()

        if not active_names:
            return NdiApplyResult(
                requested=True,
                available=True,
                active_names=[],
                message="NDI включён, но источники не создались.",
                warning="NDI Runtime найден, но источники не удалось создать.",
            )

        joined = ", ".join(active_names)
        return NdiApplyResult(
            requested=True,
            available=True,
            active_names=active_names,
            message=f"NDI в эфире: {joined}",
        )

    def send(self, main_image: QImage | None, teleprompter_image: QImage | None) -> None:
        if main_image is not None and self.main_sender.active:
            self.main_sender.send_image(main_image)
        if teleprompter_image is not None and self.teleprompter_sender.active:
            self.teleprompter_sender.send_image(teleprompter_image)

    def stop(self) -> None:
        self.main_sender.stop()
        self.teleprompter_sender.stop()

    def shutdown(self) -> None:
        self.stop()
        self.library.shutdown()
