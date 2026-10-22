# ADR-006 — Ad-hoc platform invoices, per-line allocation and fulfilment

**Status:** Accepted (DEC-022 a), 2026-10-22. Extends ADR-003 (subscription billing).

## Context

"The platform owner can raise invoice at any time. An invoice can contain the normal subscription fee, bulk sms
package etc. and upon payment receipts each item should effect its corresponding areas."

## Decision

- **Catalog** (`platform_product`): `SUBSCRIPTION_FEE` (no list price: priced by the tenant's negotiated rate),
  `SMS_BUNDLE` (`sms_credits` per unit), `SERVICE`. Prices are Decimal per currency; `taxable` flag. Full DEC-021
  lifecycle (search, details, edit with `version`, deactivate/reactivate with reason; never deleted).
- **One invoice model**: `platform_invoice.kind` = `SUBSCRIPTION` (scheduled, unchanged, one per period) or `AD_HOC`.
  Same `AST-YYYY-NNNNNNN` sequence, insert-only lines, snapshot guard trigger (now also freezing `kind`/`notes`).
  Ad-hoc lines snapshot the product, quantity, negotiated unit price and discount; tax uses the tenant's current rate
  version (`tax_name`, `tax_rate_percent`, rounding) on taxable catalog lines. A `SUBSCRIPTION_FEE` line reuses
  `InvoiceService.compute_period` (assets, minimum, pending proration charges, discount, tax) for a valid period,
  marks those pending charges invoiced, and counts as billing that period: the scheduler reports it as existing, and a
  second line for it is refused (`PERIOD_ALREADY_BILLED`) until the invoice is voided. Both paths take the same
  subscription advisory lock.
- **Allocation** (`platform_line_allocation`): verified payments and credit adjustments are applied either to a named
  line (explicit, by the platform owner, at record or verification time) or to an invoice as a whole (default:
  the payment's invoice, then the tenant's oldest open invoices by due date). Invoice-level money fills lines in line
  order after explicit allocations. Each line's *payable* is its amount less a proportional share of negative lines
  (discount/proration credits), so payables sum to the total. Invoice `amount_paid`/`credits_applied`/`balance`/status
  are recomputed from active allocations. Existing verified payments and credits were migrated as invoice-level
  allocations. A payment may now be recorded for a tenant (no invoice); unallocated verified money is tenant credit,
  applied later with `POST /platform/payments/{id}/allocations`.
- **Fulfilment** (`platform_line_fulfilment`, unique per line, claimed with `INSERT … ON CONFLICT DO NOTHING` in the
  same transaction as the allocation): `SMS_BUNDLE` → `BUNDLE_CREDIT` ledger entry in the tenant SMS wallet
  (`sms_wallet_entry`, append-only, serialized per tenant, unique per type+reference); `SUBSCRIPTION_FEE` → period
  settled + entitlement re-evaluated; `SERVICE` → recorded. Outbox `PlatformInvoiceLineFulfilled` drives the tenant
  notification. Duplicate events, retries and re-runs cannot double an effect.
- **Entitlement**: only subscription money restricts access — unpaid scheduled invoices and ad-hoc invoices whose
  `SUBSCRIPTION_FEE` line is not settled. Unpaid SMS bundles or services never suspend a tenant.
- **Void = reversal** (`POST /platform/invoices/{id}/void`, `platform.invoice.void`): status `VOIDED` (terminal,
  trigger-enforced), balance 0, allocations released (the money becomes tenant credit), fulfilled lines reversed:
  unused SMS credits are debited back (`BUNDLE_REVERSAL`) → `REVERSED`; credits already spent cannot be recalled →
  `REVERSAL_FLAGGED` with the shortfall, notified to platform staff for review; services → `REVERSAL_FLAGGED`;
  subscription lines → `REVERSED` and the period becomes billable again (ad-hoc). Voiding a *scheduled* invoice waives
  its period: the scheduler never re-issues it (re-bill explicitly with an ad-hoc subscription line). Pending
  proration charges invoiced on a voided invoice stay `INVOICED`.

## Consequences

- Platform payment verification has no segregation-of-duties check (unchanged from Gate 1); tenant finance does.
- The previous schema cannot represent ad-hoc invoices or tenant-level payments: downgrading past this revision is
  refused once they exist (restore from backup).
