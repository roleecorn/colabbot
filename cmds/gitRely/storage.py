"""Safe archive extraction and recoverable submission directory operations."""

from __future__ import annotations

import html
import os
import secrets
import shutil
import stat
import tempfile
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from typing import Iterable


ARCHIVE_EXTENSIONS = (".zip", ".rar", ".7z")
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp")


def _configure_rar_tool(rarfile_module) -> None:
    """Configure rarfile from deployment settings and common Windows paths."""
    candidates: list[str] = []
    configured = os.environ.get("RAR_TOOL") or os.environ.get("UNRAR_TOOL")
    if configured:
        candidates.append(configured)

    for command in ("unrar", "UnRAR.exe", "7z", "7zz", "bsdtar"):
        resolved = shutil.which(command)
        if resolved:
            candidates.append(resolved)

    program_roots = {
        value
        for variable in ("ProgramFiles", "ProgramW6432", "LOCALAPPDATA")
        if (value := os.environ.get(variable))
    }
    for root in program_roots:
        candidates.extend(
            str(Path(root) / relative)
            for relative in (
                Path("WinRAR") / "UnRAR.exe",
                Path("7-Zip") / "7z.exe",
                Path("7-Zip") / "7zz.exe",
            )
        )

    tool = next((candidate for candidate in candidates if Path(candidate).is_file()), None)
    if tool:
        # rarfile selects the first compatible backend. Setting all tool
        # constants lets an absolute RAR_TOOL point to either UnRAR or 7-Zip.
        rarfile_module.UNRAR_TOOL = tool
        rarfile_module.UNAR_TOOL = tool
        rarfile_module.SEVENZIP_TOOL = tool
        rarfile_module.SEVENZIP2_TOOL = tool
        rarfile_module.BSDTAR_TOOL = tool
    rarfile_module.tool_setup(force=True)


def safe_component(value: str, *, label: str = "path component") -> str:
    value = str(value).strip()
    if not value or value in {".", ".."} or "/" in value or "\\" in value:
        raise ValueError(f"invalid {label}")
    if Path(value).drive or ":" in value:
        raise ValueError(f"invalid {label}")
    return value


def new_participant_key(existing: Iterable[str] = ()) -> str:
    used = set(existing)
    for _ in range(20):
        key = secrets.token_urlsafe(6).replace("-", "a").replace("_", "b")[:8]
        if key and key not in used:
            return key
    raise RuntimeError("could not allocate a unique participant key")


def new_topic_key(existing: Iterable[str] = ()) -> str:
    return new_participant_key(existing)[:6]


def _safe_member_name(name: str) -> PurePosixPath:
    normalised = name.replace("\\", "/")
    path = PurePosixPath(normalised)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"unsafe archive path: {name!r}")
    if len(path.parts[0]) >= 2 and path.parts[0][1] == ":":
        raise ValueError(f"unsafe archive path: {name!r}")
    return path


def _ensure_within(root: Path, relative: PurePosixPath) -> Path:
    destination = (root / Path(*relative.parts)).resolve()
    root_resolved = root.resolve()
    if destination != root_resolved and root_resolved not in destination.parents:
        raise ValueError(f"archive path escapes destination: {relative}")
    return destination


def _write_member(source, destination: Path, maximum: int, current: list[int]) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as target:
        while True:
            chunk = source.read(1024 * 1024)
            if not chunk:
                break
            current[0] += len(chunk)
            if current[0] > maximum:
                raise ValueError("archive expands beyond the configured size limit")
            target.write(chunk)


class SubmissionStorage:
    def __init__(
        self,
        staging_root: str | Path = "uploads",
        *,
        max_uncompressed_bytes: int = 100 * 1024 * 1024,
        max_files: int = 500,
    ) -> None:
        self.staging_root = Path(staging_root)
        self.max_uncompressed_bytes = max_uncompressed_bytes
        self.max_files = max_files

    def create_request_directory(self) -> Path:
        self.staging_root.mkdir(parents=True, exist_ok=True)
        return Path(tempfile.mkdtemp(prefix=f"event-{uuid.uuid4()}-", dir=self.staging_root))

    def extract_archive(self, archive: str | Path, destination: str | Path) -> Path:
        source = Path(archive)
        destination = Path(destination)
        if source.suffix.lower() not in ARCHIVE_EXTENSIONS:
            raise ValueError("unsupported archive format")
        destination.mkdir(parents=True, exist_ok=True)
        total = [0]
        seen = set()
        completed = False
        try:
            if source.suffix.lower() == ".zip":
                archive_file = zipfile.ZipFile(source)
                members = archive_file.infolist()
                files = [item for item in members if not item.is_dir()]
                if len(files) > self.max_files:
                    raise ValueError("archive contains too many files")
                for info in members:
                    relative = _safe_member_name(info.filename)
                    target = _ensure_within(destination, relative)
                    if info.filename in seen:
                        raise ValueError(f"duplicate archive path: {info.filename!r}")
                    seen.add(info.filename)
                    mode = (info.external_attr >> 16) & 0o170000
                    if mode == stat.S_IFLNK:
                        raise ValueError("symbolic links are not allowed in archives")
                    if not info.is_dir():
                        if info.file_size > self.max_uncompressed_bytes:
                            raise ValueError("archive member is too large")
                        with archive_file.open(info) as source_file:
                            _write_member(source_file, target, self.max_uncompressed_bytes, total)
                archive_file.close()
            elif source.suffix.lower() == ".rar":
                try:
                    import rarfile
                except ImportError as exc:
                    raise RuntimeError("RAR extraction requires the rarfile package") from exc
                try:
                    _configure_rar_tool(rarfile)
                    with rarfile.RarFile(source) as archive_file:
                        members = archive_file.infolist()
                        files = [item for item in members if not item.isdir()]
                        self._validate_members((item.filename, item.file_size) for item in files)
                        for info in files:
                            relative = _safe_member_name(info.filename)
                            target = _ensure_within(destination, relative)
                            with archive_file.open(info) as source_file:
                                _write_member(source_file, target, self.max_uncompressed_bytes, total)
                except rarfile.RarCannotExec as exc:
                    raise RuntimeError(
                        "RAR extraction requires UnRAR or 7-Zip; install one or set RAR_TOOL"
                    ) from exc
            else:
                try:
                    import py7zr
                except ImportError as exc:
                    raise RuntimeError("7z extraction requires the py7zr package") from exc
                with py7zr.SevenZipFile(source, mode="r") as archive_file:
                    members = archive_file.list()
                    files = [item for item in members if not item.is_directory]
                    self._validate_members(
                        (item.filename, int(item.uncompressed or 0)) for item in files
                    )
                    # All member names have been checked before extraction, and
                    # the destination is request-local staging, never the live
                    # submission directory.
                    archive_file.extractall(path=destination)
                self._validate_extracted_tree(destination)
            completed = True
        finally:
            if not completed:
                shutil.rmtree(destination, ignore_errors=True)
        return destination

    def _validate_members(self, members) -> None:
        count = 0
        total = 0
        for name, size in members:
            _safe_member_name(name)
            count += 1
            total += max(0, int(size))
        if count > self.max_files:
            raise ValueError("archive contains too many files")
        if total > self.max_uncompressed_bytes:
            raise ValueError("archive expands beyond the configured size limit")

    def _validate_extracted_tree(self, destination: Path) -> None:
        files = 0
        total = 0
        root = destination.resolve()
        for path in destination.rglob("*"):
            resolved = path.resolve()
            if resolved != root and root not in resolved.parents:
                raise ValueError("archive extraction escaped destination")
            if path.is_symlink():
                raise ValueError("symbolic links are not allowed in archives")
            if path.is_file():
                files += 1
                total += path.stat().st_size
        if files > self.max_files or total > self.max_uncompressed_bytes:
            raise ValueError("extracted archive exceeds configured limits")

    @staticmethod
    def generate_gallery(folder: str | Path, title: str) -> Path:
        root = Path(folder)
        if not title.strip():
            raise ValueError("title cannot be empty")
        existing_html = sorted(
            (
                path
                for path in root.rglob("*")
                if path.is_file() and path.suffix.lower() in {".html", ".htm"}
            ),
            key=lambda path: path.as_posix().lower(),
        )
        if existing_html:
            return next(
                (path for path in existing_html if path.name.lower() == "index.html"),
                existing_html[0],
            )
        images = sorted(
            (path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS),
            key=lambda path: path.as_posix().lower(),
        )
        if not images:
            raise ValueError("submission contains no images or HTML file")
        tags = []
        for image in images:
            relative = image.relative_to(root).as_posix()
            tags.append(
                f'<img src="{html.escape(relative, quote=True)}" alt="Submission image" '
                'style="max-width:100%;height:auto"><br>\n'
            )
        content = (
            "<!doctype html><html><head><meta charset=\"utf-8\"><title>"
            f"{html.escape(title)}"
            "</title></head><body><h1>"
            f"{html.escape(title)}"
            "</h1>\n"
            + "".join(tags)
            + "</body></html>\n"
        )
        output = root / "index.html"
        output.write_text(content, encoding="utf-8", newline="\n")
        return output

    def replace_directory(self, staged: str | Path, target: str | Path) -> Path | None:
        staged_path = Path(staged)
        target_path = Path(target)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        backup: Path | None = None
        if target_path.exists():
            if not target_path.is_dir():
                raise ValueError(f"submission target is not a directory: {target_path}")
            # Keep the rollback copy in the request-local staging directory.
            # The target lives in a public Git repository, so placing the
            # backup beside it would make ``git add .`` see an internal file.
            backup = staged_path.parent / f".{target_path.name}.backup-{uuid.uuid4().hex}"
            os.replace(target_path, backup)
        try:
            os.replace(staged_path, target_path)
        except BaseException:
            if backup and backup.exists() and not target_path.exists():
                os.replace(backup, target_path)
            raise
        return backup

    @staticmethod
    def rollback(target: str | Path, backup: str | Path | None) -> None:
        target_path = Path(target)
        backup_path = Path(backup) if backup else None
        if target_path.exists():
            shutil.rmtree(target_path)
        if backup_path and backup_path.exists():
            os.replace(backup_path, target_path)

    @staticmethod
    def discard_backup(backup: str | Path | None) -> None:
        if backup:
            shutil.rmtree(Path(backup), ignore_errors=True)

    @staticmethod
    def cleanup(path: str | Path) -> None:
        shutil.rmtree(Path(path), ignore_errors=True)
