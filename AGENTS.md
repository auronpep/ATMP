## Workflow Orchestration

### 1. Plan Mode Default
- Enter plan mode for any non-trivial task with 3 or more steps or architectural decisions.
- If something goes sideways, stop and re-plan immediately.
- Use plan mode for verification steps, not just building.
- Write detailed specs upfront to reduce ambiguity.

### 2. Subagent Strategy
- Use subagents liberally to keep the main context window clean.
- Offload research, exploration, and parallel analysis to subagents.
- For complex problems, throw more compute at it via subagents.
- One task per subagent for focused execution.

### 3. Self-Improvement Loop
- After any correction from the user, update `tasks/lessons.md` with the pattern.
- Write rules that prevent the same mistake.
- Iterate on these lessons until mistake rate drops.
- Review lessons at session start for relevant project context.

### 4. Verification Before Done
- Never mark a task complete without proving it works.
- Diff behavior between main and your changes when relevant.
- Ask whether a staff engineer would approve the result.
- Run tests, check logs, and demonstrate correctness.

### 5. Demand Elegance, Balanced
- For non-trivial changes, pause and ask whether there is a more elegant way.
- If a fix feels hacky, rework toward the elegant solution.
- Skip this for simple, obvious fixes.
- Challenge your own work before presenting it.

### 6. Autonomous Bug Fixing
- When given a bug report, fix it without asking for hand-holding.
- Point at logs, errors, and failing tests, then resolve them.
- Avoid context switching back to the user when the next debugging step is discoverable.
- Fix failing CI tests without needing to be told how.

## Task Management

1. Write the plan to `tasks/todo.md` with checkable items.
2. Mark items complete as work progresses.
3. Explain changes at a high level as steps are completed.
4. Add a review section to `tasks/todo.md`.
5. Update `tasks/lessons.md` after user corrections.

## Core Principles

- Simplicity first: make every change as simple as possible and impact minimal code.
- No laziness: find root causes, avoid temporary fixes, and use senior developer standards.
- Minimal impact: touch only what is necessary and avoid introducing bugs.

## Global Git Safety

- Never push to public repositories. Public upstream repositories are read-only reference sources unless the user explicitly authorizes an upstream contribution in that exact turn.
- Before any `git push`, GitHub PR creation, release, tag push, branch mutation, or remote write, verify the target remote and repository visibility. Push only to repositories confirmed private or explicitly approved by the user.
- Do not configure public upstream repositories as push targets. For public upstream clones, remove or disable `pushurl` and keep them fetch-only.
- Fork or patch work belongs in a user-controlled private fork or local branch by default. Never assume it is acceptable to push to public source projects such as `openclaw/openclaw`.

## GitHub Issue Workflow for Codex CLI

When using Codex CLI for debugging and planning, use the repository-local workflow docs:

- `~/.codex/CODEX_GITHUB_SETUP.md` for environment and permissions setup.
- `~/.codex/BUG_REPORTING.md` for bug tracking.
- `~/.codex/IDEA_CAPTURE.md` for features and follow-up ideas.

Bug reporting and idea capture rules use the same ownership allowlist as before: `VoteWood`, `erewhonsgroup`, and `auronpep`.

## Codex CLI Operations

Use the global `codex-operator` skill at `C:\Users\JesusLovesMe\.codex\skills\codex-operator\SKILL.md` before running Codex CLI commands. Verify current local state with:

```powershell
codex --version
codex --help
codex exec --help
codex review --help
codex mcp list
```

Use `codex exec` for non-interactive runs, `codex review` for code review, and `-C` or `--cd` for the target project. Codex `--profile` means a Codex config profile, not an OpenClaw profile. Do not run dangerous sandbox bypasses, credential changes, MCP or plugin mutations, `codex logout`, or `codex apply` unless explicitly requested.

## PowerShell Operations

Use the global `powershell-operator` skill at `C:\Users\JesusLovesMe\.codex\skills\powershell-operator\SKILL.md` before running non-trivial PowerShell, editing `.ps1` files, working across AM PCs, or changing shell/profile/remoting state.

Prefer `pwsh -NoProfile -File <script.ps1>` for scripts and single-quoted `pwsh -NoProfile -Command '<command>'` for short checks from a PowerShell host. Use `powershell.exe` only for Windows PowerShell 5.1 compatibility.

Quote Windows paths, use `-LiteralPath` for file operations, check `$LASTEXITCODE` after native executables, and never perform recursive delete or move until the resolved target path is proven inside the intended workspace.

AM PC mapping:

- PC1: `JESUSISKING`
- PC2: `PRAISEJESUS`
- PC3: `HAILKINGJESUS`
- PC4: `JESUSISLORD`

Use each PC's wrapper scripts and keep `scripts\AM.Sessions.PC*.ps1` segmented.
