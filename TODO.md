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
