import Foundation

/// Migration 12 (ADR-008: machine reports replace jobs), forward-only and non-destructive for anything still in use:
/// - the server no longer sends jobs, contracts, changeover jobs or hire invoices, so their cached copies
///   (`sync_entity` types `job`, `contract`, `changeover_job`, `open_invoice`) are dropped;
/// - work-log and customer-acknowledgement records of the supervisor inbox (kinds `JOB_ACTIVITY`, `ACKNOWLEDGEMENT`)
///   and the `job_id` column (with its index) of `inbox_record` go: no remaining record carries a job;
/// - timed work-log entries left running on the phone (`sync_kv` keys `work_log_running.*`) are dropped.
/// Queued operations, evidence files and every other table are untouched. No table was used by jobs alone.
enum JobRemovalV12 {
    static let statements: [String] = [
        "DELETE FROM sync_entity WHERE entity_type IN ('job', 'contract', 'changeover_job', 'open_invoice')",
        "DELETE FROM inbox_record WHERE kind IN ('JOB_ACTIVITY', 'ACKNOWLEDGEMENT')",
        "DROP INDEX IF EXISTS ix_inbox_record_job",
        "ALTER TABLE inbox_record DROP COLUMN job_id",
        "DELETE FROM sync_kv WHERE key LIKE 'work_log_running.%'",
    ]
}
