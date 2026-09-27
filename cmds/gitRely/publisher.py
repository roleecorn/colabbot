"""Serialised, non-blocking Git publication."""

from __future__ import annotations

import asyncio
import subprocess
import tempfile
from pathlib import Path


_BACKUP_PATHSPEC = ":(exclude)**/*.backup-*"


class GitPublishError(RuntimeError):
    """Raised when the public repository could not be published."""


class LocalOnlyPublisher:
    """Accept local test-mode updates without contacting a Git remote."""

    async def publish(self, repo_path: str | Path, message: str) -> None:
        return None


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

        before_head: str | None = None
        commit_created = False
        try:
            return_code, details = run("rev-parse", "HEAD")
            if return_code != 0:
                raise GitPublishError(details.strip() or "git rev-parse failed")
            before_head = details.strip()

            # First stage changes to paths that Git already tracks.  This also
            # removes old backup files that were accidentally committed by an
            # earlier version of the publisher.
            return_code, details = run("add", "--update", "--", ".")
            if return_code != 0:
                raise GitPublishError(details.strip() or "git add --update failed")

            # New rollback backups are outside the public repository.  Keep
            # this exclusion for any stale, untracked backup left by an
            # interrupted request, but do not exclude tracked deletions above.
            return_code, details = run("add", "--all", "--", ".", _BACKUP_PATHSPEC)
            if return_code != 0:
                raise GitPublishError(details.strip() or "git add failed")

            return_code, details = run("commit", "-m", message)
            # A clean tree is not an error; pull/push still keeps the branch up
            # to date and gives callers a successful publish result.
            if return_code == 0:
                commit_created = True
            elif "nothing to commit" not in details.lower():
                raise GitPublishError(details.strip() or "git commit failed")

            return_code, details = run("pull", "--rebase")
            if return_code != 0:
                raise GitPublishError(details.strip() or "git pull failed")

            return_code, details = run("push")
            if return_code != 0:
                raise GitPublishError(details.strip() or "git push failed")
        except (GitPublishError, OSError, subprocess.SubprocessError) as exc:
            if commit_created and before_head:
                try:
                    reset_code, reset_details = run("reset", "--mixed", before_head)
                except (OSError, subprocess.SubprocessError) as reset_exc:
                    raise GitPublishError(
                        f"{exc}; additionally failed to roll back local commit: {reset_exc}"
                    ) from exc
                if reset_code != 0:
                    raise GitPublishError(
                        f"{exc}; additionally failed to roll back local commit: "
                        f"{reset_details.strip() or 'git reset failed'}"
                    ) from exc
            if isinstance(exc, GitPublishError):
                raise
            raise GitPublishError(str(exc)) from exc

    async def publish(self, repo_path: str | Path, message: str) -> None:
        repo = Path(repo_path)
        if not repo.is_dir():
            raise GitPublishError(f"repository directory not found: {repo}")
        async with self._lock_for(repo):
            await asyncio.to_thread(self._publish_sync, repo, message)
