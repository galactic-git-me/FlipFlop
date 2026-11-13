# Merged branch worktree cleanup

The `Clean up merged branch worktree` workflow runs when a pull request is merged into `dev` or `main`. It must run on a Windows self-hosted GitHub Actions runner on the machine that owns the local FlipFlop worktrees; GitHub-hosted runners cannot access `C:\Users\mclar\CODING`.

## Runner configuration

- Register a repository-scoped Windows runner with the label `flipflop-coding-cleanup`.
- Set the repository Actions variable `FLIPFLOP_WORKTREE_REPO` to the primary FlipFlop checkout, normally `C:\Users\mclar\CODING\FlipFlop`.
- Run the runner under the Windows account that owns the checkout and worktrees.

This runner executes repository workflow code on the local machine. Keep it repository-scoped, use GitHub's runner service account with access only to the required checkout, and do not enable it for workflows triggered by untrusted fork pull requests.

## Removal safeguards

The cleanup script removes a worktree only when its registered branch and HEAD exactly match the merged PR, it is below the `CODING` directory, and Git reports no tracked or untracked changes. It uses `git worktree remove` without `--force`; locked, dirty, ambiguous, moved, or otherwise unremovable worktrees are preserved. It never removes the primary checkout or deletes the remote branch.

Only linked Git worktrees registered with the primary checkout are candidates. Independent clones, dated backups, release snapshots, and folders from other projects are not removed by this workflow.
