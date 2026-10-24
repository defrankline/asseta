# Asseta user manual: Supervisor

> Part of the [Asseta user manual](README.md). Read the README first for signing in and the glossary.

## Contents

- [Who this is for](#who-this-is-for)
- [What you can do](#what-you-can-do)
- [Where you work](#where-you-work)
- [Part A: The Asseta Supervisor app (phone)](#part-a-the-asseta-supervisor-app-phone)
- [Part B: Working from a laptop (web console)](#working-from-a-laptop-web-console)
- [Statuses and what they mean](#statuses-and-what-they-mean)
- [Good practice](#good-practice)
- [Troubleshooting and FAQ](#troubleshooting-and-faq)

## Who this is for

This manual is for field supervisors: the people on site who look after hired machines, record hour-meter readings, log the work, get the customer to sign off, buy fuel, pay small expenses and collect cash.

You can do all of your work in either of two places:

- The **Asseta Supervisor** app on an Android phone or an iPhone. The two apps work the same way, and the app keeps working **without a network**.
- The **web console** at <https://asseta.co.tz> on a laptop. Its **Field work** menu has the same tasks. Use it when you are at the office or your phone is unavailable. The web console needs an internet connection.

## What you can do

- See the jobs assigned to you and the machines on them.
- Take the **opening** hour-meter reading with a photo, **start** the job, **log work, standby and downtime**, take the **closing** reading, get the **customer acknowledgement**, and **complete** the job.
- Record **fuel** (purchases, issues to machines, usage).
- Record **expenses** with receipt photos.
- Record **cash collected** from customers and **hand over cash** to the office.
- See your **cash in hand** and today's cash figures.
- **Request a meter reset** when an hour meter is replaced or rolls over.
- Read **office decisions and reminders** in your inbox.
- See the **exceptions** on your readings and the office's review notes.

What you cannot do: approve jobs, approve your own expenses, verify your own cash, or decide meter resets. The office does those. This separation protects you as much as the company.

## Where you work

**In the phone app**, the bottom tabs are:

| Tab | What it holds |
|---|---|
| **Jobs** | Your jobs: **In progress**, **Ready to start**, **Recently closed**, **My machines** |
| **Readings** | Every meter reading you captured and your meter reset requests, with the office's review |
| **Fuel** | Your fuel events (Purchase / Issue / Usage) |
| **Money** | Your cash, today's figures, expenses, collections and handovers |
| **Inbox** | Items that need your attention and notifications from the office |

At the top of each tab's first screen:

- On the left is the **account menu** (the person icon).
- On the right is the **sync badge**:
  - A cloud with a tick means everything is sent.
  - A number means that many items are waiting.
  - A red icon means something needs attention.

**In the web console**, your menus are:

| Group | Menus |
|---|---|
| Overview | Dashboard, Fleet map |
| **Field work** | **My jobs**, **Readings**, **Fuel**, **Expenses**, **Cash** |
| Operations | Jobs, Customers (to look things up) |
| Fleet | Alerts |
| Risk & review | Exceptions, Insights (read-only for you) |
| Finance | Expenses & fuel |
| Administration | Notifications, My access |

When you sign in to the web console you land on **My jobs**.

---

## Part A: The Asseta Supervisor app (phone)

### A1. First sign-in

1. Install **Asseta Supervisor** from your phone's app store, or from the link your company gives you.
2. Open it and tap **Sign in**. The secure Asseta sign-in page opens in your phone's browser.
3. Enter the username and password your company gave you. On first sign-in you may be asked to set a new password.
4. Choose your company in **Choose a company**. If you belong to only one company, it opens by itself.

   *What you'll see:* "Loading your account…", then the Jobs tab.
5. Pull down on the Jobs list once to sync. Your assigned jobs, machines, customers and your company's capture rules download to the phone.

**Do this while you have a good connection**, for example at the office or the yard, before you go to a site with weak signal. The app needs one sync to have your jobs and rules for offline work.

You stay signed in, even offline. You will not need your password every day.

### A2. A full job day on the phone

Below is a typical day for one job. The job detail screen always shows a **Next steps** section listing only the steps allowed right now. Follow it from top to bottom.

#### Step 1: Find the job

1. Open the **Jobs** tab.
2. Tap the **Ready to start** chip. Approved jobs assigned to you are listed with job number, machine, site and customer.
3. Tap the job.

*What you'll see:* the job header (Status, Machine, Meter precision, Site, Customer, Planned start), a **Summary**, and **Next steps**.

If the job is not there:

- It may not be approved yet. The office must approve a job before it reaches the field.
- It may not be assigned to you.
- Your phone may not have synced since the job was approved. Pull down to sync.

#### Step 2: Capture the opening reading

Do this **before the machine starts work**.

1. Under **Next steps**, tap **Capture opening reading**.
2. The **Method** is set by your company's rules and you cannot change it:
   - **Camera + automatic reading**: take a photo, and the phone reads the numbers.
   - **Manual entry**: type the reading. A photo may still be required.
3. Tap **Take photo** and photograph the hour meter. Fill the frame with the meter, avoid glare, and hold still.
4. With **automatic reading**, the phone says "Reading the meter on this phone…" and then shows:
   - **Recognized**: the number it read.
   - **Confidence**: for example 92%.

   Check the number against the meter. **If it is wrong, correct it.** The app then tells you: "You changed the recognized value. It will be sent as a manual correction." That is fine. Correct readings matter more than automatic ones. The office simply sees that it was corrected.
5. If the photo could not be read, the app asks you to **Retake photo** and tells you how many tries remain. After the allowed number of tries you may type the reading. The photo is still kept as evidence.
6. At the same time the app gets a **fresh GPS location** ("Getting a fresh location fix…"). When it succeeds you see the coordinates and "Accuracy ± N m".
   - If there is no GPS fix, you see a message such as "No GPS fix within 20 seconds". You can tap **Try location again**, ideally outdoors with a clear view of the sky.
   - **You can still save.** The reading is kept and marked for office review. Asseta never invents a location.
7. Tap **Save**.

*What you'll see:* "Opening reading" now shows a value in the job Summary. The reading appears in the **Readings** tab with status **Waiting to sync**, and later **Synced**, then **Accepted** or **Provisional** (see [Statuses](#statuses-and-what-they-mean)).

**Permissions:** the first time, the app asks for the **Camera** and **Location for this reading**. Choose **Allow**. Location is used only while you take a reading, never in the background. If you choose **Continue without location**, the reading is saved but flagged for review.

#### Step 3: Start the job

1. Under **Next steps**, tap **Start job**.
2. Confirm **Start this job?**. The time is recorded from the phone's clock and sent when possible.

*What you'll see:* the job moves to **In progress**. If the phone hasn't synced yet, the status shows "· not synced".

You cannot start a job without an opening reading. The app tells you: "Capture the opening reading first."

#### Step 4: Log the work during the day

On an approved or running job, the **Work log** section has quick buttons:

- **Start work**: when the machine starts working.
- **Standby**: when the machine is available but waiting, for example for the customer, trucks or weather.
- **Downtime**: when the machine cannot work, for example a breakdown or repair.

While an entry is running, its button changes to **Stop Work**, **Stop Standby** or **Stop Downtime**. Only one entry runs at a time. Stop the current one before starting another.

For more detail, or to record something after the fact, tap **Add work log entry**:

1. Choose **Type**: Work, Standby, Downtime, Mobilization (moving the machine to or from site) or Note.
2. Set **Started**.
3. If it has finished, turn on **Has ended** and set **Ended**. You can also set **Billable**:
   - **Contract default**: let the contract decide (the normal choice).
   - **Yes**
   - **No**
4. Add a **Note**, for example the downtime reason or an issue. A Note entry needs text.
5. Tap **Save**.

*What you'll see:* entries such as "Work 08:00 → 10:00 (2 h 00 min)". The Summary shows the total per type.

**Why this matters:** the hour meter shows how long the engine ran, but that is **not automatically** what the customer pays for. Standby and downtime entries help the office bill correctly under the contract.

#### Step 5: Capture the closing reading

When work ends for this job:

1. Stop any running work-log entry.
2. Under **Next steps**, tap **Capture closing reading**.
3. Follow the same steps as the opening reading: photo, check the number, location, **Save**.

#### Step 6: Get the customer acknowledgement

The customer's representative confirms the work on your phone.

1. Under **Next steps**, tap **Customer acknowledgement**.
2. Choose the method:
   - **Signature**: the representative signs on the screen with a finger. Use **Clear** to start again.
   - **Name confirmation**: you record their name only.
3. Enter the **Customer representative's name** (required). Optionally add **Phone** and **Hours acknowledged** (the hours they confirm).
4. Tap **Save**. It is enabled only when the name is entered and, for a signature, the customer has signed.

*What you'll see:* an **Acknowledgement** section on the job with the signer, method and signature.

#### Step 7: Complete the job

1. Under **Next steps**, tap **Complete job**.
2. Confirm **Complete this job?**.

*What you'll see:* the job moves to **Completed** and then appears under **Recently closed** (for 14 days). Its section says "No further actions on this job."

Asseta will not complete a job without both the **closing reading** and the **customer acknowledgement**. You'll see "Capture the closing reading first." or "Get the customer acknowledgement first."

#### Seeing what is still on the phone

At the bottom of each job, **Recorded on this phone** lists everything you did on this job and whether it has synced. For example: "Opening reading 4521 – Synced", "Job started – Waiting to sync".

### A3. Working offline and syncing

The Supervisor app is built for sites with no signal.

**What works offline:** everything in this manual. That includes jobs, readings with photos, starting and completing jobs, the work log, acknowledgements, fuel, expenses, cash collections and handovers. Everything is saved **encrypted on the phone** and sent later.

**What you'll see when offline:** a banner reading "Offline. You can keep working; everything is saved on this phone and syncs when you are back online."

**When it syncs:**

- When the app is open and the connection comes back.
- When you pull down on a list.
- When you tap **Sync now** on the Sync status screen.
- On Android, also in the background about every 15 minutes while a network is available.
- On iPhone, background sync may happen occasionally but is not guaranteed. **Open the app** to be sure.

Nothing is marked "Synced" until Asseta's server has confirmed it. Sending the same item twice never creates duplicates.

**The Sync status screen.** Tap the sync badge to open it. It shows:

- **Synced**, **Not yet synced** and **Files waiting to upload** (photos, receipts and signatures upload separately).
- **Last successful sync** and **Next automatic retry**.
- **Offline use allowed until**: how long your phone may keep working without contacting Asseta. Your company sets this.
- These groups:
  - **Waiting to sync** / **Sending**: normal. Nothing to do.
  - **Needs attention: rejected**: the server refused an item. The reason is shown as a code and message. Your original evidence stays on the phone. Fix the cause and tap **Retry**, or ask your office.
  - **Needs attention: conflicts**: the job changed on the server while you were offline, for example it was cancelled or reassigned. Nothing was overwritten. Your record is kept for the office to review.
  - **Held: subscription read-only**: your company's Asseta subscription is restricted. The items are kept and sent automatically after reactivation. Nothing is lost.

An item may show "Waiting for an earlier item" or "Waiting for its photo/receipt/signature upload". That is normal ordering. A reading, for example, is sent after its photo.

**Capture rules and offline time limits.** Your phone keeps a copy of your company's rules for readings and expenses. The copy expires after a while, and the phone may only work offline for a limited time. When either runs out, capture is paused with a message such as:

- "Connect to refresh rules. The downloaded capture rules have expired."
- "Connect to refresh rules. This device has been offline longer than allowed."

Get a connection for a moment and pull down to sync. Capture then opens again.

**Signing out with unsent items.** The app warns you: "N item(s) are not synced yet. They stay encrypted on this phone and sync after you sign in again." Unsent items are not lost, but they are sent only when **you** sign in again on that phone. Avoid signing out with unsent items when you can.

### A4. Fuel

1. Open the **Fuel** tab and tap **+** (**Record fuel event**).
2. Choose the type:
   - **Purchase**: "Fuel bought into stock. Record the money spent as an expense too."
   - **Issue**: "Fuel given to a machine from stock."
   - **Usage**: "Fuel a machine consumed (no price)."
3. Enter **Litres**. For Purchase and Issue, also enter **Price per litre** and **Currency**. The app shows the **Cost**.
4. For a purchase, enter the **Supplier (optional)**.
5. Set **When**.
6. Under **Machine**, choose the **Job** or the **Machine**. Picking a job fills in its machine. For a purchase into stock, choose "No machine (stock)".
7. Optionally enter the **Meter reading** and a **Note**, then tap **Save**.

Fuel events are a log. They are not edited after recording. If you made a mistake, tell the office.

**Tip:** when you pay for fuel with your cash, record **both** a fuel purchase (litres) and an **expense** (the money). The office links the two so the cost is not counted twice.

### A5. Expenses

1. Open the **Money** tab, tap **+** and choose **Record expense**.
2. Choose a **Category**, enter the **Amount**, **Currency**, **What was it for?** and **Supplier (optional)**.
3. Read the rules line under the form. For example: "Receipt photo required above 100 USD. GPS fix within ±50 m required. Up to 50 USD is approved automatically."
4. Set **Paid from**:
   - **My cash**: paid from the cash you hold. Once approved, it reduces your cash accountability.
   - **Company**: paid by the office.
5. Under **Charge to**, pick the **Job** or **Machine** the cost belongs to. With a job, the cost goes to that job's machine.
6. Add the **Receipt**: tap **Photograph receipt**. You can add up to 10 receipt photos.
7. If GPS is required, allow location. The fix must meet the accuracy your company requires.
8. Tap **Save**.

*What you'll see:*

- Small amounts within the auto-approval limit: "Within the auto-approval limit: approved automatically once synced."
- Larger amounts: the expense is recorded and stays **Pending approval** until someone in the office approves it.
- When the office decides, you get an inbox notification ("Expense approved" or "Expense rejected"), and the expense shows the **Office decision** and any note.

A **rejected** expense stays rejected. If the office asks for a correction, tap **Record a new expense**.

### A6. Cash: collecting and handing over

#### Record cash collected from a customer

1. **Money** tab → **+** → **Record cash collection**.
2. Choose the **Job (optional)**. This fills in its customer. Or choose the **Customer** directly.
3. Enter **Amount**, **Currency**, **Receipt / reference number (optional)**, **Received** (date and time) and a **Note (optional)**.
4. Tap **Save**.

The cash is added to your custody once the server accepts it. It stays **Awaiting verification** until the office verifies it. Until then it does not reduce the customer's balance.

#### Hand cash over to the office

1. **Money** tab → **+** → **Hand over cash**.
2. The form shows **Your cash** (an estimate per currency).
3. Enter **Amount handed over**, **Currency**, **Reference (deposit slip, receipt no.)**, **Handed over** (time) and a **Note** (for example, who received it).
4. Tap **Save**.

**Your custody goes down only when finance verifies the handover.** A handover shows **Awaiting verification** until then, and **Verified** or **Rejected** after. If it is rejected, read the office note and use **Hand over cash again** if needed.

#### Your cash figures

The **Money** tab shows your cash per currency:

- **Synced balance**: what the office's books say you hold, as of the last sync.
- **Handed over, awaiting verification**, and **Expenses awaiting approval**.
- Items **not yet synced** from this phone: collections (+), handovers (−) and cash expenses (−).
- **Estimated cash in hand (unverified)**.

The **Today** section shows today's office figures:

- Opening balance
- Floats issued
- Collections
- Approved spending
- Verified handovers
- **Outstanding**

The calculation is:

**Opening + floats + collections − approved spending − verified handovers = outstanding**

Offline, the section is headed **Today (as of HH:mm)** or **Today (estimate)**. It then uses the last office figures plus what you recorded since. These are estimates until you sync.

Below the figures, the chips **Expenses / Collections / Handovers** list your records, grouped as On this phone, Pending approval, Awaiting verification, Approved, Verified and Rejected. Rows show any **Office note**.

### A7. Request a meter reset

Use this when the hour meter was **replaced**, **repaired** or **rolled over** (went back to zero). A reset tells Asseta that later readings start from a new value, so they are not flagged as "Reading lower than before".

1. Open a reading (**Readings** tab), or a machine (**Jobs → My machines**), and tap **Request meter reset**.
2. Check the **Reading before the reset** (filled in for you) and enter the **Reading after the reset**.
3. Write the **Reason**, at least 10 characters. For example: "Meter replaced by the workshop".
4. Tap **Photograph meter** to add the **Evidence photo** (required).
5. Tap **Save**.

*What you'll see:* the request appears under **Meter reset requests** as **Pending**. "The office approves or rejects the reset. Until then readings continue from the old meter."

**You can never decide your own reset request.** Another person in the office must approve or reject it.

If the screen says "Meter reset not available", sync once while online and try again.

### A8. Readings tab: following up on your evidence

The **Readings** tab lists your readings, with a filter **All / Needs attention**. A reading appears under **Needs attention** when it was flagged or rejected.

Open a reading to see:

- **Photo**.
- **Camera reading**: what the phone read, the confidence, and whether it was corrected by hand.
- **GPS**.
- **Review**: one of "No findings", "Waiting for the office to review", "Reviewed by the office" or "No review needed".
- **Findings**: each with its type, review status, severity, "Blocking" if it blocks invoicing, and any **Office note**.

Finding names you may see:

| Finding | Plain meaning | What to do next time |
|---|---|---|
| No GPS position | No location fix with the reading | Allow location; try outdoors |
| GPS position not accurate enough / too old | The fix was weak or stale | Wait for a better fix; **Try location again** |
| Not at the job site / Does not match the tracker | Phone and machine tracker positions differ | Take readings next to the machine |
| Photo missing / Meter photo hard to read | Photo absent or unclear | Clean the meter glass, avoid glare |
| Reading corrected by hand | You changed the camera's number | Fine when the camera was wrong; the office just checks |
| Reading lower than before | Lower than the machine's previous reading | If the meter was replaced, request a meter reset |
| Reading increased too much / Gap since the last reading | More hours than time allows, or a gap between jobs | Check the number; add a note to the office |
| Photo used before | The same photo was already used | Always take a new photo |
| Phone clock was wrong | Phone time differs from Asseta's time | Set the date and time to automatic |
| Capture rules could not be verified | The rules on the phone could not be confirmed | Sync regularly |

**Findings are not accusations.** They are notes for the office to check. Many are explained in seconds, for example "meter replaced". The office records the outcome as **Explained** or **Confirmed**.

### A9. Inbox

The **Inbox** tab has two parts:

- **Needs attention**: your own items the office rejected or flagged, or that the server did not accept. Examples are a meter reading, expense, fuel event, cash collection, cash handover, job step or photo upload. Tap one to open it.
- **Notifications** from Asseta and the office, for example:
  - "Expense approved" / "Expense rejected"
  - "Job J-…: opening/closing reading missing"
  - "Cash not handed over"
  - Tracking alerts on your machines

Tap a notification to open the related job, expense or Money screen. Use **Mark all as read** to clear the unread badge. Offline, you see the notifications saved on the phone.

### A10. Account menu

Tap the person icon (top-left of the first screen of each tab):

- **Switch company**: shown only if you work for more than one company.
- **Notifications on this phone**: shows **On**, **Off — allow notifications in Settings**, or **Not registered yet** (tap **Turn on**).
- **Change password**: opens the secure Asseta sign-in page. You need a connection, and you stay signed in. *What you'll see:* "Password changed."
- **Sign out**: asks **Sign out?** first, and warns you if items are not synced.

---

<a id="working-from-a-laptop-web-console"></a>
## Part B: Working from a laptop (web console)

Everything above can also be done in the web console at <https://asseta.co.tz> under **Field work**. The web console needs a connection and does not work offline.

Differences from the phone:

- The browser **does not read the meter automatically**. Upload a photo of the meter and type the reading. If your company requires **Automatic** mode, a reading recorded in the browser has no automatic reading and is listed for office review.
- The browser asks for your **location** when you record a reading. Allow it. Without it, the reading is marked for review.

### B1. My jobs

**Field work → My jobs** has three sections:

- **In progress**
- **Ready to start** (approved jobs)
- **Recently closed** (the last 10 completed)

Click **Open** on a job.

### B2. The job page

The top of the job page shows a progress bar with five steps:

**Opening reading → Start job → Closing reading → Customer acknowledgement → Complete job**

Below the steps is a sentence telling you what to do now, and the main button for that step:

1. **Record opening reading**. The dialog **Record opening reading · J-…** shows your company's rules: Required mode, Photo for manual readings, what happens Without valid GPS, GPS max accuracy and GPS max fix age. Then:
   1. Choose the **Capture mode** (**Automatic** or **Manual**). Use the one the policy requires.
   2. Enter the **Meter reading (hours)**.
   3. Add the **Meter photo**.
   4. Wait for the GPS attempt ("Attempting a GPS fix with this browser…") to finish.
   5. Click **Submit reading**.

   *What you'll see:* a result box:
   - **Accepted**: "The reading was accepted."
   - **Provisional — requires review**: "The reading was kept and counts for the job, and the findings below are listed for office review."
   - **Rejected**: "The reading was stored as evidence but not accepted under the policy. Record it again (for example once a GPS fix is available)."
2. **Start job**. You can add a **Note (optional)**, then confirm.
3. **Record closing reading**. Same as the opening reading.
4. **Record customer acknowledgement**.
   1. Choose the **Method**: **Name confirmation** or **Signature image**. For a signature, choose **Sign on screen** (draw with the mouse or touch screen) or **Upload image**.
   2. Enter the **Customer representative** and optionally **Phone** and **Acknowledged hours**.
   3. Set **Acknowledged at**.
   4. Click **Record acknowledgement**.
5. **Complete job**.

While the job is approved or running, you also have these buttons:

- **Log work**. The **Log activity** dialog asks for:
  - **Type**: Work, Standby, Downtime, Mobilization or Note.
  - **Billable override**: Default, Billable or Non-billable.
  - **Note**.
  - **Start** and **End (optional)**. An entry without an end stays open and is not counted until ended.
- **Record fuel**. Opens **Record fuel event**. The steps match [A4](#a4-fuel).
- **Record expense**. Opens **Record expense**. The steps match [A5](#a5-expenses). The dialog has three steps: **Expense**, **Attribution & payment** and **Receipts & GPS**.

A line shows the work totals, for example "Work 5 h 10 min · Standby 1 h 00 min · Downtime 0 h 30 min".

Lower on the page you see the job's details (rate, minimum hours, standby terms, readings, **Billing ready** or **Not billing ready**, open exceptions) and these tabs:

- **Readings & evidence**
- **Work log**
- **Acknowledgement**
- **Expenses & fuel**
- **Meter resets**: requests for this machine. Use the **Request meter reset** button here. You'll be asked for:
  - **Old meter reading (before)**
  - **New meter reading (after)**
  - **Effective time**
  - **Reason** (at least 10 characters)
  - **Supporting evidence (optional)**

### B3. Readings, Fuel, Expenses, Cash pages

- **Field work → Readings**: your readings with filters for **State** and **Reading** (Opening/Closing). Click a reading to see its photo, GPS, findings and the office's review note, and **Open job**.
- **Field work → Fuel**: your fuel events. Click **Record fuel** to add one.
- **Field work → Expenses**: grouped into **Waiting for approval**, **Rejected** and **Approved**, with the **Office note**. Click **Submit expense** to add one.
- **Field work → Cash**:
  - Your custody per currency and **Today's reconciliation**, using the same calculation as the phone.
  - Tabs **My collections** and **My handovers**, with status and office notes.
  - **Record cash collection**. Three steps: Collection, Details, then Review. Choosing a job fills its customer. Afterwards you see: "Cash collection recorded; it is claimed until the office verifies it."
  - **Hand over cash**. Afterwards you see: "Handover recorded; it is claimed until the office verifies it."

---

## Statuses and what they mean

### Job status

| Status | Meaning | What you can do |
|---|---|---|
| Draft / Pending approval | The office is preparing or approving the job and its price | Nothing yet; it reaches you once approved |
| **Approved** (Ready to start) | Approved with an agreed price | Take the opening reading, then start |
| **In progress** | Running | Log work, take the closing reading, get the acknowledgement, complete |
| **Completed** | Finished | Nothing; records are kept as captured |
| Cancelled | Stopped by the office (a reason is recorded) | Nothing |

On the phone, "· not synced" after a status means your action is saved on the phone but not yet sent.

### Reading status

| Status | Meaning |
|---|---|
| Waiting to sync / Not synced / Synced | Phone-side: sent to Asseta or not yet |
| **Accepted** | Fine; no finding needing review |
| **Provisional** (web: "Provisional — requires review") | Kept and counts for the job, but at least one finding must be reviewed. Invoicing waits until the review is done |
| **Flagged** (phone) | The office is reviewing a finding on this reading |
| **Reviewed** (phone) | The office has reviewed the findings |
| **Rejected** | Stored as evidence but not used, usually because your company requires GPS and there was no valid fix. Take the reading again |
| Superseded | Replaced by an approved correction |

Each finding is shown as **Waiting for review**, **Explained** (a legitimate reason was found) or **Confirmed** (the discrepancy stands as recorded). **Blocking** findings stop the job from being invoiced until reviewed.

### Money status

| Record | Statuses |
|---|---|
| Expense | Pending approval → Approved / Rejected (small amounts are approved automatically) |
| Cash collection, handover | Awaiting verification (web: "Claimed (unverified)") → Verified / Rejected |
| Meter reset request | Pending → Approved / Rejected |

### Sync status (phone)

| Status | Meaning |
|---|---|
| Waiting to sync / Sending | Normal; waiting for a connection |
| Synced | Confirmed by the server |
| Rejected | The server refused it; see the reason and **Retry** after fixing the cause |
| Conflict | The job changed on the server; your record is kept for review |
| Held | Kept by the server while the subscription is read-only; applied after reactivation |

## Good practice

- **Sync before you leave for site.** Pull down on Jobs while you have signal.
- **One fresh photo per reading.** Never reuse a photo, not even for the same meter on the same day.
- **Check the number before saving.** Correct the camera's reading if needed. A correction is normal; a wrong number is not.
- **Stand next to the machine** when taking a reading, outdoors if possible, so GPS matches the tracker.
- **Log standby and downtime as they happen**, with a short note. This protects billing for both you and the customer.
- **Keep your phone clock on automatic** date and time.
- **Hand over cash regularly** and keep the deposit slip or receipt number as your reference.
- **Don't sign out with unsent items** unless you must.
- **Read your Inbox daily.** It is where office decisions and reminders arrive.

## Troubleshooting and FAQ

**My job is not in the list.**
Pull down to sync. Jobs appear only once **approved** and assigned to you or your machine. Ask the office to check.

**"Capture the opening reading first." / "Get the customer acknowledgement first."**
Asseta enforces the order: opening reading → start → closing reading → acknowledgement → complete.

**"Stop the running work-log entry first."**
A Work, Standby or Downtime entry is still running. Tap its **Stop** button.

**The camera can't read the meter.**
Clean the glass, avoid reflections, get closer and retake. After the allowed tries you can type the reading. The photo is kept as evidence.

**No GPS fix.**
Go outdoors, wait a few seconds and tap **Try location again**. You can still save. The reading is marked for review. If your company uses strict GPS rules, the reading is **Rejected** and you must take it again once you have a fix.

**"Connect to refresh rules…"**
Your phone's copy of the company rules has expired, or you have been offline too long. Get any connection and pull down to sync.

**An item is under "Needs attention: rejected".**
Open it to see the reason. Fix the cause (for example, choose an active customer) and tap **Retry**, or ask the office. Your evidence is kept.

**"This phone's clock is N minutes fast/slow…"**
Set the phone's date and time to automatic. Readings still record the phone's time, but a big difference is flagged for review.

**"This job is no longer assigned to you."**
The office reassigned or cancelled it. Your records are kept and the office sees them.

**The app says my device was revoked.**
Your administrator revoked this phone (for example, it was reported lost), and its local data was erased. Contact your administrator before signing in again.

**"The photo is not on this phone. Connect to view it."**
Older photos are fetched from the server when you are online.

**I forgot my password.**
Ask your company's administrator (normally the owner) to reset it. You will then set a new password at your next sign-in.

**The web console says I can't record a reading in Automatic mode.**
The browser cannot read the meter. Choose the mode your policy requires, upload the photo and type the value. A browser "Automatic" reading is listed for review. Use the phone app when you can.
