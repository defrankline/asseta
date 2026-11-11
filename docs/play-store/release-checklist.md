# Google Play release checklist (organisation account)

Publisher: **Crysalion Tech Company Ltd** (Google Play organisation developer account). Support email
frank.kachinga@gmail.com, website https://asseta.co.tz.

| App | Package | Version | Signed AAB |
|---|---|---|---|
| Asseta Supervisor | `com.asseta.supervisor` | 0.5.5 (8) | `~/Documents/Asseta-apps/play/Asseta-Supervisor-0.5.5-8.aab` |
| Asseta Owner | `com.asseta.owner` | 0.8.0 (3) | `~/Documents/Asseta-apps/play/Asseta-Owner-0.8.0-3.aab` |

Both AABs are signed with our release key: keystore `~/.asseta/asseta-release.jks`, alias `asseta-release`
(passwords in `~/.asseta/release-signing.properties`, never in the repo). We keep this key as the **app signing key**
in Play App Signing.

Everything to paste or upload lives next to this file:

| What | File |
|---|---|
| Store listing text (EN + SW) | `listing-supervisor.md`, `listing-owner.md` |
| Release notes (EN + SW) | `release-notes.md` |
| Data safety answers | `data-safety.md` |
| Content rating answers | `content-rating.md` |
| App access (reviewer login instructions) | `app-access.md` |
| Permission reasons | `permissions.md` |
| Icon, feature graphic | `graphics/<app>/icon-512.png`, `graphics/<app>/feature-1024x500.png` |
| Logos for the website / other listings | `graphics/logo-1024.png`, `graphics/logo-wide.png` (SVG sources in `graphics/src/`) |
| Screenshots | `screenshots/<app>/{phone,tablet-7,tablet-10}/` |
| Privacy policy URL | https://asseta.co.tz/privacy (`web/public/privacy.html`) |
| Account deletion URL | https://asseta.co.tz/account-deletion (`web/public/account-deletion.html`) |

---

## 0. Before you start

- [ ] Deploy the web (`scripts/deploy-live.sh`) so both public pages are live, then open
      https://asseta.co.tz/privacy and https://asseta.co.tz/account-deletion on a phone. Each must show its page, not
      the Asseta console. (The nginx site templates were changed to serve them; a deploy re-renders and reloads the
      host nginx site.)
- [ ] Demo logins for Google's reviewers exist and work in the demo company: one supervisor, one owner/manager
      (`app-access.md`). Keep the passwords out of every file; you type them into the Console only.
- [ ] Screenshots: all 8 phone + 8 tablet-7 + 8 tablet-10 per app (section 9 below captures them).
- [ ] Owner AAB decision. Owner 0.8.0 (3) as built lists `ACCESS_FINE/COARSE_LOCATION` and `ACCESS_WIFI_STATE`,
      pulled in by the MapLibre map library and never requested at runtime. The repo now removes them. Either upload
      0.8.0 (3) as is (the Data safety answer "no location" is still true), or, cleaner, rebuild Owner first as
      0.8.1 (4) with section 8 and upload that. Recommended: rebuild, so the permission list in Play matches the
      privacy policy.

## 1. Create both apps

Play Console → **Home → Create app**, once per app:

- [ ] App name: `Asseta Supervisor` / `Asseta Owner`
- [ ] Default language: English (United States) – en-US
- [ ] App or game: **App**; Free or paid: **Free**
- [ ] Accept the Developer Program Policies and US export laws declarations → **Create app**

Organisation accounts are not subject to the "12 testers for 14 days" closed-testing rule that applies to new
personal accounts, so production can follow internal testing directly.

## 2. Play App Signing with our existing key (PEPK)

Per app: **Test and release → Setup → App signing** (older Consoles: Release → Setup → App integrity → App signing).
Do this before the first upload, because the first upload otherwise makes Google generate a new key.

- [ ] Choose **Use a different key** (or "Change app signing key") → **Export and upload a key from Java keystore**.
- [ ] Download **pepk.jar** and the **encryption public key** (`encryption_public_key.pem`) that the Console shows.
      Save them in a scratch folder outside the repo.
- [ ] Run (Java 11+), entering the keystore and key passwords when asked:

      java -jar pepk.jar \
        --keystore="$HOME/.asseta/asseta-release.jks" \
        --alias=asseta-release \
        --output=asseta-release-supervisor.zip \
        --include-cert \
        --rsa-aes-encryption \
        --encryption-key-path=encryption_public_key.pem

      (`asseta-release-owner.zip` for the Owner app; download that app's encryption key from its own page.)
- [ ] Upload the zip on the same page → **Save**.
- [ ] Upload key: the Console asks for an upload certificate. Simplest: use the same key (our AABs are signed with
      it). To register it explicitly: `keytool -export -rfc -keystore "$HOME/.asseta/asseta-release.jks" -alias
      asseta-release -file upload_certificate.pem` and upload `upload_certificate.pem`.
- [ ] Afterwards the page shows the app signing key's SHA-256; it must match
      `keytool -list -v -keystore "$HOME/.asseta/asseta-release.jks" -alias asseta-release`.
- [ ] Delete the generated zip and pem files.

## 3. Internal testing first

Per app: **Test and release → Testing → Internal testing**.

- [ ] Testers: create an email list (yourself and the testers) → Save. Copy the opt-in link.
- [ ] **Create new release** → upload the AAB from the table above (or the rebuilt one).
- [ ] Release name: `0.5.5 (8)` / `0.8.0 (3)`. Release notes: paste from `release-notes.md` (both `<en-US>` and `<sw>`).
- [ ] **Next → Save and publish**. Open the opt-in link on a phone, install from Play, sign in, check the main screens.
- [ ] If the app was installed from an APK before, uninstall it first (different installer, same key is fine).

## 4. Store listing

Per app: **Grow users → Store presence → Main store listing** (older: Grow → Store presence → Main store listing).

- [ ] App name, short description, full description: from `listing-<app>.md` (English).
- [ ] App icon: `graphics/<app>/icon-512.png` (512×512, 32-bit PNG).
- [ ] Feature graphic: `graphics/<app>/feature-1024x500.png` (1024×500, 24-bit PNG, no alpha).
- [ ] Phone screenshots: `screenshots/<app>/phone/` (8, 1080×1920).
- [ ] 7-inch tablet screenshots: `screenshots/<app>/tablet-7/` (8, 1200×1920).
- [ ] 10-inch tablet screenshots: `screenshots/<app>/tablet-10/` (8, 1600×2560).
- [ ] **Manage translations → Add your own translation text → Swahili (sw)**: short and full description from the
      Swahili section; leave the name and graphics as default.
- [ ] **Store settings**: Category **Business**; tags Business, Productivity; contact email frank.kachinga@gmail.com,
      website https://asseta.co.tz.
- [ ] Save.

## 5. App content (Policy and programs → App content), per app

- [ ] **Privacy policy**: `https://asseta.co.tz/privacy`
- [ ] **App access**: All or some functionality is restricted → instructions from `app-access.md`; enter the demo
      username and password in the form.
- [ ] **Ads**: **No, my app does not contain ads.**
- [ ] **Advertising ID** (asked because target SDK ≥ 33): **No** (the apps do not use the advertising ID; no
      `AD_ID` permission in the build).
- [ ] **Content rating**: questionnaire from `content-rating.md`.
- [ ] **Target audience and content**: age groups **18 and over** only; not appealing to children.
- [ ] **News apps**: **No**.
- [ ] **COVID-19 contact tracing and status apps**: not applicable / No (if shown).
- [ ] **Data safety**: answers from `data-safety.md`; data deletion URL `https://asseta.co.tz/account-deletion`.
- [ ] **Government apps**: **No** (not developed by or for a government).
- [ ] **Financial features**: if asked, **"My app doesn't provide any financial features"**. Asseta records a
      company's own cash, expenses and customer payments as bookkeeping; it does not move money, lend, hold funds,
      trade or provide banking or payment services.
- [ ] **Health apps**: **No** (if shown).
- [ ] Permissions declarations: none needed (no background location, no SMS/call log, no all-files access, no
      photo/video media permissions). See `permissions.md`.

## 6. Countries and production

- [ ] **Test and release → Production → Countries / regions**: add Tanzania (and any other countries you sell in, or
      all countries).
- [ ] **Production → Create new release** → **Add from library** (promote the internal-testing AAB) → paste the
      release notes → **Next**.
- [ ] Rollout: 100% for a first release (or a staged rollout percentage if you prefer).
- [ ] **Publishing overview → Send changes for review**. First reviews of an organisation app usually take a few days.
- [ ] Optional: **Publishing overview → Managed publishing** on, so an approved update only goes live when you press
      Publish.

## 7. After approval

- [ ] Open both Play listings on a phone; install; sign in.
- [ ] Share the Play links with the hire companies; stop distributing APKs.
- [ ] Keep the demo reviewer logins active (reviews recur on every update).

---

## 8. Building the next version

Release signing reads `~/.asseta/release-signing.properties` (storeFile, storePassword, keyAlias, keyPassword); without
it the release build is unsigned.

1. Bump the version in the app's Gradle file. `versionCode` must be higher than any code already uploaded to Play:
   - Supervisor: `mobile/android/app/supervisor/build.gradle.kts` → `versionCode = 9`, `versionName = "0.5.6"` (example)
   - Owner: `mobile/android/app/owner/build.gradle.kts` → `versionCode = 4`, `versionName = "0.8.1"` (example)
   - Make the matching change in the iOS app (platform parity).
2. Build the signed bundle:

       cd mobile/android
       ./gradlew :app:supervisor:bundleRelease     # or :app:owner:bundleRelease
       ./gradlew --stop

   Output: `mobile/android/app/supervisor/build/outputs/bundle/release/supervisor-release.aab`
   (`app/owner/.../owner-release.aab`).
3. Check signature and version:

       jarsigner -verify -verbose:summary app/supervisor/build/outputs/bundle/release/supervisor-release.aab
       keytool -printcert -jarfile app/supervisor/build/outputs/bundle/release/supervisor-release.aab

   The SHA-256 must match the app signing key shown in the Console.
4. Copy it to `~/Documents/Asseta-apps/play/Asseta-<App>-<versionName>-<versionCode>.aab`.
5. Play Console → Internal testing → Create new release → upload → release notes (≤ 500 characters per language) →
   test → promote to Production.

## 9. Screenshots: capture commands

Play rules: PNG or JPEG, each side 320–3840 px, long side at most 2× the short side, up to 8 per device type. The
emulator's native 1344×2992 breaks the 2× rule, so the display is switched temporarily and **always restored**.

Prerequisite: the app is installed on the running emulator and **signed in** (Supervisor: a demo supervisor; Owner: a
demo owner/manager). Never save or submit anything while capturing: navigate, capture, go back.

```sh
ADB=/Users/pse/Library/Android/sdk/platform-tools/adb
APP=supervisor          # or owner
PKG=com.asseta.$APP
OUT=docs/play-store/screenshots/$APP

# One display size at a time: phone, then 7-inch, then 10-inch tablet.
#   phone:     $ADB shell wm size 1080x1920; $ADB shell wm density 420; DIR=phone
#   tablet-7:  $ADB shell wm size 1200x1920; $ADB shell wm density 240; DIR=tablet-7
#   tablet-10: $ADB shell wm size 1600x2560; $ADB shell wm density 320; DIR=tablet-10
mkdir -p "$OUT/$DIR"
$ADB shell am force-stop $PKG
$ADB shell am start -W -n $PKG/.MainActivity     # relaunch so it redraws at the new size

# For each screen: navigate in the emulator window (or adb shell input tap X Y), wait for it to settle, then:
$ADB exec-out screencap -p > "$OUT/$DIR/02-jobs.png"

# Check every file's real size:
sips -g pixelWidth -g pixelHeight "$OUT"/*/*.png

# ALWAYS restore at the end:
$ADB shell wm size reset
$ADB shell wm density reset
```

Suggested 8 screens:

- **Supervisor:** Jobs list; a job's detail; Money tab; My petty cash; Customers list; Sell customer hours (with the
  total and payment lines filled, not saved); My machines; Sync status (alternatives: Inbox, Fuel, Readings).
- **Owner:** Overview (accountability dashboard); Approvals list; an approval's detail; Fleet map; a machine's detail;
  Jobs; Cash with supervisors; Notifications (alternatives: Field spend, Meter exceptions).

Name files with a two-digit order prefix (`01-…png` to `08-…png`); Play shows them in upload order.
