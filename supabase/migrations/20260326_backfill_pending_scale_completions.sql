-- Backfill: mark scale_completion_data rows as 'processed' where
-- completed_jobs already has them linked (scale_completion_id = scd.id).
-- These rows were synced correctly when the webhook arrived but the function
-- never flipped the status. This is a one-time cleanup.

UPDATE scale_completion_data scd
SET
  status       = 'processed',
  processed_at = now(),
  updated_at   = now()
WHERE
  scd.status = 'pending'
  AND EXISTS (
    SELECT 1
    FROM completed_jobs cj
    WHERE cj.scale_completion_id = scd.id
  );
