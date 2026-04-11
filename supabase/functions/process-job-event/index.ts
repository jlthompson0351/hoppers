import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, GET, DELETE, OPTIONS",
};

const ERP_TIMEZONE_CANDIDATES = [
  { label: "erp_utc_passthrough", timeZone: null },
  { label: "erp_assumed_america_chicago", timeZone: "America/Chicago" },
  { label: "erp_assumed_america_denver", timeZone: "America/Denver" },
] as const;

// All v1 fields + all v2 fields
const scaleCompletionSelect = `
  id,
  job_id,
  machine_id,
  job_end_record_time_set_utc,
  dump_count,
  basket_dump_count,
  total_processed_lbs,
  avg_weight_lbs,
  avg_cycle_time_ms,
  override_seen,
  override_count,
  final_set_weight_lbs,
  final_set_weight_unit,
  completed_at_utc,
  rezero_warning_seen,
  rezero_warning_reason,
  rezero_warning_weight_lbs,
  weight_warning,
  warning_severity,
  zero_drift_lbs,
  post_dump_rezero_applied,
  basket_dump_count_raw,
  basket_cycle_count,
  anomaly_detected,
  first_basket_dump_utc,
  last_basket_dump_utc,
  idle_gaps,
  avg_hopper_load_time_ms,
  avg_dump_time_ms,
  hopper_load_times
`;

interface StoredScaleRow {
  id: string;
  job_id: string;
  machine_id: string;
  job_end_record_time_set_utc: string | null;
  dump_count: number;
  basket_dump_count: number | null;
  total_processed_lbs: number;
  avg_weight_lbs: number;
  avg_cycle_time_ms: number;
  override_seen: boolean;
  override_count: number | null;
  final_set_weight_lbs: number | null;
  final_set_weight_unit: string | null;
  completed_at_utc: string;
  rezero_warning_seen: boolean;
  rezero_warning_reason: string | null;
  rezero_warning_weight_lbs: number | null;
  weight_warning: boolean;
  warning_severity: string | null;
  zero_drift_lbs: number | null;
  post_dump_rezero_applied: boolean;
  // v2 fields
  basket_dump_count_raw: number | null;
  basket_cycle_count: number | null;
  anomaly_detected: boolean | null;
  first_basket_dump_utc: string | null;
  last_basket_dump_utc: string | null;
  idle_gaps: unknown[] | null;
  avg_hopper_load_time_ms: number | null;
  avg_dump_time_ms: number | null;
  hopper_load_times: unknown[] | null;
}

const VERIFICATION_WINDOW_MS = 10 * 24 * 60 * 60 * 1000;

interface JobEventPayload {
  JobID: string;
  TimecardID?: string;
  TimecardLineID?: string;
  EmployeeID: string;
  EmployeeName: string;
  StartTime: string;
  EndTime: string;
  StepID: string;
  StepName: string;
  Location: string;
  Comments?: string;
  Customer?: string;
  JobQty?: string;
  LoadSize?: number | string;
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
    const supabaseServiceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
    const supabase = createClient(supabaseUrl, supabaseServiceKey);
    const receivedAt = new Date();

    const rawPayload: any = await req.json();
    const payload: JobEventPayload = {
      JobID: rawPayload.JobID || rawPayload.JobId || "",
      TimecardID: rawPayload.TimecardID || rawPayload.TimecardId,
      TimecardLineID: rawPayload.TimecardLineID || rawPayload.TimecardLineId,
      EmployeeID: rawPayload.EmployeeID || rawPayload.EmployeeId || "",
      EmployeeName: rawPayload.EmployeeName || rawPayload.EmployeeName || "",
      StartTime: rawPayload.StartTime || rawPayload.Starttime || "",
      EndTime: rawPayload.EndTime || rawPayload.Endtime || "",
      StepID: rawPayload.StepID || rawPayload.StepId || "",
      StepName: rawPayload.StepName || rawPayload.Stepname || "",
      Location: rawPayload.Location || rawPayload.location || "",
      Comments: rawPayload.Comments || rawPayload.comments,
      Customer: rawPayload.Customer || rawPayload.customer,
      JobQty: rawPayload.JobQty || rawPayload.jobQty,
      LoadSize: rawPayload.LoadSize ?? rawPayload.loadSize ?? rawPayload.loadsize,
    };

    const rawLoadSize = payload.LoadSize;
    const parsedLoadSize = rawLoadSize != null ? parseFloat(String(rawLoadSize)) : null;
    const loadSize = (parsedLoadSize !== null && !isNaN(parsedLoadSize)) ? parsedLoadSize : null;

    if (rawLoadSize != null && loadSize === null) {
      console.warn("Invalid LoadSize value received, storing null:", rawLoadSize);
    }

    const normalizedStartTime = normalizeErpTimestamp(payload.StartTime, receivedAt);
    const normalizedEndTime = normalizeErpTimestamp(payload.EndTime, receivedAt);
    const normalizedStartedAtIso = normalizedStartTime?.iso ?? receivedAt.toISOString();

    console.log("Received job event:", {
      jobId: payload.JobID,
      employee: payload.EmployeeName,
      step: payload.StepName,
      location: payload.Location,
      hasEndTime: !!payload.EndTime,
      normalizedStartedAtIso,
      erpTimeSource: normalizedStartTime?.timeSource ?? "record_created_at_fallback",
    });

    const { data: machineData } = await supabase
      .from("machines")
      .select("id, location_id")
      .eq("name", payload.Location)
      .maybeSingle();

    let factoryLocationId;
    if (machineData?.location_id) {
      factoryLocationId = machineData.location_id;
      console.log("Factory determined from machine:", payload.Location);
    } else {
      const { data: portlandLocation, error: locationError } = await supabase
        .from("locations")
        .select("id")
        .eq("name", "Portland")
        .single();

      if (locationError || !portlandLocation) {
        console.error("Error looking up Portland location:", locationError);
        throw new Error("Failed to lookup Portland location");
      }

      factoryLocationId = portlandLocation.id;
      console.log("Factory defaulted to Portland for non-machine location:", payload.Location);
    }

    const machineId = machineData?.id || null;
    const normalizedName = payload.EmployeeName.toLowerCase().trim();

    let { data: employeeData } = await supabase
      .from("employees")
      .select("id")
      .eq("normalized_name", normalizedName)
      .eq("location_id", factoryLocationId)
      .maybeSingle();

    let employeeUuid = null;

    if (!employeeData) {
      console.log("Creating new employee:", payload.EmployeeName, "at factory");

      const { data: newEmployee, error: createError } = await supabase
        .from("employees")
        .insert({
          name: payload.EmployeeName,
          normalized_name: normalizedName,
          location_id: factoryLocationId,
          is_active: true,
        })
        .select("id")
        .single();

      if (createError) {
        console.error("Failed to create employee:", createError);
      } else {
        employeeData = newEmployee;
        console.log("New employee created:", payload.EmployeeName);
      }
    }

    employeeUuid = employeeData?.id || null;

    console.log("Employee lookup complete:", {
      employee: payload.EmployeeName,
      employeeUuid: employeeUuid,
      locationCode: payload.Location,
      machineFound: !!machineId,
      machineId: machineId
    });

    const { data: insertedStep, error: insertError } = await supabase
      .from("job_steps")
      .insert({
        job_id: payload.JobID,
        timecard_id: payload.TimecardID || null,
        timecard_line_id: payload.TimecardLineID || null,
        employee_id: payload.EmployeeID,
        employee_name: payload.EmployeeName,
        employee_uuid: employeeUuid,
        step_id: payload.StepID,
        step_name: payload.StepName,
        location_id: factoryLocationId,
        location_code: payload.Location,
        machine_id: machineId,
        comments: payload.Comments || null,
        customer: payload.Customer || null,
        job_qty: payload.JobQty || null,
        load_size: loadSize,
        started_at: normalizedStartedAtIso,
        json_start_time: payload.StartTime || null,
        json_end_time: payload.EndTime || null,
        erp_started_at_utc: normalizedStartTime?.iso ?? null,
        erp_ended_at_utc: normalizedEndTime?.iso ?? null,
        erp_time_source: normalizedStartTime?.timeSource ?? "record_created_at_fallback",
        erp_source_timezone: normalizedStartTime?.sourceTimeZone ?? null,
      })
      .select()
      .single();

    if (insertError) {
      console.error("Error inserting job step:", insertError);
      throw new Error("Failed to create job step");
    }

    console.log("Job step recorded:", {
      jobId: payload.JobID,
      step: payload.StepName,
      employee: payload.EmployeeName,
    });

    await upsertJobReviewStateForStep(supabase, payload.JobID, normalizedStartedAtIso);

    if (loadSize !== null && machineId !== null && insertedStep?.id) {
      const idempotencyKey = `${payload.JobID}:${loadSize}:${insertedStep.id}`;
      const { error: enqueueErr } = await supabase
        .from("scale_webhook_events")
        .insert({
          job_step_id: insertedStep.id,
          job_id: payload.JobID,
          machine_id: machineId,
          load_size: loadSize,
          idempotency_key: idempotencyKey,
        });
      if (enqueueErr) {
        console.error("Failed to enqueue scale webhook event:", enqueueErr);
      } else {
        console.log("Scale webhook event enqueued for machine:", payload.Location);
      }
    }

    const isFinspStep = payload.StepName === "FINSP";

    if (isFinspStep) {
      console.log("FINSP detected - calculating job summary for job:", payload.JobID);

      const { data: allSteps, error: stepsError } = await supabase
        .from("job_steps")
        .select("*")
        .eq("job_id", payload.JobID)
        .order("started_at", { ascending: true });

      if (stepsError || !allSteps || allSteps.length === 0) {
        console.error("Error querying job steps:", stepsError);
        const finspTime = new Date();

        const limitedSummary = {
          started_at: finspTime.toISOString(),
          completed_at: finspTime.toISOString(),
          total_duration_minutes: 0,
          total_steps: 1,
          machines_used: machineId ? [payload.Location] : [],
          employees_involved: [payload.EmployeeName],
          steps_sequence: ["FINSP"],
        };

        const { data: existingSummary } = await supabase
          .from("completed_jobs")
          .select("id")
          .eq("job_id", payload.JobID)
          .maybeSingle();

        if (existingSummary) {
          await supabase
            .from("completed_jobs")
            .update(limitedSummary)
            .eq("job_id", payload.JobID);
        } else {
          await supabase.from("completed_jobs").insert({
            job_id: payload.JobID,
            ...limitedSummary,
          });
        }

        return new Response(
          JSON.stringify({
            success: true,
            message: "Job step recorded and FINSP summary created (limited data)",
            jobId: payload.JobID,
          }),
          {
            headers: { ...corsHeaders, "Content-Type": "application/json" },
            status: 200,
          }
        );
      }

      const firstStep = allSteps[0];
      const finspStep = allSteps[allSteps.length - 1];
      const startedAt = new Date(firstStep.started_at);
      const completedAt = new Date(finspStep.started_at);
      const totalDurationMs = completedAt.getTime() - startedAt.getTime();
      const totalDurationMinutes = Math.round(totalDurationMs / (1000 * 60));

      const machinesUsed = [...new Set(
        allSteps
          .filter(s => s.location_code && s.location_code.startsWith('PLP'))
          .map(s => s.location_code)
      )];

      const employeesInvolved = [...new Set(allSteps.map(s => s.employee_name))];
      const stepsSequence = allSteps.map(s => s.step_name);

      const { data: existingSummary } = await supabase
        .from("completed_jobs")
        .select("id")
        .eq("job_id", payload.JobID)
        .maybeSingle();

      const summaryPayload = {
        started_at: firstStep.started_at,
        completed_at: finspStep.started_at,
        total_duration_minutes: totalDurationMinutes,
        total_steps: allSteps.length,
        machines_used: machinesUsed,
        employees_involved: employeesInvolved,
        steps_sequence: stepsSequence,
      };

      if (existingSummary) {
        const { error: summaryUpdateError } = await supabase
          .from("completed_jobs")
          .update(summaryPayload)
          .eq("job_id", payload.JobID);

        if (summaryUpdateError) {
          console.error("Error updating existing job summary:", summaryUpdateError);
        } else {
          console.log("Job summary refreshed from FINSP:", {
            jobId: payload.JobID,
            totalSteps: allSteps.length,
            totalDuration: totalDurationMinutes,
            machines: machinesUsed,
          });
        }
      } else {
        const { error: summaryInsertError } = await supabase
          .from("completed_jobs")
          .insert({
            job_id: payload.JobID,
            ...summaryPayload,
          });

        if (summaryInsertError) {
          console.error("Error creating job summary:", summaryInsertError);
        } else {
          console.log("Job completed:", {
            jobId: payload.JobID,
            totalSteps: allSteps.length,
            totalDuration: totalDurationMinutes,
            machines: machinesUsed,
          });
        }
      }

      await syncCompletedJobWithLatestScaleData(supabase, payload.JobID, allSteps);

      return new Response(
        JSON.stringify({
          success: true,
          message: "Job step recorded and job completed (FINSP detected)",
          jobId: payload.JobID,
          totalSteps: allSteps.length,
          totalDurationMinutes: totalDurationMinutes,
        }),
        {
          headers: { ...corsHeaders, "Content-Type": "application/json" },
          status: 200,
        }
      );
    }

    return new Response(
      JSON.stringify({
        success: true,
        message: "Job step recorded",
        jobId: payload.JobID,
        step: payload.StepName,
      }),
      {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
        status: 200,
      }
    );
  } catch (error) {
    console.error("Error processing job event:", error);

    return new Response(
      JSON.stringify({
        success: false,
        error: error instanceof Error ? error.message : "Unknown error",
      }),
      {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
        status: 500,
      }
    );
  }
});

async function syncCompletedJobWithLatestScaleData(
  supabase: ReturnType<typeof createClient>,
  jobId: string,
  allSteps: Array<{ location_code?: string | null; started_at?: string | null }>,
) {
  const latestScaleData = await findBestScaleDataForCompletedJob(supabase, jobId, allSteps);

  if (!latestScaleData) {
    return;
  }

  const { error: syncError } = await supabase
    .from("completed_jobs")
    .update(buildCompletedJobScaleUpdate(latestScaleData))
    .eq("job_id", jobId);

  if (syncError) {
    console.error("Error syncing completed job with scale data:", syncError);
  }
}

async function findBestScaleDataForCompletedJob(
  supabase: ReturnType<typeof createClient>,
  jobId: string,
  allSteps: Array<{ location_code?: string | null; started_at?: string | null }>,
) {
  const { data: exactScaleData, error: exactLookupError } = await supabase
    .from("scale_completion_data")
    .select(scaleCompletionSelect)
    .eq("job_id", jobId)
    .order("job_end_record_time_set_utc", { ascending: false, nullsFirst: false })
    .order("completed_at_utc", { ascending: false })
    .limit(1)
    .maybeSingle();

  if (exactLookupError) {
    console.error("Error looking up scale completion data:", exactLookupError);
    return null;
  }

  if (exactScaleData) {
    return exactScaleData;
  }

  const anchorStep = findScaleAnchorStep(allSteps);

  if (!anchorStep?.location_code || !anchorStep.started_at) {
    return null;
  }

  const anchorTimeMs = new Date(anchorStep.started_at).getTime();

  if (!Number.isFinite(anchorTimeMs)) {
    return null;
  }

  const searchStart = new Date(anchorTimeMs - (2 * 60 * 1000)).toISOString();
  const searchEnd = new Date(anchorTimeMs + (2 * 60 * 1000)).toISOString();

  const { data: nearbyScaleRows, error: fallbackLookupError } = await supabase
    .from("scale_completion_data")
    .select(scaleCompletionSelect)
    .eq("machine_id", anchorStep.location_code)
    .neq("job_id", jobId)
    .gte("completed_at_utc", searchStart)
    .lte("completed_at_utc", searchEnd)
    .order("completed_at_utc", { ascending: false })
    .limit(25);

  if (fallbackLookupError) {
    console.error("Error looking up nearby scale completion data:", fallbackLookupError);
    return null;
  }

  if (!nearbyScaleRows || nearbyScaleRows.length === 0) {
    return null;
  }

  let closestScaleRow = nearbyScaleRows[0] as StoredScaleRow;
  let closestDistanceMs = Number.POSITIVE_INFINITY;

  for (const scaleRow of nearbyScaleRows) {
    const referenceAtMs = getScaleReferenceTimeMs(scaleRow as StoredScaleRow);
    if (!Number.isFinite(referenceAtMs)) {
      continue;
    }

    const distanceMs = Math.abs(referenceAtMs - anchorTimeMs);
    if (distanceMs < closestDistanceMs) {
      closestDistanceMs = distanceMs;
      closestScaleRow = scaleRow as StoredScaleRow;
    }
  }

  return closestScaleRow;
}

function findScaleAnchorStep(
  allSteps: Array<{ location_code?: string | null; started_at?: string | null }>,
) {
  const machineSteps = allSteps
    .filter((step) =>
      typeof step.location_code === "string" &&
      step.location_code.startsWith("PL") &&
      typeof step.started_at === "string" &&
      step.started_at.length > 0
    )
    .sort((a, b) => new Date(a.started_at!).getTime() - new Date(b.started_at!).getTime());

  return machineSteps[0] ?? null;
}

function buildCompletedJobScaleUpdate(scaleRow: StoredScaleRow) {
  return {
    // v1 fields
    scale_completion_id: scaleRow.id,
    scale_machine_id: scaleRow.machine_id,
    scale_completed_at: scaleRow.completed_at_utc,
    scale_dump_count: scaleRow.dump_count,
    scale_basket_dump_count: scaleRow.basket_dump_count,
    scale_total_processed_lbs: scaleRow.total_processed_lbs,
    scale_avg_weight_lbs: scaleRow.avg_weight_lbs,
    scale_avg_cycle_time_ms: scaleRow.avg_cycle_time_ms,
    scale_override_seen: scaleRow.override_seen,
    scale_override_count: scaleRow.override_count,
    scale_final_set_weight_lbs: scaleRow.final_set_weight_lbs,
    scale_final_set_weight_unit: scaleRow.final_set_weight_unit,
    scale_rezero_warning_seen: scaleRow.rezero_warning_seen ?? false,
    scale_rezero_warning_reason: scaleRow.rezero_warning_reason ?? null,
    scale_post_dump_rezero_applied: scaleRow.post_dump_rezero_applied ?? false,
    scale_weight_warning: scaleRow.weight_warning ?? false,
    scale_warning_severity: scaleRow.warning_severity ?? null,
    scale_zero_drift_lbs: scaleRow.zero_drift_lbs ?? scaleRow.rezero_warning_weight_lbs ?? null,
    // v2 fields
    basket_dump_count_raw: scaleRow.basket_dump_count_raw ?? null,
    basket_cycle_count: scaleRow.basket_cycle_count ?? null,
    anomaly_detected: scaleRow.anomaly_detected ?? null,
    first_basket_dump_utc: scaleRow.first_basket_dump_utc ?? null,
    last_basket_dump_utc: scaleRow.last_basket_dump_utc ?? null,
    idle_gaps: scaleRow.idle_gaps ?? [],
    avg_hopper_load_time_ms: scaleRow.avg_hopper_load_time_ms ?? null,
    avg_dump_time_ms: scaleRow.avg_dump_time_ms ?? null,
    hopper_load_times: scaleRow.hopper_load_times ?? [],
  };
}

function getScaleReferenceTimeMs(scaleRow: StoredScaleRow) {
  const referenceTime = scaleRow.job_end_record_time_set_utc ?? scaleRow.completed_at_utc;
  return new Date(referenceTime).getTime();
}

async function upsertJobReviewStateForStep(
  supabase: ReturnType<typeof createClient>,
  jobId: string,
  stepStartedAtIso: string,
) {
  const stepStartedAtMs = new Date(stepStartedAtIso).getTime();
  if (!Number.isFinite(stepStartedAtMs)) {
    return;
  }

  const verificationDueAtIso = new Date(stepStartedAtMs + VERIFICATION_WINDOW_MS).toISOString();

  const { data: existingState, error: stateLookupError } = await supabase
    .from("job_review_state")
    .select("last_step_seen_at, verification_review_status, manually_completed_at")
    .eq("job_id", jobId)
    .maybeSingle();

  if (stateLookupError) {
    console.error("Failed to look up job review state:", stateLookupError);
    return;
  }

  if (!existingState) {
    const { error: insertError } = await supabase
      .from("job_review_state")
      .insert({
        job_id: jobId,
        last_step_seen_at: stepStartedAtIso,
        verification_due_at: verificationDueAtIso,
      });

    if (insertError) {
      console.error("Failed to create job review state:", insertError);
    }
    return;
  }

  const existingLastStepMs = new Date(existingState.last_step_seen_at).getTime();
  const manualCompletedMs = existingState.manually_completed_at
    ? new Date(existingState.manually_completed_at).getTime()
    : Number.NEGATIVE_INFINITY;

  if (Number.isFinite(existingLastStepMs) && stepStartedAtMs < existingLastStepMs) {
    return;
  }

  const shouldClearReviewState =
    existingState.verification_review_status === "manually_completed"
      ? stepStartedAtMs > manualCompletedMs
      : !Number.isFinite(existingLastStepMs) || stepStartedAtMs > existingLastStepMs;

  const updatePayload: Record<string, unknown> = {
    last_step_seen_at: stepStartedAtIso,
    verification_due_at: verificationDueAtIso,
  };

  if (shouldClearReviewState) {
    updatePayload.verification_review_status = null;
    updatePayload.verification_flagged_at = null;
    updatePayload.manually_completed_at = null;
    updatePayload.manually_completed_by = null;
    updatePayload.review_notes = null;
  }

  const { error: updateError } = await supabase
    .from("job_review_state")
    .update(updatePayload)
    .eq("job_id", jobId);

  if (updateError) {
    console.error("Failed to update job review state:", updateError);
  }
}

interface NormalizedErpTimestamp {
  iso: string;
  timeSource: string;
  sourceTimeZone: string | null;
}

function normalizeErpTimestamp(
  rawTimestamp: string | undefined,
  referenceAt: Date,
): NormalizedErpTimestamp | null {
  if (!rawTimestamp || rawTimestamp.trim().length === 0) {
    return null;
  }

  const candidates: Array<NormalizedErpTimestamp & { scoreMs: number }> = [];
  const referenceMs = referenceAt.getTime();

  const utcCandidate = new Date(rawTimestamp);
  if (Number.isFinite(utcCandidate.getTime())) {
    candidates.push({
      iso: utcCandidate.toISOString(),
      timeSource: "erp_utc_passthrough",
      sourceTimeZone: "UTC",
      scoreMs: Math.abs(utcCandidate.getTime() - referenceMs),
    });
  }

  for (const candidate of ERP_TIMEZONE_CANDIDATES) {
    if (!candidate.timeZone) {
      continue;
    }

    const wallClockDate = parseWallClockInTimeZone(rawTimestamp, candidate.timeZone);
    if (!wallClockDate) {
      continue;
    }

    candidates.push({
      iso: wallClockDate.toISOString(),
      timeSource: candidate.label,
      sourceTimeZone: candidate.timeZone,
      scoreMs: Math.abs(wallClockDate.getTime() - referenceMs),
    });
  }

  if (candidates.length === 0) {
    return null;
  }

  candidates.sort((a, b) => a.scoreMs - b.scoreMs);

  return {
    iso: candidates[0].iso,
    timeSource: candidates[0].timeSource,
    sourceTimeZone: candidates[0].sourceTimeZone,
  };
}

function parseWallClockInTimeZone(rawTimestamp: string, timeZone: string): Date | null {
  const match = rawTimestamp.trim().match(
    /^(\d{4})-(\d{2})-(\d{2})[T\s](\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,3}))?)?/,
  );

  if (!match) {
    return null;
  }

  const [, year, month, day, hour, minute, second = "0", millisecond = "0"] = match;
  const parsedMillisecond = Number(millisecond.padEnd(3, "0"));
  const baseUtcMs = Date.UTC(
    Number(year),
    Number(month) - 1,
    Number(day),
    Number(hour),
    Number(minute),
    Number(second),
    parsedMillisecond,
  );

  let adjustedUtcMs = baseUtcMs;
  for (let i = 0; i < 3; i += 1) {
    const offsetMinutes = getTimeZoneOffsetMinutes(new Date(adjustedUtcMs), timeZone);
    adjustedUtcMs = baseUtcMs - (offsetMinutes * 60 * 1000);
  }

  const parsedDate = new Date(adjustedUtcMs);
  return Number.isFinite(parsedDate.getTime()) ? parsedDate : null;
}

function getTimeZoneOffsetMinutes(date: Date, timeZone: string): number {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).formatToParts(date);

  const values = Object.fromEntries(
    parts
      .filter((part) => part.type !== "literal")
      .map((part) => [part.type, part.value]),
  );

  const zonedUtcMs = Date.UTC(
    Number(values.year),
    Number(values.month) - 1,
    Number(values.day),
    Number(values.hour),
    Number(values.minute),
    Number(values.second),
  );

  return (zonedUtcMs - date.getTime()) / (60 * 1000);
}
