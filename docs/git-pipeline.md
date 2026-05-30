# ATMP Git Pipeline

This repo is a private working copy of `harry0703/MoneyPrinterTurbo`.

## Remote Layout

```text
origin
  private repo: https://github.com/auronpep/ATMP.git
  push target: yes

upstream
  public source: https://github.com/harry0703/MoneyPrinterTurbo.git
  push target: DISABLED
```

The public repo stays fetch-only. All private work lands in `origin`.

## Daily Work

```powershell
git status --short --branch
git switch -c feature/my-change
.\scripts\Run-CI.ps1
git add <files>
git commit -m "Describe the change"
git push -u origin feature/my-change
```

Open a pull request into `main` when the branch is ready.

## Main Branch Rule

`main` should always be runnable. Before merging to `main`, the CI check should pass:

```powershell
.\scripts\Run-CI.ps1
```

GitHub Actions runs the same command on pushes and pull requests.

GitHub branch protection/ruleset enforcement for this private personal repo is currently unavailable through the API on this account plan. Treat CI as mandatory by team practice until GitHub branch protection is available.

## Updating From Upstream

```powershell
git fetch upstream
git log --oneline main..upstream/main
git merge upstream/main
.\scripts\Run-CI.ps1
git push origin main
```

If upstream changes conflict with private ATMP setup files, keep local project setup intentional and resolve conflicts file by file.

## Collaborators

Admin collaborator invitations are tracked in `tasks/todo.md`. Pending invitations do not appear as active collaborators until each user accepts.
