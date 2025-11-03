import subprocess
import os
import threading

# 全域鎖
_git_lock = threading.Lock()

def git_commit_and_push(repo_path: str, commit_message: str):
    with _git_lock:  # 確保同一時間只會有一個在執行
        try:
            cwd = os.path.abspath(repo_path)
            subprocess.run(["git", "add", "."], cwd=cwd, check=True)
            commit_proc = subprocess.run(
                ["git", "commit", "-m", commit_message],
                cwd=cwd
            )
            if commit_proc.returncode != 0:
                print("⚠️ 沒有新變更可提交，跳過 commit")

            subprocess.run(["git", "pull", "--rebase"], cwd=cwd, check=True)
            subprocess.run(["git", "push"], cwd=cwd, check=True)

            return True, "✅ 成功將檔案 commit 並 push 到 GitHub"
        except subprocess.CalledProcessError as e:
            return False, f"❌ Git 操作失敗：{e}"
