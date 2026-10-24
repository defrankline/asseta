# Asseta user manual: Platform Auditor

> Part of the [Asseta user manual](README.md). Read the README first for signing in and the glossary.

## Who this is for

This manual is for people who need to **inspect** the Asseta platform without changing anything. That includes internal or external auditors, finance reviewers and compliance staff.

The **Platform Auditor** role sees the same platform console as the [Platform Owner](06-platform-owner.md), but **read-only**.

## What you can do

You can view:

- The platform **dashboard**: tenants, subscriptions, contracted revenue per currency, outstanding balances and churn.
- **Tenants**: company records, verification, access state, subscriptions, rate versions, enrollments, pending charges and invoices.
- **Invoices**, **Payments**, **Products** and tenants' **SMS wallets**.
- **Managed-service mandates** and their staff.
- **Models**: versions, evaluations, training data manifests, lifecycle history, drift and monitoring.
- **Trackers & gateways**: approved tracker models and gateways.
- **System status**.
- The **Audit log**.
- Your **Notifications**.

You can also **export** reports (CSV / PDF) where an **Export** button is shown, **Preview next invoice** for a tenant, and click **Refresh** on pages that offer it.

You cannot:

- Create, edit, approve, verify, void, deploy or delete anything.
- See tenants' business data (jobs, machines, money, people). Like platform owners, auditors do not see tenant data without a managed-service mandate.

## Where you work

The web console at <https://asseta.co.tz>, in the **Asseta platform** console:

| Group | Menus |
|---|---|
| Overview | Dashboard, System status |
| Tenants | Tenants, Managed service |
| Billing | Invoices, Products, Payments, SMS wallets |
| Intelligence | Models |
| Administration | Trackers & gateways, Audit log, Notifications, My access |

Action buttons you are not allowed to use are **hidden**, not greyed out. Examples are **Onboard tenant**, **Record payment**, **Verify**, **Change status**, **Raise invoice** and the model lifecycle buttons. If a colleague mentions a button you cannot see, that is expected.

## Tasks

### 1. Review the commercial position

1. Open **Overview → Dashboard**. Note the **Contracted MRR / ARR**, **Billable / enrolled assets**, **Open invoices** and **Outstanding balance** per currency. These figures are never added across currencies.
2. Open **Billing → Invoices**. Filter by **Status** (Issued, Partially paid, Paid, Voided) and **Kind** (Subscription, Ad hoc). Use **Export** to download the list.
3. Click an invoice to see its lines, verified payments, credits applied and balance. Voided invoices are kept and marked "This invoice is void."

### 2. Check a tenant's subscription

1. Open **Tenants → Tenants** and **View details** on a tenant.
2. Check the company verification, subscription status and current rate.
3. Use the tabs:
   - **Rate versions**: every price change, with effective date and reason.
   - **Enrollments**: billable machines, with from and to dates.
   - **Pending charges**: proration items and any overrides with their reasons.
   - **Invoices**: use **Preview next invoice** to see what the next run would bill.

### 3. Check payments and segregation of duties

1. Open **Billing → Payments**. Each payment shows who **Recorded** it, its **Status** (Recorded, Verified, Rejected) and what it was **Applied to**.
2. A payment must be verified by someone other than the person who recorded it. Asseta enforces this, and the audit log shows both people.

### 4. Use the audit log

1. Open **Administration → Audit log**.
2. Filter by **Actor**, **Tenant**, **Action starts with**, **Record type**, **Record id**, **From** and **To**.
3. Expand a row to see the **Before** and **After** values, source, actor roles and correlation id.
4. Actions taken inside a tenant's account under a managed-service mandate are marked "By Asseta staff under {mandate}".

### 5. Review model governance

1. Open **Intelligence → Models**.
2. For each version, check the evaluation result (**Passed** / **Not passed**), the **Evaluation vs baseline**, the **Training data manifest** and the **Lifecycle history**: who approved or deployed it, when and why.
3. Check that a model was deployed **in shadow** before being deployed **active**. Check also the **Drift** and **Monitoring** sections.

### 6. Check managed-service mandates

Open **Tenants → Managed service**. Each mandate shows:

- The client and **Scope** (Full management or Operations only).
- **Starts on** and **Ends on**.
- The **Consent reference**.
- The staff assigned.
- Its status (Scheduled, In force, Expired, Revoked, Ended).

## Statuses and what they mean

See the status table in the [Platform Owner manual](06-platform-owner.md#statuses-and-what-they-mean). The meanings are identical.

## Good practice

- Export the lists you rely on at the time of review. Figures such as balances change as payments are verified.
- Reference audit-log **Record id** and **correlation id** values in your findings so they can be traced.
- Report anything that needs action to a Platform Owner. You cannot correct records yourself.

## Troubleshooting and FAQ

**I can't see an "Onboard tenant" (or "Verify", "Record payment") button.**
That is correct for a read-only role.

**An invoice dialog says "You cannot view payments."**
Your role is missing payment read permission. Ask a Platform Owner to check your role.

**I need to see a tenant's jobs or cash.**
Tenant business data is not part of the platform console. It is available only through a managed-service mandate, with the tenant's consent.
