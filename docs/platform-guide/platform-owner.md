# Asseta platform guide: Platform Owner

> Platform operations guide (not part of the tenant user manual). Signing in and the glossary: [user manual](../user-manual/README.md).

## Who this is for

This manual is for the **Platform Owner**: the owner and operator of the Asseta SaaS business. You onboard equipment companies as tenants, they pay you a subscription fee (per billable machine), and they then use Asseta to manage their own assets. Your work:

- Onboarding equipment companies (tenants).
- Negotiating and recording their subscription prices.
- Invoicing them and verifying their payments.
- Approving tracker hardware.
- Governing the machine-learning models.
- Watching the system's health.

You work in the **platform console** of the web app at <https://asseta.co.tz>.

The platform console is separate from tenants' business data:

- By default you **cannot** see a tenant's jobs, machines, money or people.
- Access to a tenant's account happens only under a **managed-service mandate**, which the tenant consents to. Everything you do under a mandate is recorded and visible to the tenant.

## What you can do

- **Tenants**: onboard companies, verify their company records, edit details, and manage each subscription:
  - Status changes
  - Rate versions
  - Billable-asset enrollments
  - Pending charges
  - Invoice generation
- **Billing**:
  - Raise subscription and ad-hoc invoices.
  - Record, verify, reject and allocate payments.
  - Apply credits and void invoices.
  - Maintain the **product catalog** (subscription fees, SMS bundles, services).
  - View tenants' **SMS wallets**.
- **Managed service**: grant, staff and end mandates.
- **Models**: review, approve, deploy (shadow or active), roll back, retire or disable ML models. Switch inference on or off.
- **Trackers & gateways**: approve tracker models and register telemetry gateways.
- **System status** and the **Audit log**.
- **Notifications**: your inbox, preferences, the SMS delivery log and test sends.

## Where you work

| Group | Menus |
|---|---|
| Overview | Dashboard, System status |
| Tenants | Tenants, Managed service |
| Billing | Invoices, Products, Payments, SMS wallets |
| Intelligence | Models |
| Administration | Trackers & gateways, Audit log, Notifications, My access |

Use the switcher at the top left to move between **Asseta platform** (the platform console) and any tenant account you hold a mandate for.

---

## First sign-in

The first platform owner account is created by the system administrator, who gives you a one-time temporary password.

1. Open <https://asseta.co.tz> and click **Sign in**.
2. Enter your email and the temporary password.
3. Set a new password.
4. When asked, set up an **authenticator app** (one-time codes) on your phone. You will need a code at each sign-in.

## Tasks

### 1. Read the platform dashboard

**Overview → Dashboard** ("Platform dashboard") shows:

- **Tenants by status**, **Tenants by access**, **Subscriptions by status**.
- **Churn events (30 days)**: cancellations and expiries.
- **Revenue by currency**: **Contracted MRR**, **Contracted ARR**, **Billable / enrolled assets**, **Open invoices** and **Outstanding balance**.

Totals are reported per currency and never converted or added across currencies. Click **Refresh** to update.

### 2. Onboard a new tenant

1. Go to **Tenants → Tenants** and click **Onboard tenant**.
2. **Company**: **Legal name**, **Display name**, **Registration no.**, **Contact name**, **Contact email**, **Contact phone**.
3. **Settings**: **Timezone**, **Currency** and **Locale** (for example en or sw).
4. **Owner**: the tenant owner's **Owner email**, **First name** and **Last name**.
5. **Commercial terms**. The price is negotiated per tenant, as an amount per billable machine per billing period.
   - **Start date**, **Trial days**, **Payment terms (days)**
   - **Currency** (TZS by default)
   - **Billing cadence**: **Monthly** or **Yearly**
   - **Unit price per asset per period**
   - **Minimum billable assets** (at least 1)
   - **Discount %**
   - **Rounding**
   - **Tax name** and **Tax %**
   - **Mid-cycle asset add**: **Prorate daily (default)**, **Charge full period** or **Start billing next period**
   - **Mid-cycle asset removal**: **Prorated credit (default)** or **No credit**
6. Check the **Review** step and click **Onboard tenant**.
7. The **Tenant onboarded** dialog shows the owner's **temporary password**. It is **shown once**:
   1. Click **Copy password**.
   2. Send it to the owner through a secure channel.
   3. Click **I have saved it**.

   The owner must change it at first sign-in.

If you lose the password before sharing it, it cannot be shown again. Reset the owner's password in the identity provider (Keycloak administration).

### 3. Verify the company and activate the subscription

1. Open the tenant (**View details**).
2. In the company panel, click **Verify company**. Set the **Verification status** (**Verified**, **Rejected** or **Unverified**). Add a **Note** saying what was checked, for example the registration certificate or TIN. Click **Save verification**.
3. In the **Subscription** panel, click **Change status**, choose **Activate**, set the **Effective date** and **Reason**, then click **Apply**.

Activation requires a verified company record and a negotiated rate.

### 4. Manage a subscription

On the tenant detail page:

**Change status.** The available actions depend on the current status:

| Current status | Actions |
|---|---|
| Draft | Cancel subscription |
| Pending activation | Activate, Cancel subscription |
| Active, Past due | Suspend, Cancel subscription |
| Suspended | Reactivate, Cancel subscription |

- **Past due** and **Expired** are set automatically, never by hand.
- A future effective date **schedules** a cancellation.
- Data is never deleted.

**Evaluate entitlement** re-checks the tenant's access (Full / Read only / Blocked) against its billing state.

**Rate versions** tab: **New rate version** creates a new price from an **Effective from** date with a **Reason**. Earlier versions stay unchanged. Rates cannot be backdated. Changing between monthly and yearly requires a new subscription.

**Enrollments** tab: the machines the tenant has enrolled as billable assets. Tenants enrol them from their own console. To end one:

1. Click **End enrollment**.
2. Enter the **End date** and choose a **Reason**: Removed from fleet, Disposed, Subscription ended or Correction.
3. Click **Preview** to see the proration effect.
4. Click **Confirm end**.

**Pending charges** tab: mid-period charges and credits waiting for the next invoice. Use **Override** to change one, with a reason. Credits are negative amounts.

**Invoices** tab:

- **Preview next invoice** shows what would be billed as of a date.
- **Generate due invoices** issues them.

Generating twice for the same period never creates duplicates.

### 5. Raise an ad-hoc invoice

Use this for SMS bundles, services, or a subscription fee outside the automatic run.

1. Go to **Billing → Invoices** and click **Raise invoice**.
2. **Tenant & terms**: **Tenant**, **Currency** (the tenant's by default), **Due date** and **Notes (shown on the invoice)**.
3. **Lines**: for each line, choose a **Catalog item**. Then enter either the **Billing period start** (for subscription fees) or the **Quantity**, **Unit price** (empty = catalog price) and **Discount %**. Add more lines with **Add line**.
4. Check the server-calculated totals on **Review** and click **Raise invoice**.

### 6. Record and verify tenant payments

1. Go to **Billing → Payments** and click **Record payment**. Or use **Record payment** on an invoice.
2. Choose the **Tenant** and optionally the **Invoice**. Then enter the **Method** (Cash, Bank transfer or Mobile money), **Reference**, **Received on** and **Amount**.
3. The payment is **Recorded** until verified. Only verified payments reduce the balance.
4. **Another staff member** verifies it with **Verify**, or rejects it with **Reject**. Both need a **Note**. A payment you recorded shows "Recorded by you — another staff member must verify".
5. Use **Allocate** to apply an unallocated payment to invoice lines.

Verifying a payment can restore a past-due tenant's access automatically.

On an invoice's detail page:

- Each line shows its **Payment** state (Unpaid / Partially paid / Paid) and **Fulfilment**, for example "Fulfilled" when a paid SMS bundle has been credited to the wallet.
- **Apply credit** reduces the balance, with a reason.
- **Void invoice** reverses the invoice. It needs a reason and cannot be undone.

### 7. Product catalog and SMS wallets

- **Billing → Products** ("Product catalog"): use **Add catalog item** to create:
  - **Subscription fee**
  - **SMS bundle**, with **SMS credits per bundle**
  - **Service**

  Each item has list prices per currency and can be marked **Taxable**. Items can be deactivated and reactivated. The **Code** is fixed once created.
- **Billing → SMS wallets**: choose a **Tenant** to see **Available credits**, the **Low-balance alert at** level, and the ledger (Bundle credit, Bundle reversal, SMS sent, SMS refund).

### 8. Managed service

Use this when a tenant asks Asseta to operate their account for them.

1. Go to **Tenants → Managed service** and click **Grant mandate**.
2. **Client & scope**: choose the **Client tenant** and the **Scope**: **Full management** or **Operations only**.
3. **Consent & term**: **Starts on**, **Ends on (optional)**, the **Consent reference** (the client's written consent) and **Notes**.
4. Click **Grant mandate**.
5. Open the mandate and, under **Assign staff**, choose the **Platform staff** member and their **Client role**, then click **Assign**.

When you work under a mandate:

- You switch into the client's account with the top-left switcher.
- A banner says: "Acting for {Tenant} under managed-service mandate {ref} … Everything you do is recorded for the client."
- **Return to Asseta platform** takes you back.

To end a mandate, use **End mandate** with a reason. The client can also revoke it at any time from their own console.

### 9. Trackers & gateways

**Administration → Trackers & gateways**:

- **Tracker models**: **Add tracker model** with **Manufacturer**, **Model**, **Protocol**, **Adapter** and **Declared capabilities**. Only approved models can be registered by tenants. Use **Withdraw** or **Restore** to change availability.
- **Gateways**: **Add gateway** creates a telemetry gateway. Its key is **shown once**: click **Copy key**, then **I have stored the key**.

### 10. Models (governed machine learning)

**Intelligence → Models**:

- **Inference switch**: **Switch inference off** or **on** for the whole platform. When off, Asseta keeps working with its rule-based checks.
- **Model versions**, with statuses:
  - Trained
  - Evaluated
  - Approved
  - Deployed (shadow)
  - Deployed (active)
  - Retired
  - Disabled
  - Rejected
- **Readiness per tenant**: **Ready** or **Not enough history**. **Refresh snapshots…** and **Train now…** start data preparation and training.

On a model's page you can:

- Read its **Evaluation vs baseline**, **Training data manifest**, **Lifecycle history**, **Drift** and **Monitoring**.
- Act on it. Each action needs a reason:
  - **Approve**: only after the evaluation passes.
  - **Deploy in shadow**: predictions are recorded for the platform and never shown to the tenant.
  - **Deploy active**.
  - **Roll back**: retires this version and redeploys the previous one.
  - **Reject**, **Retire**, **Disable**.

### 11. System status and audit log

- **Overview → System status** shows an **Overall** state (ok / degraded / error) and each health check. Click **Refresh** to re-check.
- **Administration → Audit log** shows platform and billing actions with **When**, **Actor**, **Action**, **Record**, **Reason** and **Tenant**. Filter by actor, tenant, action, record or date. Expand a row for the before and after values.

### 12. Notifications

Your inbox (**Administration → Notifications**) receives, for example:

- "Payment to verify"
- "Reversal needs review"
- "Asseta invoice overdue"
- "Subscription status"
- "Model feature drift"

**Preferences** sets your channels. **Delivery log** shows SMS, push and e-mail results. Use **Send test** to check delivery.

---

## Statuses and what they mean

| Item | Statuses |
|---|---|
| Tenant | Onboarding, Active, Closed |
| Company verification | Unverified, Verified, Rejected |
| Tenant access | Full, Read only (changes disabled, data kept), Blocked |
| Subscription | Draft → Pending activation → Active → Past due / Suspended → Cancelled / Expired |
| Platform invoice | Issued, Partially paid, Paid, Voided |
| Platform payment | Recorded → Verified / Rejected |
| Pending charge | Pending, Invoiced, Waived |
| Mandate | Scheduled, In force, Expired, Revoked, Ended |
| Model | Trained, Evaluated, Approved, Deployed (shadow/active), Retired, Disabled, Rejected |

## Good practice

- **Share temporary passwords and gateway keys only through secure channels.** They are shown once.
- **Always have a second person verify payments.**
- **Record clear reasons** on status changes, rate versions, overrides and model actions. They are the audit trail.
- **Never access tenant data without a mandate**, and keep mandates scoped (**Operations only** when full management isn't needed) and time-limited.
- **Deploy new models in shadow first** and compare them with the baseline before going active.

## Troubleshooting and FAQ

**"Activation requires a verified company record and a negotiated rate."**
Verify the company and create a rate version first.

**I can't verify a payment.**
You recorded it. Another staff member must verify it.

**A tenant says their account is read-only.**
Their subscription is past due or suspended. Check their invoices and payments. Verifying the payment, or **Reactivate**, restores access. Their data was never deleted, and their supervisors' offline work is applied after reactivation.

**The owner never received the temporary password.**
It cannot be shown again. Reset the owner's password in Keycloak administration.

**A tenant can't find their tracker model.**
Only approved models are offered. Add it under **Trackers & gateways → Tracker models**.

**Approve is greyed out on a model.**
The evaluation has not passed. A model must beat its baseline before approval.
