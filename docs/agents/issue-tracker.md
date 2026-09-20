# Issue tracker: GitHub Issues

Issues for this repository live in GitHub Issues. Use the `gh` CLI for issue operations; it infers the repository from the current checkout.

## Conventions

- Create an issue with `gh issue create --title "..." --body "..."`.
- Read an issue with `gh issue view <number> --comments`.
- List issues with `gh issue list`, adding `--state` and `--label` filters as needed.
- Comment with `gh issue comment <number> --body "..."`.
- Add or remove labels with `gh issue edit <number> --add-label "..."` or `--remove-label "..."`.
- Close an issue with `gh issue close <number> --comment "..."`.

## Pull requests

PRs are not part of the triage request surface for this repository. The triage workflow should operate on GitHub Issues unless this setting is intentionally changed.
