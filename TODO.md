# TODO

## Current Cross-Project Feature Support
- [ ] Support the next public machine-kiosk enhancement across the linked manufacturing system.
- [ ] Confirm the completed-job webhook payload and downstream storage still expose the manager-facing metrics needed by the frontend kiosk:
  - [ ] average basket weight
  - [ ] set weight
  - [ ] average cycle time
  - [ ] weight drift warning
- [ ] Verify naming/units for the fields mirrored downstream into Supabase `completed_jobs`.
- [ ] Keep the distinction clear between Hopper as the scale/runtime source and Supabase as the broader backend/storage layer.

## Data / Product Alignment
- [ ] Document Hopper's role in the three-project chain: ERP/job context + machine set weight flow + scale completion output → Supabase → Frontend kiosk/dashboard views.
- [ ] Confirm what Hopper emits or derives for:
  - [ ] average basket weight
  - [ ] final set weight
  - [ ] final set weight unit
  - [ ] average cycle time
  - [ ] basket dump count
  - [ ] weight drift warning / severity / drift amount
- [ ] Note any gaps between what Hopper currently emits and what the frontend wants to display.

## Operational Reminder
- [ ] Do not blur pushed code with staged-on-Pi or live runtime state.
- [ ] Preserve current rollout truth while documenting the next frontend-linked feature work.

- [ ] **Feature: Basket Dump Webhook Integration** (Added: 2026-03-24)
  - Context: We are now counting "basket dumps" via the Pi (IN1 signal). At the end of a job, the scale data sent via webhook needs to use these basket dumps instead of (or alongside) "hopper dumps".
  - Goal: Correlate the basket dump signal with the scale weight data to confirm which basket dumps were *actual* parts dumps versus noise.

## Next Priority (2026-03-25)
- [ ] Integrate opto CH1 basket dump signal into the main acquisition loop
- [ ] Correlate opto dumps with weight-curve dumps — two signals confirming one real basket dump
- [ ] Update completed-job webhook payload to use opto-based (or opto+weight correlated) basket_dump_count
- [ ] Debounce logic: two opto transitions within ~30s = one dump event
- [ ] Consider: opto + weight together = confirmed parts dump vs opto alone = mechanical rotation
- [ ] Convert opto monitor from nohup script to systemd service (survives reboot)
  - **Mechanical Constraints to Handle:**
    1. **Double-Dump Shake**: The basket dumps twice rapidly to shake off stuck painted parts. The code must group these into a single "logical" dump event (debounce).
    2. **Empty Startup Dumps**: At the start of an order, the system dumps the baskets empty before the hopper drops any parts. We must filter these out.
    3. **Carousel FIFO Delay**: The system has a 2-basket carousel. Sequence: Hopper fills Basket 1 -> Carousel rotates Basket 1 into paint booth -> Hopper fills Basket 2 -> Basket 1 comes out and dumps onto conveyor. This means there is an offset between a hopper weight drop and the corresponding basket dump. The code needs a queue to track which basket has parts and which is empty.
    4. **Manual/Maintenance Dumps**: Maintenance may manually trigger a basket dump (empty or full) outside of normal operation. Examples:
       - Dumping an empty basket during troubleshooting.
       - Overfilled basket (hopper dropped too many parts, can't paint them) — maintenance manually dumps excess parts before resuming.
       - These are NOT production dumps and should be flagged or filtered. Possible detection: dump happens outside of the normal hopper-fill → carousel → paint → dump cycle, or the weight doesn't match expected hopper drop.
