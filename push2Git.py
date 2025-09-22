import subprocess
import os

def git_commit_and_push(repo_path: str, commit_message: str):
    try:
        cwd = os.path.abspath(repo_path)
        subprocess.run(["git", "add", "."], cwd=cwd, check=True)
        commit_proc = subprocess.run(
            ["git", "commit", "-m", commit_message],
            cwd=cwd
        )
        if commit_proc.returncode != 0:
            print("⚠️ 沒有新變更可提交，跳過 commit")

        # 拉取最新版本，避免衝突
        subprocess.run(["git", "pull", "--rebase"], cwd=cwd, check=True)
        subprocess.run(["git", "push"], cwd=cwd, check=True)

        return True, "✅ 成功將檔案 commit 並 push 到 GitHub"
    except subprocess.CalledProcessError as e:
        return False, f"❌ Git 操作失敗：{e}"
