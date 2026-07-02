---
name: trigger-profile-readme-workflow
description: Trigger and verify the VectorPeak/VectorPeak GitHub Actions workflow that regenerates the profile README. Use when the user asks to manually run, rerun, test, validate, or check the scheduled/dispatch profile README workflow, especially update-profile.yml, Update profile README, workflow_dispatch, schedule runs, or whether README regeneration creates and merges an automated PR.
---

# Trigger Profile README Workflow

## Overview

Use this skill to manually trigger the `VectorPeak/VectorPeak` profile README automation and verify whether it completed, created a PR, merged a PR, or exited because there was no README diff.

Default target:

- Repository: `VectorPeak/VectorPeak`
- Workflow file: `update-profile.yml`
- Branch: `main`
- Workflow name: `Update profile README`

## Quick Workflow

1. Confirm the workflow exists and inspect the latest runs when context is stale:

```powershell
gh workflow list --repo VectorPeak/VectorPeak
gh run list --repo VectorPeak/VectorPeak --workflow update-profile.yml --limit 10
```

2. Trigger the workflow manually:

```powershell
gh workflow run update-profile.yml --repo VectorPeak/VectorPeak --ref main
```

3. Capture the returned run URL or run ID. If only the URL is returned, the run ID is the final path segment.

4. Watch the run until completion:

```powershell
gh run watch <run-id> --repo VectorPeak/VectorPeak --exit-status
```

5. Inspect the commit step to distinguish a no-op run from a PR-producing run:

```powershell
gh run view <run-id> --repo VectorPeak/VectorPeak --log | Select-String -Pattern 'git diff --cached --quiet|git checkout -b|gh pr create|gh pr merge|https://github.com/VectorPeak/VectorPeak/pull|\[update-profile-|1 file changed|nothing to commit' -Context 0,2
```

6. Confirm latest PR and `main` state when the run creates a PR:

```powershell
gh pr list --repo VectorPeak/VectorPeak --state all --limit 5 --json number,title,state,headRefName,baseRefName,mergedAt,url,createdAt
gh api repos/VectorPeak/VectorPeak/commits/main --jq '{sha: .sha, message: .commit.message}'
```

## Interpretation

- Run success plus no PR URL in logs usually means the generated `README.md` matched the current file and the workflow exited at `git diff --cached --quiet && exit 0`.
- Run success plus a PR URL means the workflow created an `update-profile-*` branch, opened a PR, and attempted to merge it.
- A `HTTP 401: Bad credentials` error in `gh pr create` or `gh pr merge` usually means `WORKFLOW_PUSH_PAT` is invalid or expired.
- GitHub scheduled workflows may run later than the exact cron time. A delay of several minutes, and sometimes longer, is normal.
- The workflow currently has both `workflow_dispatch` and `schedule`, so it supports manual and automatic runs.

## Safety Notes

- Do not print secret values such as `WORKFLOW_PUSH_PAT` or `gh auth token`.
- Do not rewrite the workflow unless the user explicitly asks for a code change.
- If updating a secret is requested, use stdin-based `gh secret set` and verify only with `gh secret list`; never echo the token.
- If a run leaves orphan `update-profile-*` branches, list them first and ask before deleting unless the user explicitly requests cleanup.

## Common Commands

List recent scheduled and manual runs:

```powershell
gh run list --repo VectorPeak/VectorPeak --workflow update-profile.yml --limit 20
```

Open one run's structured status:

```powershell
gh run view <run-id> --repo VectorPeak/VectorPeak --json status,conclusion,event,headBranch,headSha,displayTitle,url,jobs
```

Check whether remote README contains a target phrase:

```powershell
gh api repos/VectorPeak/VectorPeak/contents/README.md --jq .content | ForEach-Object { [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($_)) } | Select-String -Pattern '<phrase>' -Context 0,1
```
