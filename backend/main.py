import argparse
import os
import sys
import tempfile
from typing import Optional

from fastapi import FastAPI, Body, Path, Query
from fastapi.responses import JSONResponse
import uvicorn
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy.orm import Session
from sqlalchemy import select

from dotenv import load_dotenv

# Allow running as a script: `uv run backend/main.py ...`
if __package__ is None or __package__ == "":
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from backend.db import engine, get_db
from backend.models import Base, Repository, Review, FileFeedback
from backend.github_utils import (
    clone_or_fetch,
    parse_github_url,
    get_latest_commit,
    diff_changed_files,
    create_branch_commit_push,
    create_pr_in_repo,
)
from backend.ai_utils import classify_file_and_feedback

load_dotenv()
app = FastAPI(title="Code Reviewer", version="0.1.0")

# Configure CORS via environment
cors_origins_env = os.getenv("CORS_ORIGINS", "*")
if cors_origins_env.strip() == "*":
    _origins = ["*"]
else:
    _origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()]
allow_credentials = os.getenv("CORS_ALLOW_CREDENTIALS", "false").lower() == "true"

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/")
def root() -> dict:
    return {"status": "ok", "service": "code-reviewer", "version": app.version}


@app.post("/review")
def review_endpoint(payload: dict = Body(...)):
    repo = payload.get("repo")
    mode = payload.get("mode")
    if not repo:
        return JSONResponse(status_code=400, content={"error": "Missing 'repo'"})
    try:
        summary = review_repo(repo, mode=mode)
        return summary
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/reviews")
def list_reviews(repo: Optional[str] = Query(default=None), limit: int = Query(default=20, ge=1, le=100)):
    ensure_db()
    with next(get_db()) as db:  # type: ignore
        assert isinstance(db, Session)
        stmt = select(Review, Repository).join(Repository, Review.repository_id == Repository.id).order_by(Review.created_at.desc()).limit(limit)
        if repo:
            stmt = stmt.where(Repository.url == repo)
        rows = db.execute(stmt).all()
        out = []
        for review, repository in rows:
            out.append({
                "id": review.id,
                "repository": repository.url,
                "owner": repository.owner,
                "name": repository.name,
                "commit": review.commit_sha,
                "branch": review.branch,
                "pr_url": review.pr_url,
                "created_at": review.created_at.isoformat(),
            })
        return {"items": out}


@app.get("/reviews/{review_id}")
def get_review(review_id: int = Path(...)):
    ensure_db()
    with next(get_db()) as db:  # type: ignore
        assert isinstance(db, Session)
        review = db.get(Review, review_id)
        if not review:
            return JSONResponse(status_code=404, content={"error": "Review not found"})
        repo = db.get(Repository, review.repository_id)
        files = db.execute(select(FileFeedback).where(FileFeedback.review_id == review_id)).scalars().all()
        return {
            "id": review.id,
            "repository": repo.url if repo else None,
            "commit": review.commit_sha,
            "branch": review.branch,
            "pr_url": review.pr_url,
            "created_at": review.created_at.isoformat(),
            "files": [
                {
                    "file_path": f.file_path,
                    "classification": f.classification,
                    "feedback": f.feedback,
                    "created_at": f.created_at.isoformat(),
                }
                for f in files
            ],
        }


def ensure_db():
    import time
    attempts = int(os.getenv("DB_INIT_RETRIES", "15"))
    delay = float(os.getenv("DB_INIT_DELAY", "2.0"))
    last_err = None
    for _ in range(attempts):
        try:
            Base.metadata.create_all(bind=engine)
            return
        except Exception as e:
            last_err = e
            time.sleep(delay)
    # One final try or raise
    if last_err:
        raise last_err


def review_repo(repo_url: str, branch: str = "origin/main", workdir: Optional[str] = None, token: Optional[str] = None, mode: Optional[str] = None) -> dict:
    ensure_db()
    owner, name = parse_github_url(repo_url)
    gh_token = token or os.getenv("GITHUB_TOKEN")
    with next(get_db()) as db:  # type: ignore
        assert isinstance(db, Session)
        repo = db.execute(select(Repository).where(Repository.url == repo_url)).scalar_one_or_none()
        if not repo:
            repo = Repository(owner=owner, name=name, url=repo_url, last_reviewed_commit=None)
            db.add(repo)
            db.commit()
            db.refresh(repo)
        # Determine clone root directory
        clone_root = workdir or os.getenv("REPO_CLONE_DIR") or tempfile.gettempdir()
        try:
            os.makedirs(clone_root, exist_ok=True)
        except Exception:
            pass

        local = clone_or_fetch(repo_url, clone_root, token=gh_token)
        latest = get_latest_commit(local, branch=branch)

        base_sha = repo.last_reviewed_commit or latest
        changed = [] if repo.last_reviewed_commit is None else diff_changed_files(local, base_sha, latest)

        all_files = _all_repo_files(local)
        # Determine selection strategy based on mode
        sel_mode = (mode or os.getenv("DEFAULT_REVIEW_MODE", "full")).lower()
        if sel_mode == "full":
            files_to_check = all_files
        elif sel_mode == "recent":
            # If we have a base commit, prefer changed files; otherwise, a small subset
            files_to_check = changed if changed else all_files[:10]
        elif sel_mode == "smart":
            # Prefer changed files; else prioritize source files over docs
            code_exts = {".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".cpp", ".c", ".go", ".rs"}
            code_files = [f for f in all_files if os.path.splitext(f)[1] in code_exts]
            base_list = changed if changed else code_files
            files_to_check = base_list[:20] if len(base_list) > 20 else base_list
        else:
            # Fallback to prior behavior
            files_to_check = changed if changed else all_files
        # Safety limit: avoid processing massive repos entirely on first run
        max_files = int(os.getenv("MAX_FILES_REVIEW", "50"))
        if len(files_to_check) > max_files:
            files_to_check = files_to_check[:max_files]

        feedback_entries = []
        for rel in files_to_check:
            abs_path = os.path.join(local, rel)
            if not os.path.isfile(abs_path):
                continue
            try:
                with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                classification, feedback = classify_file_and_feedback(rel, content)
                append_as_comment(abs_path, classification, feedback)
                feedback_entries.append((rel, classification, feedback))
            except Exception as e:
                print(f"Skipping {rel}: {e}")

        review_branch = f"review/auto-{latest[:7]}"
        create_branch_commit_push(local, review_branch, f"Automated review for {latest}", token=gh_token)
        pr_url = create_pr_in_repo(local, review_branch, f"Automated Review {latest[:7]}", "Automated suggestions", token=gh_token)

        review = Review(repository_id=repo.id, commit_sha=latest, branch=review_branch, pr_url=pr_url)
        db.add(review)
        db.commit()

        for rel, classification, feedback in feedback_entries:
            db.add(FileFeedback(review_id=review.id, file_path=rel, classification=classification, feedback=feedback))
        db.commit()

        repo.last_reviewed_commit = latest
        db.add(repo)
        db.commit()

        return {
            "repository": repo.url,
            "commit": latest,
            "files_reviewed": len(feedback_entries),
            "pr_url": pr_url,
            "review_id": review.id,
            "mode": sel_mode,
        }


def _all_repo_files(local_repo: str) -> list[str]:
    files = []
    for root, _, filenames in os.walk(local_repo):
        # skip .git
        if "/.git" in root:
            continue
        for name in filenames:
            # Only text-like files
            if any(name.endswith(ext) for ext in [".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".cpp", ".c", ".go", ".rs", ".md", ".txt"]):
                rel = os.path.relpath(os.path.join(root, name), local_repo)
                files.append(rel)
    return files


def append_as_comment(path: str, classification: str, feedback: str) -> None:
    comment_prefix = "#" if path.endswith(".py") else "//"
    separator = f"\n{comment_prefix} --- Auto Review ({classification}) ---\n"
    with open(path, "a", encoding="utf-8") as f:
        f.write(separator)
        f.write(feedback if feedback.endswith("\n") else feedback + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Code Reviewer Service")
    parser.add_argument("--repo", type=str, help="GitHub repository URL")
    parser.add_argument("--health", action="store_true", help="Run health check and exit")
    parser.add_argument("--serve", action="store_true", help="Run FastAPI server")
    parser.add_argument("--branch", type=str, default="origin/main")
    parser.add_argument("--token", type=str, default=None, help="GitHub token (optional, else env GITHUB_TOKEN)")
    args = parser.parse_args()

    if args.health:
        print({"status": "ok"})
        sys.exit(0)

    if args.serve:
        uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
        sys.exit(0)

    if args.repo:
        summary = review_repo(args.repo, branch=args.branch, token=args.token)
        print(summary)
        sys.exit(0)

    parser.print_help()
