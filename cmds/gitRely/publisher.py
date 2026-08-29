"""Serialised, non-blocking Git publication."""

from __future__ import annotations

import asyncio
import subprocess
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
        def run(*args: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                ["git", *args],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

        try:
            run("add", ".")
            commit = subprocess.run(
                ["git", "commit", "-m", message],
                cwd=repo,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            # A clean tree is not an error; pull/push still keeps the branch up
            # to date and gives callers a successful publish result.
            if commit.returncode != 0 and "nothing to commit" not in (
                commit.stdout + commit.stderr
            ).lower():
                raise GitPublishError(commit.stderr.strip() or "git commit failed")
            run("pull", "--rebase")
            run("push")
        except (OSError, subprocess.SubprocessError) as exc:
            raise GitPublishError(str(exc)) from exc

    async def publish(self, repo_path: str | Path, message: str) -> None:
        repo = Path(repo_path)
        if not repo.is_dir():
            raise GitPublishError(f"repository directory not found: {repo}")
        async with self._lock_for(repo):
            await asyncio.to_thread(self._publish_sync, repo, message)
