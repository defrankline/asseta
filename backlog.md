# ASSETA — POST–RELEASE 1 BACKLOG

**Status:** FUTURE OPTIONS ONLY — NOT AUTHORIZED FOR RELEASE 1.

## Scope protection

Every idea not already expressly covered by `prompt.md` goes here. Recording an idea does **not** authorize implementation, migrations, new API endpoints or UI pages. Items may be reconsidered only after Release 1 acceptance and explicit written Platform Owner approval of a new release baseline. Do not create dependencies from in-scope Release 1 work to backlog items.

## Deferred enhancements

| ID | Candidate (NOT R1) | Why it may matter | Trigger/prerequisite | Priority for later review |
|---|---|---|---|---|
| BL-001 | Fully supervised fraud classifier trained on confirmed cases | More accurate fraud prioritization | Sufficient investigated, labelled outcomes and low false-positive rate | High |
| BL-002 | Advanced predictive mechanical failure models | Better downtime avoidance | Reliable breakdown/repair and sensor history | High |
| BL-003 | Dynamic/ML-optimized rental pricing | Better margin and utilization | Historical demand, actual costs and explainable optimization | Medium |
| BL-004 | Automated subscription payment gateways/recurring card/mobile money collection | Reduce platform billing effort | Licensed provider agreement, reconciliation and security compliance | High |
| BL-005 | Automatic tenant-customer mobile money/bank collections | Faster tenant settlement | Payment provider onboarding and reconciled APIs | High |
| BL-006 | Enterprise ERP/general ledger/tax/payroll modules | Full financial management | Validated client demand; integration vs build analysis | Low |
| BL-007 | Customer self-service mobile/portal | Customer transparency | Adoption evidence; data-sharing rules | Medium |
| BL-008 | Separate operator application | Granular operator events | Evidence supervisors cannot adequately capture | Low |
| BL-009 | Multi-vendor deep diagnostics / remote configuration / OTA firmware management | Advanced device operations | Certified vendor APIs and device security audits | Medium |
| BL-010 | Dedicated IoT firmware or custom Asseta hardware | Greater control of telemetry | Volume economics, regulatory certification | Low |
| BL-011 | Real-time fuel tank sensor integrations | Stronger theft detection | Reliable sensor calibration and installation | High |
| BL-012 | Hydraulic/PTO deep work classification and excavator activity detection | Distinguish work from idle more accurately | Suitable equipment/sensors and labeled data | Medium |
| BL-013 | Automated contractor/customer OTP confirmations | Reduce timesheet disputes | Customer consent/UX and SMS contracts | Medium |
| BL-014 | Route optimization and asset dispatch optimizer | Reduce mobilization costs | Enough dispatch and site demand data | Medium |
| BL-015 | Predictive resale/asset value and replacement timing | Long-term capital planning | Market data and valuation evidence | Low |
| BL-016 | AI natural-language assistant/chat and report Q&A | Convenience | Proven demand and data access governance | Low |
| BL-017 | Custom no-code workflow/rules builder | Broader owner flexibility | Concrete needs beyond typed R1 policies | Low |
| BL-018 | Free-form dashboard and report designer | Customized analytics | Verified reporting demand | Low |
| BL-019 | Multi-currency auto FX conversion and consolidated revenue views | Multinational tenants | Exchange-rate source and finance rules | Low |
| BL-020 | Data warehouse/lakehouse and dedicated ML feature platform | Scale beyond relational store | Measured Postgres/Redis limits | Low |
| BL-021 | Kubernetes/service mesh/microservice decomposition | Extreme deployment scalability | Proven operational bottleneck | Low |
| BL-022 | Satellite communications and remote no-cellular live tracking | Remote sites with no mobile coverage | Hardware + commercial satellite connectivity | Medium |
| BL-023 | Asset financing/insurance marketplace | New commercial offerings | Regulatory and commercial partnerships | Low |
| BL-024 | Public equipment rental marketplace and online bookings | New sales channel | Product/market validation beyond client operations | Low |
| BL-025 | Photo fraud deepfake/forensic analysis beyond basic duplicate/quality checks | Stronger evidence validation | Diverse adversarial test dataset | Medium |
| BL-026 | Advanced geospatial machine-learning route clustering and behavioral baselines | Better route anomalies | Representative historical telemetry | Medium |
| BL-027 | Email-based tenant-owner invitation (Keycloak execute-actions email + SMTP) instead of one-time temporary password | Smoother onboarding, no password handling by platform staff | SMTP provider, email templates, deliverability | Medium |
| BL-028 | Managed-service assignments scoped to a site/operating area (not only the whole client), as the reference product does for branches | Finer least-privilege for mandate staff | Needs unit-scoped tenant RBAC, which R1 roles do not have (tenant-wide); ADR-004 | Medium |
| BL-029 | Email/SMS notification to client administrators when a mandate is granted/ended (R1: console banner + Managed service page + outbox event) | Client is told even if nobody signs in | BL-027 SMTP; outbox consumer | Medium |

## New idea intake template

```
ID: BL-<next>
Date proposed:
Proposed by:
Idea:
Problem/benefit:
Why NOT required by frozen R1:
Dependencies/data/hardware:
Risk / estimated complexity:
Tentative future priority: High | Medium | Low
Owner decision: UNREVIEWED
```

## Change-control ledger

| Date | Item | Owner-approved future release | Decision |
|---|---|---|---|
| 2026-10-21 | Public business landing page at `/` for signed-out visitors (capabilities, how it works, pricing model, managed service; optional `VITE_CONTACT_EMAIL` demo link) and Asseta-branded Keycloak login theme (sign in, forgot/update password, register, OTP, errors) | R1 (requested directly by the Platform Owner in chat) | APPROVED by owner; implemented in R1 |
