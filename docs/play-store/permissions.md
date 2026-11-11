# Permissions and why each is needed

Source: `mobile/android/app/supervisor/src/main/AndroidManifest.xml`, `mobile/android/app/owner/src/main/AndroidManifest.xml`
(release 0.5.5 (8) and 0.8.0 (3)), checked against the merged manifests of the signed release builds with
`aapt2 dump permissions` on 2026-11-12.

Library manifests add these normal (install-time, not runtime) permissions: `WAKE_LOCK`, `RECEIVE_BOOT_COMPLETED` and
`FOREGROUND_SERVICE` (WorkManager background sync, Supervisor), `com.google.android.c2dm.permission.RECEIVE` (Firebase
Messaging, both; inactive while push is off) and a `DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION` signature permission
(AndroidX, both).

**Owner 0.8.0 (3) as built also lists `ACCESS_FINE_LOCATION`, `ACCESS_COARSE_LOCATION` and `ACCESS_WIFI_STATE`,**
merged in from the MapLibre map library. The Owner app never asks for them, so Android never grants them and the app
cannot read the phone's location. The manifest now removes them (`tools:node="remove"` in
`app/owner/src/main/AndroidManifest.xml`), so the next Owner build no longer lists them. See `release-checklist.md`
step 0 for whether to rebuild before the first upload.

| Permission | Supervisor | Owner | Why |
|---|---|---|---|
| `INTERNET` | Yes | Yes | Talk to the company's Asseta server (asseta.co.tz) over HTTPS: sign-in, sync, approvals. |
| `ACCESS_NETWORK_STATE` | Yes | Yes | Know whether the phone is online, to show the offline banner and sync as soon as a connection returns. |
| `CAMERA` | Yes | No | Take the hour-meter photo (the number is read on the phone), and photos of receipts and payment slips. Asked the first time the user opens a capture screen, with an explanation. |
| `ACCESS_FINE_LOCATION` | Yes | No | Stamp the GPS position on a reading or record at the moment it is captured, as evidence of where the work was done. Foreground only, while the capture screen is open. The user can decline and continue; the record is then saved without location and flagged. |
| `ACCESS_COARSE_LOCATION` | Yes | No | Required by Android alongside fine location (Android 12+ lets the user grant only approximate location); same use as above. |
| `POST_NOTIFICATIONS` | Yes | Yes | Android 13+ permission to show notifications. Asked when the user opens the Inbox (Supervisor) or turns on push in Settings (Owner). Push delivery (FCM) is not enabled in this release, so in practice no notifications are posted yet; the permission is kept so that enabling push later needs no new release. |

Not requested: `ACCESS_BACKGROUND_LOCATION` (no background tracking; machines have their own trackers), contacts,
storage, microphone, phone state, SMS, calendar, accounts. The apps disable Android backups of their data
(`allowBackup=false`).

## Play Console declarations this triggers

- **Location permissions declaration:** not required, because the apps do not request background location.
- **Foreground service declaration:** not expected: the build lists plain `FOREGROUND_SERVICE` but no
  `FOREGROUND_SERVICE_<type>` permission. If the Console still asks, the purpose is "Data sync: uploading field records
  captured offline when the connection returns".
- **Camera / photo and video permissions:** the apps use the camera directly (CameraX) and do not request
  `READ_MEDIA_IMAGES`, so no Photo and video permissions declaration is needed.
