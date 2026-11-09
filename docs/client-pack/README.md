# Asseta client acceptance pack

This pack is for the owner and management of the company. It answers section 9 of your *Developer Implementation Guideline*: what we must show you, and tell you, before you accept the system.

Everything here describes the system as it is built today. Where something cannot be fully enforced, we say so.

## What is in the pack

| Document | What it answers | Guideline section 9 item |
|---|---|---|
| [01 How the system is built](01-how-the-system-is-built.md) | The parts of the system and how they fit together, in plain terms | A clear explanation of the system architecture |
| [02 The six ledgers](02-ledgers.md) | What each ledger records, how balances are worked out, and how to trace a balance back to its records | A description of the database and ledger structure |
| [03 Offline and central](03-offline-and-central.md) | Every activity: can it be done offline, and does it need central confirmation? | Section 7: which activities can be completed offline and which need central authorization |
| [04 What the technology cannot fully enforce](04-what-the-technology-cannot-fully-enforce.md) | An honest list of limits, what the system does instead, and what the company should do | A list of any requirements that cannot be fully enforced |
| [05 Acceptance scenarios](05-acceptance-scenarios.md) | The 13 scenarios as a step-by-step demonstration on a test company, with tick boxes and a signature page | A demonstration of the main workflows and the 13 scenarios |
| [06 Your data (DRAFT)](06-your-data.md) | What data the company has, how to export it, how long it is kept, and when the Platform Owner can see it | Confirmation that the company will own and have access to its data, configuration and accounts |
| [07 Training notes](07-training-notes.md) | What each role needs to learn, with pointers to the user manual | User training and basic system documentation |

## Status

| Item | Status |
|---|---|
| Documents 01 to 05 and 07 | Written and checked against the system as built |
| Document 06 | **Draft.** The Platform Owner must review it before it is given to the company |
| The 13 scenarios | The script is written. **The demonstration has not yet been held.** The scenarios count as accepted only when the signature page in document 05 is signed |
| Schedule and cost | Not yet written (see below) |

## Schedule and cost — to be completed by the Platform Owner

*This section is a placeholder. The Platform Owner completes it before the pack is handed over.*

| Item | To be completed |
|---|---|
| Implementation schedule (demonstration date, training dates, go-live date) | |
| Implementation cost | |
| Monthly subscription (per billable machine) | |
| Trackers and installation, if any | |
| SMS credits, if any | |
| Payment terms | |

## Words used in this pack

| Word | Meaning |
|---|---|
| **Company** | Your company's private account on Asseta |
| **Platform Owner** | The provider of Asseta, who runs the central system |
| **Ledger** | A permanent list of entries. Entries are added, never changed or removed |
| **Custodian** | Any employee who is responsible for holding company cash, with or without a login |
| **Claimed** | Recorded by one person, not yet confirmed by another |
| **Confirmed** or **verified** | Checked and accepted by a second, independent person |
| **Sync** | The phone sending its saved records to the central system, and receiving updates |
| **Offline** | The phone has no internet connection |
