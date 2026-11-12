# Google Play Data safety form

Play Console → the app → Policy and programs → App content → Data safety. Fill it once per app. The answers below
follow the order of the form. They are based on the release code (manifests, `mobile/android/README.md`,
`core/network`, `core/security`, `core/sync`, `app/*`) as of Supervisor 0.5.6 (9) and Owner 0.8.2 (5).

Key facts behind the answers:

- All traffic goes over HTTPS to the company's Asseta account on asseta.co.tz (operated by Crysalion Tech Company Ltd).
- On the phone, data is in an SQLCipher database and AES-GCM encrypted files with Android Keystore keys; backups are
  off; sign-out wipes it except records not yet sent (kept encrypted until sent); account deletion wipes all of it.
- No ads SDK, no advertising ID, no analytics SDK, no crash reporter. Firebase Messaging is compiled in but has no
  Firebase config in this release, so it never starts and sends nothing (push is not enabled).
- **Google ML Kit text recognition** (bundled, Supervisor only) reads the hour-meter photo on the phone. Google's ML
  Kit data disclosure (developers.google.com/ml-kit/android-data-disclosure) says the SDK sends Google device
  information, app package and version, a per-installation identifier, performance metrics, API configuration and
  error codes "for diagnostics and usage analytics", encrypted over HTTPS, and does not transfer it to third parties.
  That is declared below as collected (Diagnostics, Device or other IDs; purpose Analytics).
- **Owner fleet map** downloads raster tiles from OpenStreetMap's tile servers (default `asseta.mapTileUrl`). Those
  requests carry only the tile coordinates, the phone's IP address and the app's User-Agent; no user data. Not
  declared (no Play data type is sent).
- Service providers that process data on our behalf (our hosting provider) are not "sharing" under Play's definitions.
  Crysalion processes the data on behalf of the hire company, which is not a third party for its own data.

---

## Section 1: Data collection and security

| Question | Answer (both apps) |
|---|---|
| Does your app collect or share any of the required user data types? | **Yes** |
| Is all of the user data collected by your app encrypted in transit? | **Yes** |
| Which of the following methods of account creation does your app support? | **Username and password** (see note 1). Logins are created by the user's company, not by public sign-up. |
| Do you provide a way for users to request that their data is deleted? / Delete account URL | **Yes.** URL: **https://asseta.co.tz/account-deletion** |
| Can users request that some or all of their data is deleted without deleting their account? | **Yes** (see note 2) |

Deletion, as the page describes it: a user deletes their own login in the app or on the web (Delete my account: web My access, Supervisor account
menu, Owner Settings; name, email and phone wiped at once; records made for the company stay with the company as "Former user");
a company owner closes the company on the web (Administration → Close company; 30-day read-only grace period, then
everything is deleted permanently); anyone who cannot sign in emails frank.kachinga@gmail.com and gets a reply within
30 days.

Note 1 (uncertain): the form asks how users create accounts. Our users never create accounts in the app; the company
administrator creates them on the web. Choosing "Username and password" is the conservative answer: it keeps the
account deletion URL requirement and matches what users see (they sign in with a username/email and password). If the
Console offers an option such as "My app does not allow users to create an account" together with a question about
logins created outside the app, choose that pairing instead and still give the deletion URL.

Note 2: a user can ask their company administrator to correct or remove personal details, and can email us; the
account-deletion page covers deleting the login itself.

---

## Section 2: Data types

For every type below: **Shared = No**, **Processed ephemerally = No**. "Collected" means it leaves the phone and is
stored on the company's Asseta account (or, for ML Kit metrics, sent to Google).

### Asseta Supervisor (`com.asseta.supervisor`)

| Category | Data type | Collected | Required or optional | Purposes |
|---|---|---|---|---|
| Location | **Precise location** | Yes | **Optional** (the app asks at capture time; the user can continue without location and the record is flagged) | App functionality; Fraud prevention, security, and compliance |
| Location | **Approximate location** | Yes (if the user grants only approximate) | Optional | App functionality; Fraud prevention, security, and compliance |
| Personal info | **Name** | Yes (the user, staff, customers) | Required | App functionality; Account management |
| Personal info | **Email address** | Yes (the user's sign-in) | Required | App functionality; Account management |
| Personal info | **User IDs** | Yes (account and person ids on every record) | Required | App functionality; Account management; Fraud prevention, security, and compliance |
| Personal info | **Phone number** | Yes (customer phone numbers the user enters) | Optional | App functionality |
| Financial info | **Other financial info** | Yes (cash collected and handed over, expenses, petty cash, customer hours sales, payment method and references) | Required | App functionality; Fraud prevention, security, and compliance |
| Photos and videos | **Photos** | Yes (hour-meter, receipt and payment-slip photos) | Required (evidence for those records) | App functionality; Fraud prevention, security, and compliance |
| App activity | **Other user-generated content** | Yes (job records, readings, notes, customer signatures, acknowledgements) | Required | App functionality |
| App info and performance | **Diagnostics** | Yes (ML Kit SDK metrics to Google; see above) | Required (cannot be turned off in the app) | Analytics |
| Device or other IDs | **Device or other IDs** | Yes (random per-install device id created by the app, sent as `X-Device-Id` for offline sync; ML Kit's per-installation id) | Required | App functionality; Fraud prevention, security, and compliance; Analytics |

Not collected by Supervisor: Personal info (Address, Race and ethnicity, Political or religious beliefs, Sexual
orientation, Other info), Financial info (User payment info, Purchase history, Credit score), Health and fitness,
Messages, Photos and videos (Videos), Audio, Files and docs, Calendar, Contacts, App activity (App interactions,
In-app search history, Installed apps, Other user actions), Web browsing, App info and performance (Crash logs, Other
app performance data). If the Console's description of "Diagnostics" vs "Other app performance data" makes the ML Kit
latency metrics fit better under "Other app performance data", tick that too with the same answers.

### Asseta Owner (`com.asseta.owner`)

| Category | Data type | Collected | Required or optional | Purposes |
|---|---|---|---|---|
| Personal info | **Name** | Yes (the user; names entered on jobs and decisions) | Required | App functionality; Account management |
| Personal info | **Email address** | Yes (the user's sign-in) | Required | App functionality; Account management |
| Personal info | **User IDs** | Yes | Required | App functionality; Account management; Fraud prevention, security, and compliance |
| Personal info | **Phone number** | Yes (customer phone on a new job, when entered) | Optional | App functionality |
| Financial info | **Other financial info** | Yes (approval decisions on petty cash and money records, cash handover confirmations) | Required | App functionality; Fraud prevention, security, and compliance |
| App activity | **Other user-generated content** | Yes (approval and rejection reasons, notes, new jobs) | Required | App functionality |

Not collected by Owner: Location (it shows machines' tracker positions from the server, but never reads the phone's
location; no location permission), Photos (it only displays evidence photos), Device or other IDs (no device id is
sent; the push device registration is not active in this release), App info and performance, and all other types.

When push (FCM) is enabled in a later release, update both apps: add **Device or other IDs** (FCM token, device
make and model as the push device label) for App functionality, and review Firebase's own disclosure.

---

## Section 3: Review and submit

Check the preview against `web/public/privacy.html` (served at https://asseta.co.tz/privacy): the policy states the
same types, purposes, no sharing, encryption in transit, and deletion.

## Points to double-check (uncertain)

1. Account creation method (note 1 above).
2. Whether data a user enters about *other people* (customer names and phones) must be declared: Google says yes
   ("data about others that users provide"), so it is declared.
3. ML Kit: Google's disclosure page does not name text recognition explicitly; its "all features" table is applied
   here. Declaring Diagnostics and Device IDs for Analytics is the conservative reading.
4. Photos "Required": capture screens require evidence photos for meter readings and receipts per company policy; if a
   company's policy makes them optional, the answer can still stay "Required" (the strict reading).
5. Owner 0.8.2 (5) declares no location or Wi-Fi permissions (the map library's ones are removed in the manifest),
   so "Location: not collected" matches the bundle.
6. Owner app collection is minimal because it mostly displays data; what it sends is decisions, notes and new jobs.
