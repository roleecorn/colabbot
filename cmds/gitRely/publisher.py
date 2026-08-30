"""Serialised, non-blocking Git publication."""

from __future__ import annotations

import asyncio
import subprocess
import tempfile
from pathlib import Path


class GitPublishError(RuntimeError):
    """Raised when the public repository could not be published."""


class GitPublisher:
    _locks: dict[Path, asyncio.Lock] = {}

    def __init__(self, timeout: int = 120) -> None:
        self.timeout = timeout

    @classmethod
    def _lock_for(cls, repo: Path) -> asyncio.Lock:
        return cls._locks.setdefault(repo.resolve(), asyncio.Lock())

    def _publish_sync(self, repo: Path, message: str) -> None:
        def run(*args: str) -> tuple[int, str]:
            # On Windows, subprocess.run(capture_output=True) starts reader
            # threads for the pipes.  Git can close a pipe while that reader
            # is consuming it, which occasionally leaks a readerthread
            # traceback even when the publish itself succeeds.  A temporary
            # file keeps output available for diagnostics without using pipes.
            with tempfile.TemporaryFile() as output:
                process = subprocess.run(
                    ["git", *args],
                    cwd=repo,
                    stdout=output,
                    stderr=subprocess.STDOUT,
                    timeout=self.timeout,
                )
                output.seek(0)
                details = output.read().decode("utf-8", errors="replace")
            return process.returncode, details

        try:
            return_code, details = run("add", ".")
            if return_code != 0:
                raise GitPublishError(details.strip() or "git add failed")

            return_code, details = run("commit", "-m", message)
            # A clean tree is not an error; pull/push still keeps the branch up
            # to date and gives callers a successful publish result.
            if return_code != 0 and "nothing to commit" not in details.lower():
                raise GitPublishError(details.strip() or "git commit failed")

            return_code, details = run("pull", "--rebase")
            if return_code != 0:
                raise GitPublishError(details.strip() or "git pull failed")

            return_code, details = run("push")
            if return_code != 0:
                raise GitPublishError(details.strip() or "git push failed")
        except (OSError, subprocess.SubprocessError) as exc:
            raise GitPublishError(str(exc)) from exc

    async def publish(self, repo_path: str | Path, message: str) -> None:
        repo = Path(repo_path)
        if not repo.is_dir():
            raise GitPublishError(f"repository directory not found: {repo}")
        async with self._lock_for(repo):
            await asyncio.to_thread(self._publish_sync, repo, message)
