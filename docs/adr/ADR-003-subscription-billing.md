# ADR-003 — Platform subscription billing model

**Status:** Accepted (implements prompt.md §1.2)

* **Billing unit:** distinct machine UUID enrolled in `subscription_asset_enrollment` over `[effective_from,
  effective_to)`. A partial unique index allows one open enrollment per machine → no double billing on retries,
  duplicates or tracker swaps (trackers never touch enrollments).
* **Prices:** `subscription_rate_version` — immutable, effective-dated, per-tenant negotiated unit price per asset
  per period, currency, cadence (MONTHLY/YEARLY), minimum billable assets (≥1), discount %, tax name/%,
  mid-cycle policies, rounding mode. Renegotiation = new version; no backdating; cadence change needs new subscription.
* **Periods:** anchored to the billing start day; short months clamp. Billing in advance at period start.
* **Recurring invoice (period P):** one line per machine active at P.start, minimum-commitment top-up, pending
  proration lines, discount, tax. Unique `(subscription_id, period_start)` + advisory lock = idempotent; catch-up
  generates missed periods. Lines immutable; header only changes paid/credit/balance/status.
* **Mid-cycle changes (documented default policy):** changes must fall in the current period (no backdating).
  A change at d creates a *pending charge* (add: PRORATE_DAILY | FULL_PERIOD | NEXT_PERIOD; remove:
  PRORATE_CREDIT | NO_CREDIT) when d > P.start or P's invoice is already issued; zero when covered by the minimum
  commitment. Previews are available before applying; pending charges are overridable (audited) until invoiced.
* **Payments:** recorded manually (cash/bank/mobile money) with unique reference; only VERIFIED payments reduce
  balances; overpayment and currency mismatch rejected. Credits via audited credit adjustments. Gateways: BL-004.
* **Entitlements:** versioned `entitlement_policy` (platform default, tenant override): grace days, suspend-after
  days, access for PAST_DUE/SUSPENDED/CANCELLED. Evaluation is deterministic and records `entitlement_event`.
  Manual suspension persists until manual reactivation; automatic suspension lifts on verified payment.
  Data is never deleted or hidden; READ_ONLY rejects writes explicitly.
* **Cancellation:** future-dated cancellation stays billable until the date, then auto-cancels; no further invoices.
* **Reporting:** MRR/ARR per currency (yearly normalized /12), never summed across currencies.
