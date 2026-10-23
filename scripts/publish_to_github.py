"""Automated GitHub Publisher for SentinelGate.

Uses pure-Python Dulwich and GitHub REST API to:
1. Authenticate with GitHub securely (using getpass or GITHUB_TOKEN env var).
2. Create the public repository 'sentinelgate' under your account if it doesn't exist.
3. Initialize the Git repository locally, commit all project files, and push to main branch.
4. Works seamlessly even if macOS Xcode Command Line Tools are missing.
"""

import getpass
import os
import sys
from pathlib import Path

import dulwich.porcelain as dp
import httpx
from dulwich.repo import Repo

REPO_NAME = "sentinelgate"
REPO_DESCRIPTION = (
    "Production-grade reverse proxy gateway for LLMs featuring real-time dual-layer prompt "
    "injection defense, PII masking, sub-millisecond semantic caching, and RAG hallucination evaluation."
)


def get_token() -> str:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        return token

    print("\n" + "=" * 65)
    print("🔒 GitHub Authentication")
    print("=" * 65)
    print("Please paste your GitHub Personal Access Token (PAT).")
    print("It will be hidden as you type for security.")
    print("Generate one at: https://github.com/settings/tokens (Scope: repo)\n")
    try:
        token = getpass.getpass("Enter GitHub Token: ").strip()
    except Exception:
        token = input("Enter GitHub Token: ").strip()

    # Remove any stray spaces
    token = "".join(token.split())
    return token


def verify_and_create_repo(token: str) -> tuple[str, str]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "SentinelGate-Publisher",
    }

    # 1. Verify user
    with httpx.Client(timeout=15.0) as client:
        user_resp = client.get("https://api.github.com/user", headers=headers)
        if user_resp.status_code != 200:
            print(f"\n❌ Authentication failed (HTTP {user_resp.status_code}):")
            print(user_resp.text)
            sys.exit(1)

        user_data = user_resp.json()
        username = user_data.get("login")
        user_email = user_data.get("email") or f"{username}@users.noreply.github.com"
        print(f"✓ Authenticated as: {username} ({user_data.get('name') or username})")

        # 2. Check if repo exists
        repo_resp = client.get(f"https://api.github.com/repos/{username}/{REPO_NAME}", headers=headers)
        if repo_resp.status_code == 200:
            print(f"✓ Repository '{username}/{REPO_NAME}' already exists on GitHub.")
        elif repo_resp.status_code == 404:
            print(f"⚙ Creating public repository '{username}/{REPO_NAME}' on GitHub...")
            create_payload = {
                "name": REPO_NAME,
                "description": REPO_DESCRIPTION,
                "private": False,
                "has_issues": True,
                "has_projects": True,
                "has_wiki": False,
            }
            create_resp = client.post(
                "https://api.github.com/user/repos", headers=headers, json=create_payload
            )
            if create_resp.status_code in (200, 201):
                print(f"✓ Successfully created public repository '{username}/{REPO_NAME}'!")
            else:
                print(f"❌ Failed to create repository (HTTP {create_resp.status_code}):")
                print(create_resp.text)
                sys.exit(1)
        else:
            print(f"❌ Unexpected GitHub API response: {repo_resp.status_code}")
            sys.exit(1)

    return username, user_email


def commit_and_push(username: str, user_email: str, token: str, root_dir: Path):
    print("\n📦 Initializing and staging project files with Dulwich...")

    git_dir = root_dir / ".git"
    if not git_dir.exists():
        repo = Repo.init(str(root_dir))
        print("✓ Initialized local Git repository.")
    else:
        repo = Repo(str(root_dir))
        print("✓ Found existing local Git repository.")

    # Stage all files
    dp.add(str(root_dir))
    print("✓ Staged all project files.")

    # Commit
    author_str = f"{username} <{user_email}>"
    try:
        commit_sha = dp.commit(
            str(root_dir),
            message=b"feat: initial release - SentinelGate dual-layer AI security gateway\n\n- Production-grade OpenAI reverse proxy\n- Dual-layer prompt injection defense (heuristic + semantic vector)\n- Real-time PII masking (Luhn algorithm)\n- Sub-millisecond semantic caching\n- RAG groundedness evaluation\n- 191 passing tests",
            author=author_str.encode("utf-8"),
            committer=author_str.encode("utf-8"),
        )
        print(f"✓ Created commit: {commit_sha.decode('utf-8')[:8] if isinstance(commit_sha, bytes) else str(commit_sha)[:8]}")
    except Exception as e:
        print(f"ℹ Commit status: {e}")

    # Set default branch to main
    try:
        repo.refs[b"refs/heads/main"] = repo.head()
    except Exception:
        pass

    # Push to GitHub
    remote_url = f"https://{username}:{token}@github.com/{username}/{REPO_NAME}.git"
    print(f"🚀 Pushing to https://github.com/{username}/{REPO_NAME}.git (branch: main)...")

    try:
        dp.push(str(root_dir), remote_location=remote_url, refspecs=[b"refs/heads/main:refs/heads/main"], force=True)
        print("\n" + "=" * 65)
        print("🎉 SUCCESS! SentinelGate is live on GitHub!")
        print("=" * 65)
        print(f"🔗 Repository URL: https://github.com/{username}/{REPO_NAME}")
        print("=" * 65 + "\n")
    except Exception as e:
        print(f"\n❌ Push failed: {e}")
        print("You can also push manually via standard git:")
        print(f"  git remote add origin https://github.com/{username}/{REPO_NAME}.git")
        print("  git push -u origin main")


def main():
    root_dir = Path(__file__).resolve().parent.parent
    token = get_token()
    if not token:
        print("❌ No token provided. Aborted.")
        sys.exit(1)

    username, email = verify_and_create_repo(token)
    commit_and_push(username, email, token, root_dir)


if __name__ == "__main__":
    main()
