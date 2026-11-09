# What the technology cannot fully enforce

Your guideline requires us to disclose any limitation before the system is approved, not after. This is that list.

A system can make dishonesty difficult, visible and traceable. It cannot observe everything that happens at a remote site. Each item below says what cannot be enforced, what the system does instead, and what the company should do.

## Field evidence

### 1. A faked GPS position is not detected

**The limit.** A phone can be made to report a false location using a fake-GPS app. The system does not detect this.

**What the system does instead.** It records the position, its accuracy and its age with every reading. It flags readings with no position, a weak or old position, or a position away from the site (**Not at the job site**). Where a tracker is fitted, it compares the phone's position with the tracker's at the same moment (**Does not match the tracker**).

**What the company should do.** Fit trackers to the machines that matter most, and keep the tracker distance check on. Choose **Hard** GPS enforcement if readings without a valid position must be refused. Spot-check sites.

### 2. A photo of a photo passes

**The limit.** The app forces the use of the camera, but it cannot tell whether the camera was pointed at the real meter or at a picture of it. In the web console a user uploads a picture file, so any image can be used there.

**What the system does instead.** The exact same photo file used twice is flagged (**Photo used before**). The meter value is read from the picture, and impossible values are flagged. Every photo is kept and can be opened by a reviewer. Readings entered in the browser have no automatic reading and are listed for review if the company requires automatic mode.

**What the company should do.** Have supervisors take readings on the phone, not in the browser. Look at the photos when reviewing flagged readings, and compare photos of the same machine for matching surroundings. Make surprise checks of the meter against the last reading.

### 3. The phone's clock is only flagged, not controlled

**The limit.** A phone's time can be changed by its user. Times on offline records are the phone's times, and times typed into a form are what the person typed.

**What the system does instead.** At every sync the phone reports its clock. If it is more than 5 minutes off (a company setting), an alert is raised. A reading dated in the future is flagged **Phone clock was wrong**. The central system stamps its own receive time on readings and sync records, so the gap is visible.

If a clock is changed, a record made, and the clock put right before the next sync, that alone raises no flag. The meter checks may still catch an impossible jump. The offline limits in [Offline and central](03-offline-and-central.md) also use the phone's clock.

**What the company should do.** Require automatic date and time on company phones. Read the **Clock difference** on any disputed reading.

### 4. Meter tampering is caught only where a tracker can compare

**The limit.** If an hour meter is slowed, disconnected or swapped, the meter itself gives no sign. The system reads what the meter shows. It has no connection to the machine.

**What the system does instead.** It flags readings that go down, jump more than the time allows, or leave a gap since the last reading. Where a tracker that reports engine data is fitted and checked, it compares the meter with the tracker (**Tracker disagrees**) and flags engine activity with no job. Without such a tracker, a meter that simply runs slowly cannot be noticed.

**What the company should do.** Fit trackers with ignition or engine-hour reporting. Compare fuel with engine hours (the fuel norm controls, off until you set them). Seal and inspect meters during servicing. Treat any meter reset request with care.

### 5. The system cannot prove who was holding the phone

**The limit.** A record shows which login and which phone made it. It cannot prove which human being was holding the phone. Passwords can be shared and phones can be passed around. The app stays signed in between uses.

**What the system does instead.** Each login is personal, each phone is registered to a login, and every record names both. The Platform Owner can revoke a phone on request; there is no screen for the company to do this itself today.

**What the company should do.** Forbid sharing of logins, in writing. Issue company phones with a screen lock. Report a lost phone to the Platform Owner at once, and when a person leaves.

### 6. Automatic meter reading can be wrong

**The limit.** The phone's reading of the digits is an aid and it can misread them.

**What the system does instead.** It shows the confidence to the supervisor and the reviewer. A low-confidence reading is retaken, and after the allowed retries it can be typed. A change to the value it read is recorded as a manual correction for the office to check.

**What the company should do.** Keep **OCR corrections require review** on and check those readings.

## People and money

### 7. Money or hours that are never recorded are invisible

**The limit.** If a customer pays cash and nobody records it, or a machine works for someone off the books with no reading taken, the system has nothing to count.

**What the system does instead.** Every engine hour between readings must be explained, so unrecorded work appears as **Not yet explained** at the next reading. With trackers, engine activity with no job is flagged. With revenue checks on, hours are compared with money. **Revenue checks are off until the company switches them on.**

**What the company should do.** Switch on revenue checks and daily reports. Send customers their **Hours statement** and tell them to ask for the number on every purchase. A customer who holds a statement is a second check on your staff.

### 8. Confirming money relies on an honest person checking a real statement

**The limit.** The system is not connected to any bank or mobile-money service. When someone records "amount received", the system cannot see the bank.

**What the system does instead.** It requires a second person, and never accepts confirmation by the person holding the cash or the person who recorded it. Slip photos are evidence only and never confirm money. A bank or mobile-money reference can be used only once. Each confirmation is recorded with the name and time.

**What the company should do.** Have confirmations done against the real bank or mobile-money statement. Give the confirming role to someone with no field duties.

### 9. Two people acting together can defeat a second-person check

**The limit.** "Nobody decides their own request" stops one person. It cannot stop two people who agree to cooperate, or someone who is using another person's login.

**What the system does instead.** Every approval names both people. The **People scorecard**, refused attempts and the audit log show patterns. Refused attempts are recorded.

**What the company should do.** Keep the people who propose and those who approve in separate reporting lines. Review the scorecard and audit log regularly. Rotate duties where practical.

### 10. Staff without a login have their cash recorded by someone else

**The limit.** An operator who holds cash but has no login cannot personally confirm anything in the system. A supervisor or manager records on their behalf, and that recorder's word is what is captured. If the company allows it, a recorder who is the receiver acknowledges a transfer just by recording it.

**What the system does instead.** The recorder is named on every record, and the operator's cash balance is calculated separately.

**What the company should do.** Give each cash holder a statement of their balance periodically, or give them the permission to acknowledge for themselves.

### 11. A customer acknowledgement is not proof of identity

**The limit.** The acknowledgement is a signature on the screen or a name typed by the supervisor. The system cannot prove who signed.

**What the system does instead.** It records the name, the phone number if given, the hours acknowledged, the time and the signature.

**What the company should do.** Prefer signatures. Agree with regular customers who may sign for them.

### 12. Controls can be switched off by those who hold the permission

**The limit.** Most controls are company settings. Someone with the policy permission (the Tenant Owner or an Administrator) can switch one off, and the Owner holds every permission.

**What the system does instead.** Each change creates a new version, with who, when and why, and it never alters past records. The rule that nobody decides their own request cannot be turned off for adjustment requests and for confirming remittances. Some other second-person checks (for example on transfers, cancellations and engine-hour explanations) are settings.

**What the company should do.** Limit who holds the policy permission. Review policy changes in the audit log.

### 13. Second-person rules need at least two people

**The limit.** A control needs two people holding the permission. If only one person holds it, their own requests wait forever.

**What the company should do.** Make sure at least two people hold each approval permission before switching a control on.

## Access and accounts

### 14. Roles edited directly in the sign-in service bypass the owner-only rule

**The limit.** Inside Asseta, only the company owner can give someone a role that approves things. That check lives in Asseta's own screens. A person with administrator access to the sign-in service could change a role or a group there directly, and Asseta would not stop it. Only the Platform Owner has that access in normal operation.

**What the system does instead.** The approver rule applies everywhere inside Asseta, and refused attempts are recorded. **Administration → Users & roles** always shows who holds which role. Role removals made directly in the sign-in service take effect when the system next refreshes its copy or the login's short-lived token expires.

**What the company should do.** Check **Users & roles** periodically, and record in your agreement with the Platform Owner that roles will only be changed on the owner's instruction.

### 15. New logins are created by the Platform Owner

**The limit.** The web console does not yet have an invite-user button, so new logins are created on request by the Platform Owner. The company can remove roles itself.

**What the company should do.** Send requests from a named person, and check **Users & roles** afterwards.

## Data and continuity

### 16. A lost or broken phone can lose what has not synced

**The limit.** Offline records exist only on that phone until they sync. There is deliberately no cloud copy. If the phone is destroyed before syncing, those records and photos are gone. Revoking a phone (done by the Platform Owner on request) wipes everything on it, including what had not been sent.

**What the system does instead.** Everything on the phone is encrypted, and the **Sync status** screen shows what has not been sent.

**What the company should do.** Sync whenever there is a signal, and before travelling. If a phone is lost but may be found, weigh that before revoking it.

### 17. The data export file is not itself encrypted

**The limit.** The file made by **Data export** is an ordinary ZIP with no password. Anyone holding it can read the company's records. It contains no passwords.

**What the system does instead.** Exports need a permission held by default only by the Tenant Owner. Every request is recorded, the download link lasts a few minutes, and the stored file is deleted automatically (after 7 days unless the company changes it).

**What the company should do.** Keep it on encrypted storage, and delete copies after use.

### 18. People who run the servers have technical access

**The limit.** The rules protect the company's records from anyone using the system. A person with direct administrator control of the servers or database works below those rules. Their direct actions would not appear in the company's audit log.

**What the system does instead.** Platform staff have no access to company data through the system without a written mandate from the company. Each action under a mandate is recorded and visible to the company. Ordinary application accounts cannot change the database structure or rewrite ledger entries.

**What the company should do.** Cover this in the agreement with the Platform Owner. Take your own [data export](06-your-data.md) periodically, so you have an independent copy.

### 19. A restore can lose up to one day of work

**The limit.** Backups are taken on a schedule, by default daily. A failure could lose the work done since the last backup. Backups cover the whole system, so a single company cannot be restored on its own without affecting others. The off-site copy is a setting the Platform Owner must configure; without it the only copy is on the same server.

**What the company should do.** Ask the Platform Owner to confirm that the daily backup and the off-site copy are in place, and when a restore was last tested.

### 20. A suspended subscription stops new data exports

**The limit.** If the company's subscription is restricted to read-only, its people can still view everything, but a new data export cannot be requested or downloaded. If the account is blocked, nobody in the company can sign in.

**What the company should do.** Take regular exports while the account is active. See [Your data](06-your-data.md).

## Things that depend on connectivity

### 21. Management only sees what has synced

**The limit.** A dashboard can only count what has reached the central system. A phone that has been out of signal for three days shows nothing for those three days. Nobody at a site can get an approval, a confirmation or a purchase number until a connection exists.

**What the system does instead.** Missing daily reports are flagged after the cut-off time, if the company switches that on. Each phone's last sync is known, and phones show what is waiting to send.

**What the company should do.** Decide how often each site must get to a signal, and make that part of the routine.

### 22. The phone does not work out what the customer owes

**The limit.** The price of an hours sale comes from the rate card and approved discount, and is worked out when the record reaches the central system. A supervisor offline types the amount they received, and the phone does not show a price to check it against.

**What the system does instead.** Hours activate only in proportion to confirmed money, and the record shows the correct amount once it arrives.

**What the company should do.** Give field staff a current price list, and check new purchases for amounts that do not match.

### 23. Trackers are outside our control until commissioned

**The limit.** A tracker can be unplugged or lose signal. The tracker connection itself is not authenticated by most manufacturers; a device is identified by its serial number. Our tests used a simulator; each real tracker model must be tested on hardware before it is relied on.

**What the system does instead.** It raises alerts when a tracker goes offline or loses power. It never treats a tracker feature as working until it has actually been observed in that tracker's data. Data from unknown devices is set aside, not used.

**What the company should do.** Treat a tracker that goes silent as something to investigate. Have the first tracker of each model checked using the commissioning steps.

## How hours get divided

### 24. The meter does not know which customer came first

**The limit.** Inside a single interval between two readings, the system cannot know the order of events. Hours over midnight are split by clock time. Unless a reading was taken at the changeover, the split between two customers is an allocation, not a measurement.

**What the company should do.** Take a reading at every changeover of customer.
