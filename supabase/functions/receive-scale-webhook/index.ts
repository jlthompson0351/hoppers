import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, GET, DELETE, OPTIONS",
};

const sel = `
  id,schema_version,job_id,line_id,machine_id,
  job_start_record_time_set_utc,job_end_record_time_set_utc,
  first_erp_timestamp_utc,last_erp_timestamp_utc,
  cycle_count,dump_count,
  basket_dump_count,basket_dump_count_raw,basket_cycle_count,
  anomaly_detected,first_basket_dump_utc,last_basket_dump_utc,
  idle_gaps,avg_hopper_load_time_ms,avg_dump_time_ms,hopper_load_times,
  dump_events,total_processed_lbs,avg_weight_lbs,avg_cycle_time_ms,
  override_seen,override_count,override_weight_lbs,
  final_set_weight_lbs,final_set_weight_unit,
  rezero_warning_seen,rezero_warning_reason,
  rezero_warning_weight_lbs,rezero_warning_threshold_lbs,
  post_dump_rezero_applied,post_dump_rezero_last_apply_utc,
  weight_warning,warning_severity,zero_drift_lbs,
  completed_at_utc,status
`;

type R = Record<string, unknown> & {
  schema_version?: unknown; job_id?: unknown; jobId?: unknown;
  line_id?: unknown; lineId?: unknown; machine_id?: unknown; machineId?: unknown;
  job_start_record_time_set_utc?: unknown; jobStartRecordTimeSetUtc?: unknown;
  job_end_record_time_set_utc?: unknown; jobEndRecordTimeSetUtc?: unknown;
  first_erp_timestamp_utc?: unknown; firstErpTimestampUtc?: unknown;
  last_erp_timestamp_utc?: unknown; lastErpTimestampUtc?: unknown;
  cycle_count?: unknown; cycleCount?: unknown;
  dump_count?: unknown; dumpCount?: unknown;
  basket_dump_count?: unknown; basketDumpCount?: unknown;
  basket_dump_count_raw?: unknown; basketDumpCountRaw?: unknown;
  basket_cycle_count?: unknown; basketCycleCount?: unknown;
  anomaly_detected?: unknown; anomalyDetected?: unknown;
  first_basket_dump_utc?: unknown; firstBasketDumpUtc?: unknown;
  last_basket_dump_utc?: unknown; lastBasketDumpUtc?: unknown;
  idle_gaps?: unknown; idleGaps?: unknown;
  avg_hopper_load_time_ms?: unknown; avgHopperLoadTimeMs?: unknown;
  avg_dump_time_ms?: unknown; avgDumpTimeMs?: unknown;
  hopper_load_times?: unknown; hopperLoadTimes?: unknown;
  dump_events?: unknown; dumpEvents?: unknown;
  total_processed_lbs?: unknown; totalProcessedLbs?: unknown;
  avg_weight_lbs?: unknown; avgWeightLbs?: unknown;
  avg_cycle_time_ms?: unknown; avgCycleTimeMs?: unknown;
  override_seen?: unknown; overrideSeen?: unknown;
  override_count?: unknown; overrideCount?: unknown;
  override_weight_lbs?: unknown; overrideWeightLbs?: unknown;
  final_set_weight_lbs?: unknown; finalSetWeightLbs?: unknown;
  final_set_weight_unit?: unknown; finalSetWeightUnit?: unknown;
  rezero_warning_seen?: unknown; rezeroWarningSeen?: unknown;
  rezero_warning_reason?: unknown; rezeroWarningReason?: unknown;
  rezero_warning_weight_lbs?: unknown; rezeroWarningWeightLbs?: unknown;
  rezero_warning_threshold_lbs?: unknown; rezeroWarningThresholdLbs?: unknown;
  post_dump_rezero_applied?: unknown; postDumpRezeroApplied?: unknown;
  post_dump_rezero_last_apply_utc?: unknown; postDumpRezeroLastApplyUtc?: unknown;
  completed_at_utc?: unknown; completedAtUtc?: unknown;
  weight_warning?: unknown; weightWarning?: unknown;
  warning_severity?: unknown; warningSeverity?: unknown;
  zero_drift_lbs?: unknown; zeroDriftLbs?: unknown;
  zero_health?: unknown; zeroHealth?: unknown;
  zero_health_severity?: unknown; zeroHealthSeverity?: unknown;
  zero_health_drift_lbs?: unknown; zeroHealthDriftLbs?: unknown;
  drift_lbs?: unknown; driftLbs?: unknown;
};

interface N {
  schemaVersion: number; hasExplicitSchemaVersion: boolean; usesExpandedContract: boolean;
  jobId: string | null; lineId: string | null; machineId: string | null;
  jobStartRecordTimeSetUtc: string | null; jobEndRecordTimeSetUtc: string | null;
  firstErpTimestampUtc: string | null; lastErpTimestampUtc: string | null;
  cycleCount: number | null; dumpCount: number | null;
  basketDumpCount: number | null; basketDumpCountRaw: number | null;
  basketCycleCount: number | null; anomalyDetected: boolean | null;
  firstBasketDumpUtc: string | null; lastBasketDumpUtc: string | null;
  idleGaps: unknown[]; avgHopperLoadTimeMs: number | null; avgDumpTimeMs: number | null;
  hopperLoadTimes: unknown[]; dumpEvents: unknown[];
  totalProcessedLbs: number | null; avgWeightLbs: number | null; avgCycleTimeMs: number | null;
  overrideSeen: boolean; overrideCount: number | null; overrideWeightLbs: number | null;
  finalSetWeightLbs: number | null; finalSetWeightUnit: string | null;
  rezeroWarningSeen: boolean; rezeroWarningReason: string | null;
  rezeroWarningWeightLbs: number | null; rezeroWarningThresholdLbs: number | null;
  postDumpRezeroApplied: boolean; postDumpRezeroLastApplyUtc: string | null;
  completedAtUtc: string | null;
  compatibilityWeightWarning: boolean; compatibilityWarningSeverity: string | null;
  compatibilityZeroDriftLbs: number | null; rawPayload: R;
}

interface S {
  id: string; schema_version: number; job_id: string; line_id: string | null;
  machine_id: string; job_start_record_time_set_utc: string | null;
  job_end_record_time_set_utc: string | null; first_erp_timestamp_utc: string | null;
  last_erp_timestamp_utc: string | null; cycle_count: number | null; dump_count: number;
  basket_dump_count: number | null; basket_dump_count_raw: number | null;
  basket_cycle_count: number | null; anomaly_detected: boolean | null;
  first_basket_dump_utc: string | null; last_basket_dump_utc: string | null;
  idle_gaps: unknown[] | null; avg_hopper_load_time_ms: number | null;
  avg_dump_time_ms: number | null; hopper_load_times: unknown[] | null;
  dump_events: unknown[] | null; total_processed_lbs: number; avg_weight_lbs: number;
  avg_cycle_time_ms: number; override_seen: boolean; override_count: number | null;
  override_weight_lbs: number | null; final_set_weight_lbs: number | null;
  final_set_weight_unit: string | null; rezero_warning_seen: boolean;
  rezero_warning_reason: string | null; rezero_warning_weight_lbs: number | null;
  rezero_warning_threshold_lbs: number | null; post_dump_rezero_applied: boolean;
  post_dump_rezero_last_apply_utc: string | null; weight_warning: boolean;
  warning_severity: string | null; zero_drift_lbs: number | null;
  completed_at_utc: string; status: string;
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response(null, { headers: corsHeaders });

  const sb = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
  );

  try {
    const rb = await req.text();
    let p: R;
    try {
      const x = JSON.parse(rb);
      if (typeof x !== "object" || x === null || Array.isArray(x)) throw new Error("not object");
      p = x as R;
    } catch (e) {
      await logErr(sb, "INVALID_JSON_RECEIVED", { raw_body: rb, parse_error: e instanceof Error ? e.message : "Unknown" });
      return jr({ success: false, error: "Invalid JSON payload" }, 400);
    }

    const n = norm(p);
    const ve = validate(n);
    if (ve) return jr({ success: false, error: ve }, 400);

    const rids = await relatedIds(sb, n);
    const ex = await findEx(sb, n);
    if (ex) {
      await sync(sb, ex, rids);
      return jr({ success: true, message: "Duplicate scale completion payload ignored", id: ex.id, duplicate: true });
    }

    const row = buildRow(n);
    const { data: ins, error: ie } = await sb.from("scale_completion_data").insert(row).select(sel).single();
    if (ie) {
      if (ie.code === "23505") {
        const dr = await findEx(sb, n);
        if (dr) {
          await sync(sb, dr, rids);
          return jr({ success: true, message: "Duplicate scale completion payload ignored", id: dr.id, duplicate: true });
        }
        return jr({ success: true, message: "Duplicate scale completion payload ignored", duplicate: true });
      }
      await logErr(sb, "FAILED_TO_STORE_SCALE_DATA", { payload: p, error: ie });
      return jr({ success: false, error: "Failed to store data" }, 500);
    }

    await sync(sb, ins as S, rids);

    // Mark as processed now that completed_jobs has been updated
    await sb
      .from("scale_completion_data")
      .update({ status: "processed", processed_at: new Date().toISOString(), updated_at: new Date().toISOString() })
      .eq("id", (ins as S).id);

    return jr({
      success: true,
      message: "Scale completion data received and stored",
      id: (ins as S).id,
      schema_version: n.schemaVersion,
    });
  } catch (e) {
    return jr({ success: false, error: e instanceof Error ? e.message : "Unknown error" }, 500);
  }
});

function jr(d: unknown, s = 200) {
  return new Response(JSON.stringify(d), {
    headers: { ...corsHeaders, "Content-Type": "application/json" },
    status: s,
  });
}

function norm(p: R): N {
  const li = rs(p.line_id ?? p.lineId);
  const js = nt(p.job_start_record_time_set_utc ?? p.jobStartRecordTimeSetUtc);
  const je = nt(p.job_end_record_time_set_utc ?? p.jobEndRecordTimeSetUtc);
  const bdr = ri(p.basket_dump_count_raw ?? p.basketDumpCountRaw ?? p.basket_dump_count ?? p.basketDumpCount);
  const rws = rb2(p.rezero_warning_seen ?? p.rezeroWarningSeen ?? p.weight_warning ?? p.weightWarning ?? p.zero_health ?? p.zeroHealth, false);
  const rwr = rs(p.rezero_warning_reason ?? p.rezeroWarningReason ?? p.warning_severity ?? p.warningSeverity ?? p.zero_health_severity ?? p.zeroHealthSeverity);
  const rww = rn(p.rezero_warning_weight_lbs ?? p.rezeroWarningWeightLbs ?? p.zero_drift_lbs ?? p.zeroDriftLbs ?? p.zero_health_drift_lbs ?? p.zeroHealthDriftLbs ?? p.drift_lbs ?? p.driftLbs);
  return {
    schemaVersion: ri(p.schema_version) ?? 1,
    hasExplicitSchemaVersion: hv(p.schema_version),
    usesExpandedContract:
      li !== null || js !== null || je !== null ||
      hv(p.cycle_count) || hv(p.basket_dump_count) || hv(p.basket_dump_count_raw) ||
      hv(p.basket_cycle_count) || hv(p.anomaly_detected) || hv(p.idle_gaps) ||
      hv(p.hopper_load_times) || hv(p.dump_events) || hv(p.override_count) ||
      hv(p.rezero_warning_seen) || hv(p.rezero_warning_reason) ||
      hv(p.rezero_warning_weight_lbs) || hv(p.rezero_warning_threshold_lbs) ||
      hv(p.post_dump_rezero_applied),
    jobId: rs(p.job_id ?? p.jobId),
    lineId: li,
    machineId: rs(p.machine_id ?? p.machineId),
    jobStartRecordTimeSetUtc: js,
    jobEndRecordTimeSetUtc: je,
    firstErpTimestampUtc: nt(p.first_erp_timestamp_utc ?? p.firstErpTimestampUtc),
    lastErpTimestampUtc: nt(p.last_erp_timestamp_utc ?? p.lastErpTimestampUtc),
    cycleCount: ri(p.cycle_count ?? p.cycleCount),
    dumpCount: ri(p.dump_count ?? p.dumpCount),
    basketDumpCount: bdr,
    basketDumpCountRaw: bdr,
    basketCycleCount: ri(p.basket_cycle_count ?? p.basketCycleCount),
    anomalyDetected: rnb(p.anomaly_detected ?? p.anomalyDetected),
    firstBasketDumpUtc: nt(p.first_basket_dump_utc ?? p.firstBasketDumpUtc),
    lastBasketDumpUtc: nt(p.last_basket_dump_utc ?? p.lastBasketDumpUtc),
    idleGaps: ra(p.idle_gaps ?? p.idleGaps),
    avgHopperLoadTimeMs: ri(p.avg_hopper_load_time_ms ?? p.avgHopperLoadTimeMs),
    avgDumpTimeMs: ri(p.avg_dump_time_ms ?? p.avgDumpTimeMs),
    hopperLoadTimes: ra(p.hopper_load_times ?? p.hopperLoadTimes),
    dumpEvents: ra(p.dump_events ?? p.dumpEvents),
    totalProcessedLbs: rn(p.total_processed_lbs ?? p.totalProcessedLbs),
    avgWeightLbs: rn(p.avg_weight_lbs ?? p.avgWeightLbs),
    avgCycleTimeMs: ri(p.avg_cycle_time_ms ?? p.avgCycleTimeMs),
    overrideSeen: rb2(p.override_seen ?? p.overrideSeen, false),
    overrideCount: ri(p.override_count ?? p.overrideCount),
    overrideWeightLbs: rn(p.override_weight_lbs ?? p.overrideWeightLbs),
    finalSetWeightLbs: rn(p.final_set_weight_lbs ?? p.finalSetWeightLbs),
    finalSetWeightUnit: rs(p.final_set_weight_unit ?? p.finalSetWeightUnit),
    rezeroWarningSeen: rws,
    rezeroWarningReason: rwr,
    rezeroWarningWeightLbs: rww,
    rezeroWarningThresholdLbs: rn(p.rezero_warning_threshold_lbs ?? p.rezeroWarningThresholdLbs),
    postDumpRezeroApplied: rb2(p.post_dump_rezero_applied ?? p.postDumpRezeroApplied, false),
    postDumpRezeroLastApplyUtc: nt(p.post_dump_rezero_last_apply_utc ?? p.postDumpRezeroLastApplyUtc),
    completedAtUtc: nt(p.completed_at_utc ?? p.completedAtUtc),
    compatibilityWeightWarning: rws,
    compatibilityWarningSeverity: rwr,
    compatibilityZeroDriftLbs: rww,
    rawPayload: p,
  };
}

function validate(n: N) {
  const mf = [
    n.jobId === null ? "job_id" : null,
    n.machineId === null ? "machine_id" : null,
    n.completedAtUtc === null ? "completed_at_utc" : null,
    n.dumpCount === null ? "dump_count" : null,
    n.totalProcessedLbs === null ? "total_processed_lbs" : null,
    n.avgWeightLbs === null ? "avg_weight_lbs" : null,
    n.avgCycleTimeMs === null ? "avg_cycle_time_ms" : null,
  ].filter((f): f is string => f !== null);
  if (n.usesExpandedContract) {
    if (!n.hasExplicitSchemaVersion) mf.push("schema_version");
    if (n.lineId === null) mf.push("line_id");
    if (n.jobStartRecordTimeSetUtc === null) mf.push("job_start_record_time_set_utc");
    if (n.jobEndRecordTimeSetUtc === null) mf.push("job_end_record_time_set_utc");
  }
  if (mf.length > 0) return `Missing or invalid required field(s): ${mf.join(", ")}`;
  return null;
}

function buildRow(n: N) {
  return {
    schema_version: n.schemaVersion,
    job_id: n.jobId, line_id: n.lineId, machine_id: n.machineId,
    job_start_record_time_set_utc: n.jobStartRecordTimeSetUtc,
    job_end_record_time_set_utc: n.jobEndRecordTimeSetUtc,
    first_erp_timestamp_utc: n.firstErpTimestampUtc,
    last_erp_timestamp_utc: n.lastErpTimestampUtc,
    cycle_count: n.cycleCount, dump_count: n.dumpCount,
    basket_dump_count: n.basketDumpCount, basket_dump_count_raw: n.basketDumpCountRaw,
    basket_cycle_count: n.basketCycleCount, anomaly_detected: n.anomalyDetected,
    first_basket_dump_utc: n.firstBasketDumpUtc, last_basket_dump_utc: n.lastBasketDumpUtc,
    idle_gaps: n.idleGaps, avg_hopper_load_time_ms: n.avgHopperLoadTimeMs,
    avg_dump_time_ms: n.avgDumpTimeMs, hopper_load_times: n.hopperLoadTimes,
    dump_events: n.dumpEvents.length > 0 ? n.dumpEvents : null,
    total_processed_lbs: n.totalProcessedLbs, avg_weight_lbs: n.avgWeightLbs,
    avg_cycle_time_ms: n.avgCycleTimeMs, override_seen: n.overrideSeen,
    override_count: n.overrideCount, override_weight_lbs: n.overrideWeightLbs,
    final_set_weight_lbs: n.finalSetWeightLbs, final_set_weight_unit: n.finalSetWeightUnit,
    rezero_warning_seen: n.rezeroWarningSeen, rezero_warning_reason: n.rezeroWarningReason,
    rezero_warning_weight_lbs: n.rezeroWarningWeightLbs,
    rezero_warning_threshold_lbs: n.rezeroWarningThresholdLbs,
    post_dump_rezero_applied: n.postDumpRezeroApplied,
    post_dump_rezero_last_apply_utc: n.postDumpRezeroLastApplyUtc,
    completed_at_utc: n.completedAtUtc,
    weight_warning: n.compatibilityWeightWarning,
    warning_severity: n.compatibilityWarningSeverity,
    zero_drift_lbs: n.compatibilityZeroDriftLbs,
    raw_payload: n.rawPayload,
    status: "pending",
  };
}

function buildUpd(s: S) {
  return {
    scale_completion_id: s.id,
    scale_machine_id: s.machine_id,
    scale_completed_at: s.completed_at_utc,
    scale_dump_count: s.dump_count,
    scale_basket_dump_count: s.basket_dump_count,
    scale_dump_events: s.dump_events,
    basket_dump_count_raw: s.basket_dump_count_raw,
    basket_cycle_count: s.basket_cycle_count,
    anomaly_detected: s.anomaly_detected,
    first_basket_dump_utc: s.first_basket_dump_utc,
    last_basket_dump_utc: s.last_basket_dump_utc,
    idle_gaps: s.idle_gaps ?? [],
    avg_hopper_load_time_ms: s.avg_hopper_load_time_ms,
    avg_dump_time_ms: s.avg_dump_time_ms,
    hopper_load_times: s.hopper_load_times ?? [],
    scale_total_processed_lbs: s.total_processed_lbs,
    scale_avg_weight_lbs: s.avg_weight_lbs,
    scale_avg_cycle_time_ms: s.avg_cycle_time_ms,
    scale_override_seen: s.override_seen,
    scale_override_count: s.override_count,
    scale_final_set_weight_lbs: s.final_set_weight_lbs,
    scale_final_set_weight_unit: s.final_set_weight_unit,
    scale_rezero_warning_seen: s.rezero_warning_seen ?? false,
    scale_rezero_warning_reason: s.rezero_warning_reason ?? null,
    scale_post_dump_rezero_applied: s.post_dump_rezero_applied ?? false,
    scale_weight_warning: s.weight_warning ?? false,
    scale_warning_severity: s.warning_severity ?? null,
    scale_zero_drift_lbs: s.zero_drift_lbs ?? null,
  };
}

async function findEx(sb: ReturnType<typeof createClient>, n: N) {
  let q = sb.from("scale_completion_data").select(sel)
    .eq("job_id", n.jobId!)
    .eq("machine_id", n.machineId!);
  if (n.lineId && n.jobStartRecordTimeSetUtc && n.jobEndRecordTimeSetUtc) {
    q = q.eq("line_id", n.lineId)
      .eq("job_start_record_time_set_utc", n.jobStartRecordTimeSetUtc)
      .eq("job_end_record_time_set_utc", n.jobEndRecordTimeSetUtc);
  } else {
    q = q.eq("completed_at_utc", n.completedAtUtc!);
  }
  const { data, error } = await q.limit(1).maybeSingle();
  if (error) { console.error("findEx error:", error); return null; }
  return (data as S | null) ?? null;
}

async function sync(sb: ReturnType<typeof createClient>, sc: S, ids: string[]) {
  if (ids.length === 0) return;
  const u = buildUpd(sc);
  const { data: ex, error: le } = await sb.from("completed_jobs").select("job_id").in("job_id", ids);
  if (le) {
    await logErr(sb, "FAILED_TO_LOOK_UP_COMPLETED_JOBS_FOR_SCALE_SYNC", {
      job_id: sc.job_id, scale_completion_id: sc.id, target_job_ids: ids, error: le,
    });
    return;
  }
  const ej = new Set((ex ?? []).map((r) => r.job_id as string));
  const mj = ids.filter((j) => !ej.has(j));
  if (ej.size > 0) {
    const { error: ue } = await sb.from("completed_jobs").update(u).in("job_id", [...ej]);
    if (ue) await logErr(sb, "FAILED_TO_SYNC_COMPLETED_JOB_SCALE_DATA", {
      job_id: sc.job_id, scale_completion_id: sc.id, target_job_ids: ids, error: ue,
    });
  }
  if (mj.length === 0) return;
  const fs = sc.job_start_record_time_set_utc ?? sc.job_end_record_time_set_utc ?? sc.completed_at_utc;
  const fc = sc.job_end_record_time_set_utc ?? sc.completed_at_utc;
  const sr = mj.map((j) => ({
    job_id: j, started_at: fs, completed_at: fc,
    total_duration_minutes: 0, total_steps: 0,
    machines_used: sc.machine_id ? [sc.machine_id] : [],
    employees_involved: [], steps_sequence: ["SCALE_WEBHOOK_ONLY"],
    ...u,
  }));
  const { error: ie } = await sb.from("completed_jobs").insert(sr);
  if (ie) await logErr(sb, "FAILED_TO_SYNC_COMPLETED_JOB_SCALE_DATA", {
    job_id: sc.job_id, scale_completion_id: sc.id, target_job_ids: ids, missing_job_ids: mj, error: ie,
  });
}

async function relatedIds(sb: ReturnType<typeof createClient>, n: N) {
  const ids = new Set<string>([n.jobId!]);
  const ref = n.jobEndRecordTimeSetUtc ?? n.completedAtUtc!;
  const sid = await nearestStep(sb, n.machineId!, n.jobId!, ref);
  if (sid) ids.add(sid);
  return [...ids];
}

async function nearestStep(sb: ReturnType<typeof createClient>, mid: string, src: string, ref: string) {
  const rm = new Date(ref).getTime();
  if (!Number.isFinite(rm)) return null;
  const ss = new Date(rm - (2 * 60 * 1000)).toISOString();
  const se = new Date(rm + (10 * 60 * 1000)).toISOString();
  const { data: ns, error } = await sb.from("job_steps").select("job_id,started_at")
    .eq("location_code", mid).neq("job_id", src)
    .gte("started_at", ss).lte("started_at", se)
    .order("started_at", { ascending: true }).limit(25);
  if (error) { console.error("nearestStep error:", error); return null; }
  if (!ns || ns.length === 0) return null;
  const m = new Map<string, number>();
  for (const s of ns) {
    const t = new Date(s.started_at).getTime();
    if (!Number.isFinite(t)) continue;
    const d = Math.abs(t - rm);
    const e = m.get(s.job_id);
    if (e === undefined || d < e) m.set(s.job_id, d);
  }
  let cj: string | null = null, cd = Infinity;
  for (const [j, d] of m.entries()) { if (d < cd) { cd = d; cj = j; } }
  return cj;
}

async function logErr(sb: ReturnType<typeof createClient>, msg: string, data: Record<string, unknown>) {
  await sb.from("system_error_log").insert({
    function_name: "receive-scale-webhook",
    error_message: msg,
    error_data: data,
    created_at: new Date().toISOString(),
  });
}

function hv(v: unknown) { return v !== null && v !== undefined; }
function nt(v: unknown) {
  const r = rs(v);
  if (r === null) return null;
  const p = new Date(r);
  if (!Number.isFinite(p.getTime())) return null;
  return p.toISOString();
}
function rb2(v: unknown, fb = false): boolean {
  if (typeof v === "boolean") return v;
  if (typeof v === "string") {
    const n = v.trim().toLowerCase();
    if (n === "true") return true;
    if (n === "false") return false;
  }
  if (typeof v === "number") return v !== 0;
  return fb;
}
function rnb(v: unknown): boolean | null {
  if (v === null || v === undefined) return null;
  return rb2(v, false);
}
function rn(v: unknown): number | null {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string" && v.trim() !== "") {
    const p = Number(v);
    return Number.isFinite(p) ? p : null;
  }
  return null;
}
function ri(v: unknown): number | null {
  const p = rn(v);
  return p !== null ? Math.trunc(p) : null;
}
function rs(v: unknown): string | null {
  if (typeof v !== "string") return null;
  const t = v.trim();
  return t === "" ? null : t;
}
function ra(v: unknown): unknown[] {
  if (Array.isArray(v)) return v;
  return [];
}
