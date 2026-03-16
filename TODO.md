# TODO

## Immediate

- [ ] Finish the repo/doc cleanup so project state, rollout state, and backup/image notes stop contradicting each other.
- [ ] Keep the already-staged hopper updates clearly documented so they are not lost or accidentally represented as live.
- [ ] Prepare a clean future runbook for Pi settings scrape + image capture + clone prep.
- [ ] Push cleanup changes only when explicitly approved.

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

## Backup / clone-image prep

- [ ] Refresh backup/inventory docs so they reflect the latest known baseline artifacts and the still-pending full image capture.
- [ ] Create a single runbook for:
  - scraping current Pi settings/state
  - confirming staged vs live rollout state
  - capturing a fresh baseline bundle
  - capturing a cloneable full image
  - handling post-clone identity cleanup for a second scale

## Repo workflow

- [ ] Keep root coordination docs current whenever repo state, rollout state, or blockers change.
- [ ] Keep folder orientation docs using names like `OVERVIEW.md` / `GUIDE.md` instead of new startup READMEs.

## Longer backlog

For detailed rollout notes, validation steps, and historical backlog context, see `docs/TODO_BACKLOG.md`.
