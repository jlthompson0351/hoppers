# TODO

## Immediate

- [ ] Commit and push the new root coordination docs if Justin wants this repo-standardization shared immediately.
- [ ] Run a fresh-session test after push to confirm the README-first startup flow works cleanly.

## Production rollout

- [ ] Activate the staged between-jobs re-zero warning during an approved restart window.
  - Runtime files are already staged on the production Pi.
  - After restart, verify the warning only appears between jobs when stable weight stays outside tolerance.
  - Verify `ZERO` clears the warning.

- [ ] Activate the staged configurable floor threshold + legacy floor signal behavior during the same approved window.
  - Verify `scale.zero_target_lb` persists in Settings.
  - Verify Job Target mode can use `0.0 lb` floor.
  - Verify Legacy mode holds the configured floor signal at/below the floor.

- [ ] Activate staged basket-dump counting during the same approved window.
  - Verify the mapped opto input counts one pulse per rising edge.
  - Verify completed-job payloads include `basket_dump_count`.

- [ ] Validate completed-job webhook delivery after restart.
  - Confirm lifecycle tracking, outbox retry, and payload fields work on a real job transition.
  - Confirm re-zero diagnostics are included in the completed-job payload.

## Repo workflow

- [ ] Keep root coordination docs current whenever repo state, rollout state, or blockers change.
- [ ] Keep folder orientation docs using names like `OVERVIEW.md` / `GUIDE.md` instead of new startup READMEs.

## Longer backlog

For detailed rollout notes, validation steps, and historical backlog context, see `docs/TODO_BACKLOG.md`.
