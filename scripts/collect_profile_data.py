#!/usr/bin/env python3
"""Collect public GitHub facts used to render the profile README."""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


API = "https://api.github.com"

LANDED_MERGED_PR_OVERRIDES: list[dict[str, Any]] = [
    {
        "author": "VectorPeak",
        "repository_url": f"{API}/repos/pytorch/pytorch",
        "html_url": "https://github.com/pytorch/pytorch/pull/188830",
        "number": 188830,
        "title": "Fix test name detection for Git-style paths",
        "state": "closed",
        "landed_status": "closed_but_landed",
        "repo_stars": 101294,
    },
]


def github_json(path: str, token: str | None, params: dict[str, Any] | None = None, retries: int = 3) -> Any:
    query = ""
    if params:
        query = "?" + urllib.parse.urlencode(params)
    url = API + path + query
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "VectorPeak-profile-readme-updater",
        **({"Authorization": f"Bearer {token}"} if token else {}),
    }
    for attempt in range(retries + 1):
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
                if isinstance(data, dict) and data.get("incomplete_results"):
                    raise RuntimeError(f"GitHub search returned incomplete results for {path}")
                return data
        except urllib.error.HTTPError as exc:
            retry_after = exc.headers.get("Retry-After")
            should_retry = exc.code in {403, 429, 500, 502, 503, 504}
            if attempt >= retries or not should_retry:
                body = exc.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"GitHub API request failed: {exc.code} {url}: {body}") from exc
            delay = int(retry_after) if retry_after and retry_after.isdigit() else min(2 ** attempt, 10)
            time.sleep(delay)
        except urllib.error.URLError as exc:
            if attempt >= retries:
                raise RuntimeError(f"GitHub API request failed: {url}: {exc}") from exc
            time.sleep(min(2 ** attempt, 10))
    raise RuntimeError(f"GitHub API request failed after retries: {url}")


def public_repos(owner: str, token: str | None, excluded_names: set[str]) -> list[dict[str, Any]]:
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
            if repo.get("fork") or repo["name"].lower() in excluded_names:
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
    repo = github_json(f"/repos/{full_name}", token)
    return int(repo.get("stargazers_count") or 0)


def compact_repo_display(full_name: str) -> str:
    _, _, name = full_name.partition("/")
    special = {
        "vllm": "vLLM",
        "transformers": "Hugging Face Transformers",
        "hivemind": "HiveMind",
        "lightrag": "LightRAG",
        "openhands": "OpenHands",
        "langgraph": "LangGraph",
        "llama.cpp": "llama.cpp",
        "mcp-go": "mcp-go",
        "mcp-go-sdk": "mcp-go-sdk",
        "qwen-agent": "Qwen-Agent",
        "agentscope": "AgentScope",
        "inspect_ai": "Inspect AI",
        "inspect-ai": "Inspect AI",
        "google-genai": "Google GenAI",
        "python-genai": "Python GenAI",
        "qwen-code": "Qwen Code",
        "github-mcp-server": "GitHub MCP Server",
        "agent-framework": "Microsoft Agent Framework",
        "agents": "LiveKit Agents",
        "microsoft-agent-framework": "Microsoft Agent Framework",
        "litellm": "LiteLLM",
        "pytorch": "PyTorch",
    }
    if name.lower() in special:
        return special[name.lower()]
    if any(char.isupper() for char in name) or "." in name:
        return name.replace("-", " ").replace("_", " ")
    return name.replace("-", " ").replace("_", " ").title()


def contribution_area(full_name: str) -> str:
    name = full_name.rsplit("/", 1)[-1].lower()
    if name in {
        "vllm",
        "transformers",
        "mooncake",
        "triton",
        "verl",
        "sglang",
        "flashinfer",
        "lmcache",
        "litellm",
        "pytorch",
        "ktransformers",
    }:
        return "AI infrastructure / model systems"
    if name in {
        "qwen-code",
        "openclaw",
        "astrbot",
        "pydantic-ai",
        "qwenpaw",
        "mem0",
        "agent-framework",
        "agents",
        "microsoft-agent-framework",
        "github-mcp-server",
        "model-context-protocol",
        "mcp-go",
        "mcp-go-sdk",
        "agentscope",
        "agno",
        "ag-ui",
        "inspect_ai",
        "inspect-ai",
        "cline",
        "hivemind",
        "openhands",
    }:
        return "Agent frameworks / protocols / evals"
    if name in {"dify", "ragflow", "langchain", "llamaindex", "google-genai", "python-genai"}:
        return "Applied AI / RAG / observability"
    if "recommender" in name or "recbole" in name:
        return "Recommender systems"
    return "Applied AI / RAG / observability"


def pr_key(item: dict[str, Any]) -> tuple[str, int]:
    return repo_from_search_item(item).lower(), int(item.get("number") or 0)


def merge_landed_overrides(owner: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged = list(items)
    seen = {pr_key(item) for item in merged}
    for override in LANDED_MERGED_PR_OVERRIDES:
        if str(override.get("author", "")).lower() != owner.lower():
            continue
        item = {key: value for key, value in override.items() if key not in {"author", "repo_stars"}}
        key = pr_key(item)
        if key in seen:
            continue
        merged.append(item)
        seen.add(key)
    return merged


def override_repo_stars(item: dict[str, Any]) -> int | None:
    key = pr_key(item)
    for override in LANDED_MERGED_PR_OVERRIDES:
        if key == pr_key(override):
            stars = override.get("repo_stars")
            return int(stars) if stars is not None else None
    return None


def merged_upstream_pr_summary(owner: str, token: str | None, min_stars: int, max_pages: int) -> tuple[int, list[dict[str, Any]], list[dict[str, Any]]]:
    query = f"author:{owner} type:pr is:merged -user:{owner}"
    items: list[dict[str, Any]] = []
    total_count = 0
    for page in range(1, max_pages + 1):
        data = github_json("/search/issues", token, {"q": query, "per_page": 100, "page": page})
        total_count = int(data.get("total_count") or 0)
        batch = list(data.get("items", []))
        items.extend(batch)
        if len(items) >= total_count or not batch:
            break
    if total_count > len(items):
        print(f"warning: merged PR search returned {len(items)} of {total_count} results; increase --max-search-pages if needed")
    items = merge_landed_overrides(owner, items)
    repo_counts: dict[str, int] = {}
    repo_urls: dict[str, str] = {}
    repo_star_counts: dict[str, int] = {}
    upstream_prs: list[dict[str, Any]] = []

    for item in items:
        repo = repo_from_search_item(item)
        if repo not in repo_star_counts:
            override_stars = override_repo_stars(item)
            if override_stars is None:
                time.sleep(0.05)
                repo_star_counts[repo] = repo_stars(repo, token)
            else:
                repo_star_counts[repo] = override_stars
        if repo_star_counts[repo] < min_stars:
            continue
        repo_counts[repo] = repo_counts.get(repo, 0) + 1
        repo_urls[repo] = "https://github.com/" + repo
        upstream_prs.append(
            {
                "repo": repo,
                "repo_display": compact_repo_display(repo),
                "repo_display_en": compact_repo_display(repo),
                "repo_display_zh": compact_repo_display(repo),
                "area": contribution_area(repo),
                "repo_url": repo_urls[repo],
                "repo_stars": repo_star_counts[repo],
                "number": item.get("number"),
                "title": item.get("title") or "",
                "url": item.get("html_url"),
            }
        )

    ordered = sorted(repo_counts, key=lambda repo: (-repo_star_counts[repo], -repo_counts[repo], repo.lower()))
    upstream_repos = [
        {
            "name": repo,
            "display": compact_repo_display(repo),
            "display_en": compact_repo_display(repo),
            "display_zh": compact_repo_display(repo),
            "url": repo_urls[repo],
            "count": repo_counts[repo],
            "stars": repo_star_counts[repo],
        }
        for repo in ordered
    ]
    upstream_prs.sort(key=lambda item: (-int(item["repo_stars"]), str(item["repo"]).lower(), -int(item.get("number") or 0)))
    return sum(repo_counts.values()), upstream_repos, upstream_prs


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect GitHub facts for the VectorPeak profile README.")
    parser.add_argument("--owner", default="VectorPeak")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--min-upstream-stars", type=int, default=100)
    parser.add_argument("--max-search-pages", type=int, default=10)
    parser.add_argument("--exclude-repo", action="append", default=[], help="Repository name to exclude from profile project counts.")
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    excluded_names = {args.owner.lower(), *(name.lower() for name in args.exclude_repo)}
    repos = public_repos(args.owner, token, excluded_names)
    merged_pr_count, upstream_repos, upstream_prs = merged_upstream_pr_summary(args.owner, token, args.min_upstream_stars, args.max_search_pages)
    facts = {
        "owner": args.owner,
        "public_project_count": len(repos),
        "public_repos": repos,
        "merged_pr_count": merged_pr_count,
        "min_upstream_repo_stars": args.min_upstream_stars,
        "upstream_repos": upstream_repos,
        "upstream_prs": upstream_prs,
    }
    args.out.write_text(json.dumps(facts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
