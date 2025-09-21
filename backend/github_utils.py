import os
import subprocess
from typing import List, Tuple, Optional
from urllib.parse import urlparse

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")


def parse_github_url(url: str) -> Tuple[str, str]:
    """Return (owner, repo) from a GitHub URL."""
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    parts = path.split("/")
    if len(parts) < 2:
        raise ValueError("Invalid GitHub URL")
    return parts[0], parts[1].removesuffix(".git")


def gh_authenticated() -> bool:
    try:
        subprocess.run(["gh", "auth", "status"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


def _auth_url(url: str, token: Optional[str]) -> str:
    if not token:
        return url
    # Embed token for HTTPS clone, stripping any existing credentials first
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return url
    # Strip userinfo if present (e.g., token@github.com)
    host = parsed.netloc.split("@")[-1]
    if not host.endswith("github.com"):
        return url
    auth_netloc = f"{token}@{host}"
    return parsed._replace(netloc=auth_netloc).geturl()


def clone_or_fetch(url: str, workdir: str, token: Optional[str] = None) -> str:
    """Clone if missing, else fetch. Returns local path."""
    owner, repo = parse_github_url(url)
    local = os.path.join(workdir, f"{owner}__{repo}")
    if not os.path.exists(local):
        clone_url = _auth_url(url, token)
        subprocess.run(["git", "clone", clone_url, local], check=True)
        # After clone, reset origin URL to non-auth form to avoid storing token
        try:
            subprocess.run(["git", "-C", local, "remote", "set-url", "origin", url], check=True)
        except subprocess.CalledProcessError:
            pass
    else:
        # Use authed URL transiently to fetch without mutating remotes
        if token:
            origin_url = subprocess.run(["git", "-C", local, "remote", "get-url", "origin"], check=True, capture_output=True, text=True).stdout.strip()
            authed = _auth_url(origin_url, token)
            subprocess.run(["git", "-C", local, "fetch", authed, "--prune"], check=True)
        else:
            subprocess.run(["git", "-C", local, "fetch", "--all"], check=True)
    return local


def get_latest_commit(local_repo: str, branch: str = "origin/main") -> str:
    try:
        result = subprocess.run(["git", "-C", local_repo, "rev-parse", branch], check=True, capture_output=True, text=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        # Fallback to origin/master if origin/main doesn't exist
        fallback = "origin/master" if branch == "origin/main" else branch
        result = subprocess.run(["git", "-C", local_repo, "rev-parse", fallback], check=True, capture_output=True, text=True)
        return result.stdout.strip()
def _ensure_git_identity(local_repo: str) -> None:
    def _has(key: str) -> bool:
        r = subprocess.run(["git", "-C", local_repo, "config", "--get", key], capture_output=True, text=True)
        return r.returncode == 0 and r.stdout.strip() != ""
    if not _has("user.email"):
        email = os.getenv("GIT_USER_EMAIL", "code-reviewer-bot@local")
        subprocess.run(["git", "-C", local_repo, "config", "user.email", email], check=True)
    if not _has("user.name"):
        name = os.getenv("GIT_USER_NAME", "Code Reviewer Bot")
        subprocess.run(["git", "-C", local_repo, "config", "user.name", name], check=True)



def diff_changed_files(local_repo: str, base_sha: str, head_sha: str) -> List[str]:
    result = subprocess.run(["git", "-C", local_repo, "diff", "--name-only", base_sha, head_sha], check=True, capture_output=True, text=True)
    return [p for p in result.stdout.splitlines() if p]


def create_branch_commit_push(local_repo: str, branch: str, message: str, token: Optional[str] = None) -> None:
    subprocess.run(["git", "-C", local_repo, "checkout", "-B", branch], check=True)
    subprocess.run(["git", "-C", local_repo, "add", "-A"], check=True)
    # Commit only if there are staged changes
    status = subprocess.run(["git", "-C", local_repo, "diff", "--cached", "--quiet"], capture_output=True)
    if status.returncode != 0:
        _ensure_git_identity(local_repo)
        subprocess.run(["git", "-C", local_repo, "commit", "-m", message], check=True)
        try:
            origin_url = subprocess.run(["git", "-C", local_repo, "remote", "get-url", "origin"], check=True, capture_output=True, text=True).stdout.strip()
            push_target = _auth_url(origin_url, token) if token else origin_url
            subprocess.run(["git", "-C", local_repo, "push", "-u", push_target, f"HEAD:{branch}"], check=True)
        except subprocess.CalledProcessError:
            # Retry with force-with-lease in case branch exists and is non-fast-forward
            try:
                origin_url = subprocess.run(["git", "-C", local_repo, "remote", "get-url", "origin"], check=True, capture_output=True, text=True).stdout.strip()
                push_target = _auth_url(origin_url, token) if token else origin_url
                subprocess.run(["git", "-C", local_repo, "push", "--force-with-lease", "-u", push_target, f"HEAD:{branch}"], check=True)
            except subprocess.CalledProcessError:
                # Try fork workflow as a last resort
                try:
                    ensure_fork_remote(local_repo)
                    subprocess.run(["git", "-C", local_repo, "push", "-u", "origin", branch], check=True)
                except FileNotFoundError:
                    raise RuntimeError("Cannot push changes: missing permissions and GitHub CLI not available. Set GITHUB_TOKEN to enable HTTPS push.")
    else:
        # No changes but ensure branch exists on remote (create empty branch by pushing existing state)
        try:
            origin_url = subprocess.run(["git", "-C", local_repo, "remote", "get-url", "origin"], check=True, capture_output=True, text=True).stdout.strip()
            push_target = _auth_url(origin_url, token) if token else origin_url
            subprocess.run(["git", "-C", local_repo, "push", "-u", push_target, f"HEAD:{branch}"], check=True)
        except subprocess.CalledProcessError:
            try:
                origin_url = subprocess.run(["git", "-C", local_repo, "remote", "get-url", "origin"], check=True, capture_output=True, text=True).stdout.strip()
                push_target = _auth_url(origin_url, token) if token else origin_url
                subprocess.run(["git", "-C", local_repo, "push", "--force-with-lease", "-u", push_target, f"HEAD:{branch}"], check=True)
            except subprocess.CalledProcessError:
                try:
                    ensure_fork_remote(local_repo)
                    subprocess.run(["git", "-C", local_repo, "push", "-u", "origin", branch], check=True)
                except FileNotFoundError:
                    raise RuntimeError("Cannot push branch: missing permissions and GitHub CLI not available. Set GITHUB_TOKEN to enable HTTPS push.")


def create_pr_in_repo(local_repo: str, branch: str, title: str, body: str, token: Optional[str] = None) -> str:
    env = os.environ.copy()
    if token:
        env["GH_TOKEN"] = token
    # Prefer using gh to actually create the PR
    try:
        result = subprocess.run([
            "gh", "pr", "create",
            "--title", title,
            "--body", body,
            "--head", branch,
        ], check=True, capture_output=True, text=True, env=env, cwd=local_repo)
        return result.stdout.strip()
    except FileNotFoundError:
        # gh not installed; fall back to constructing a link
        origin = subprocess.run(["git", "-C", local_repo, "remote", "get-url", "origin"], check=True, capture_output=True, text=True).stdout.strip()
        owner, repo = parse_github_url(origin)
        return f"https://github.com/{owner}/{repo}/pull/new/{branch}"
    except subprocess.CalledProcessError as e:
        # If PR already exists, try to fetch its URL
        try:
            view = subprocess.run([
                "gh", "pr", "view", branch, "--json", "url", "-q", ".url"
            ], check=True, capture_output=True, text=True, env=env, cwd=local_repo)
            url = view.stdout.strip()
            if url:
                return url
        except Exception:
            pass
        # Fallback to a link to create PR manually
        origin = subprocess.run(["git", "-C", local_repo, "remote", "get-url", "origin"], check=True, capture_output=True, text=True).stdout.strip()
        owner, repo = parse_github_url(origin)
        return f"https://github.com/{owner}/{repo}/pull/new/{branch}"


def ensure_fork_remote(local_repo: str) -> None:
    # If 'upstream' remote missing, fork and set remotes
    remotes = subprocess.run(["git", "-C", local_repo, "remote"], check=True, capture_output=True, text=True).stdout.split()
    if "upstream" not in remotes:
        try:
            subprocess.run(["gh", "repo", "fork", "--remote"], check=True, cwd=local_repo)
        except subprocess.CalledProcessError:
            # Likely cannot fork own repository; ignore and proceed
            pass
