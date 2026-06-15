#!/usr/bin/env python3
"""Collect public GitHub facts used to render the profile README."""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


API = "https://api.github.com"


def github_json(path: str, token: str | None, params: dict[str, Any] | None = None) -> Any:
    query = ""
    if params:
        query = "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(
        API + path + query,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "VectorPeak-profile-readme-updater",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def public_repos(owner: str, token: str | None) -> list[dict[str, Any]]:
    repos: list[dict[str, Any]] = []
    page = 1
    while True:
        batch = github_json(
            f"/users/{owner}/repos",
            token,
            {"type": "owner", "sort": "updated", "per_page": 100, "page": page},
        )
        if not batch:
            break
        for repo in batch:
            if repo.get("fork"):
                continue
            repos.append(
                {
                    "name": repo["name"],
                    "stars": int(repo.get("stargazers_count") or 0),
                    "url": repo.get("html_url"),
                    "description": repo.get("description") or "",
                    "is_archived": bool(repo.get("archived")),
                }
            )
        page += 1
    return sorted(repos, key=lambda item: (-int(item["stars"]), item["name"].lower()))


def repo_from_search_item(item: dict[str, Any]) -> str:
    url = str(item.get("repository_url") or "")
    marker = "/repos/"
    if marker in url:
        return url.split(marker, 1)[1]
    return url.rsplit("/", 1)[-1]


def repo_stars(full_name: str, token: str | None) -> int:
    try:
        repo = github_json(f"/repos/{full_name}", token)
        return int(repo.get("stargazers_count") or 0)
    except Exception:
        return 0


def compact_repo_display(full_name: str) -> str:
    _, _, name = full_name.partition("/")
    special = {
        "vllm": "vLLM",
        "transformers": "Hugging Face Transformers",
        "qwen-code": "Qwen Code",
        "github-mcp-server": "GitHub MCP Server",
        "microsoft-agent-framework": "Microsoft Agent Framework",
        "litellm": "LiteLLM",
    }
    return special.get(name.lower(), name.replace("-", " ").replace("_", " ").title())


def merged_upstream_pr_summary(owner: str, token: str | None, min_stars: int) -> tuple[int, list[dict[str, Any]]]:
    query = f"author:{owner} type:pr is:merged -user:{owner}"
    data = github_json("/search/issues", token, {"q": query, "per_page": 100})
    items = list(data.get("items", []))
    repo_counts: dict[str, int] = {}
    repo_urls: dict[str, str] = {}
    repo_star_counts: dict[str, int] = {}

    for item in items:
        repo = repo_from_search_item(item)
        if repo not in repo_star_counts:
            time.sleep(0.05)
            repo_star_counts[repo] = repo_stars(repo, token)
        if repo_star_counts[repo] < min_stars:
            continue
        repo_counts[repo] = repo_counts.get(repo, 0) + 1
        repo_urls[repo] = "https://github.com/" + repo

    ordered = sorted(repo_counts, key=lambda repo: (-repo_star_counts[repo], -repo_counts[repo], repo.lower()))
    upstream_repos = [
        {
            "name": repo,
            "display": compact_repo_display(repo),
            "url": repo_urls[repo],
            "count": repo_counts[repo],
            "stars": repo_star_counts[repo],
        }
        for repo in ordered
    ]
    return sum(repo_counts.values()), upstream_repos


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect GitHub facts for the VectorPeak profile README.")
    parser.add_argument("--owner", default="VectorPeak")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--min-upstream-stars", type=int, default=500)
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    repos = public_repos(args.owner, token)
    merged_pr_count, upstream_repos = merged_upstream_pr_summary(args.owner, token, args.min_upstream_stars)
    facts = {
        "owner": args.owner,
        "public_project_count": len(repos),
        "public_repos": repos,
        "merged_pr_count": merged_pr_count,
        "min_upstream_repo_stars": args.min_upstream_stars,
        "upstream_repos": upstream_repos,
    }
    args.out.write_text(json.dumps(facts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
