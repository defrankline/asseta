#if os(iOS)
import AssetaAppShell
import AssetaCapture
import AssetaModel
import AssetaStore
import AssetaSync
import SwiftUI

// DEC-031 Phase 5 (M3, Supervisor): the "Site check-in" row on the Jobs tab and the Site check-ins screen. The schedule
// is read online and saved (encrypted) for offline; "Check in now" takes one fresh GPS attempt (as meter readings)
// and queues `SITE_CHECKIN`, so it works offline. Same screens and wording as Android.

private typealias T = SiteCheckinTexts

extension FieldModel {
    /// Reads my check-in schedule (online, check-in gate open) and re-reads the saved lists.
    func refreshSiteCheckins() async {
        guard access.siteCheckin, isOnline, let online else { return }
        await online.refreshSiteCheckins()
        refresh()
    }

    var checkinSchedule: SavedOnline<MySiteCheckinsDTO>? { accountabilityData?.siteCheckins }
    var myCheckins: [CheckinItem] { accountabilityData?.myCheckins() ?? [] }
}

/// The Jobs tab row: due slot (in warning), else the next one today, else none left; before the first read, where the
/// times will appear. Opens Site check-ins.
struct SiteCheckinEntryRow: View {
    let model: FieldModel

    var body: some View {
        let _ = model.accountabilityTick
        NavigationLink(value: FieldRoute.siteCheckins) {
            TimelineView(.everyMinute) { context in
                let schedule = model.checkinSchedule?.value
                let items = model.myCheckins
                let due = SiteCheckinPresentation.today(schedule, items: items, now: context.date).contains { $0.state == .due }
                VStack(alignment: .leading, spacing: 2) {
                    Text(T.entry).font(.headline)
                    Text(SiteCheckinPresentation.jobsSubtitle(schedule, items: items, now: context.date))
                        .font(.subheadline).foregroundStyle(due ? Palette.warning : .secondary)
                }
                .accessibilityElement(children: .combine)
            }
        }
        .accessibilityIdentifier("checkin.entry")
    }
}

/// "Site check-ins": today's slots (footer: what the company asks), Check in now, then my check-ins.
struct SiteCheckinView: View {
    let model: FieldModel
    @State private var locating = false
    @State private var message: (text: String, error: Bool)?

    var body: some View {
        let _ = model.accountabilityTick
        let saved = model.checkinSchedule
        let schedule = saved?.value
        let zone = SiteCheckinPresentation.timeZone(schedule)
        let items = model.myCheckins
        TimelineView(.everyMinute) { context in
            List {
                Section {
                    let slots = SiteCheckinPresentation.today(schedule, items: items, now: context.date)
                    if saved == nil {
                        Text(T.never).foregroundStyle(.secondary)
                    } else if slots.isEmpty {
                        Text(T.todayEmpty).foregroundStyle(.secondary)
                    }
                    ForEach(slots, id: \.scheduledAt) { slot in
                        HStack {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(slot.time).font(.headline)
                                Text(slot.window).font(.caption).foregroundStyle(.secondary)
                            }
                            Spacer()
                            Pill(text: T.status(slot.state), color: color(slot.state))
                        }
                        .accessibilityElement(children: .combine)
                    }
                } header: {
                    Text(T.today)
                } footer: {
                    Text(SiteCheckinPresentation.footer(schedule, savedAt: model.isOnline ? nil : saved?.fetchedAt, timeZone: zone))
                }
                Section {
                    if locating {
                        HStack { ProgressView(); Text(T.locating) }
                    } else {
                        Button { Task { await checkIn() } } label: { Text(T.action).frame(maxWidth: .infinity) }
                            .buttonStyle(.borderedProminent)
                            .accessibilityIdentifier("checkin.action")
                    }
                    if let message {
                        Text(message.text).font(.subheadline).foregroundStyle(message.error ? Palette.offline : .secondary)
                    }
                }
                Section(T.mine) {
                    let rows = SiteCheckinPresentation.rows(items, timeZone: zone)
                    if rows.isEmpty { Text(T.mineEmpty).foregroundStyle(.secondary) }
                    ForEach(rows) { row in
                        VStack(alignment: .leading, spacing: 2) {
                            HStack {
                                Text(row.label).font(.subheadline)
                                Spacer()
                                if !row.value.isEmpty { Text(row.value).font(.subheadline).foregroundStyle(.secondary) }
                            }
                            if let caption = row.caption { Text(caption).font(.caption).foregroundStyle(tone(row.tone)) }
                        }
                        .accessibilityElement(children: .combine)
                    }
                }
            }
        }
        .navigationTitle(T.title)
        .refreshable { await model.sync(force: true); await model.refreshSiteCheckins() }
        .task { await model.refreshSiteCheckins() }
    }

    private func tone(_ tone: CheckinTone) -> Color {
        switch tone {
        case .plain: .secondary
        case .info: Color.accentColor
        case .warning: Palette.warning
        case .bad: Palette.offline
        }
    }

    private func color(_ state: SlotState) -> Color {
        switch state {
        case .made: Palette.live
        case .saved: Color.accentColor
        case .missed: Palette.offline
        case .due: Palette.warning
        case .upcoming: Palette.neutral
        }
    }

    /// One fresh GPS attempt, then the check-in is queued at the time the button was tapped (a failed attempt is
    /// recorded without coordinates).
    private func checkIn() async {
        guard let recorder = model.recorder, !locating else { return }
        locating = true
        message = nil
        let at = Date()
        let gps = await model.locator.captureFix(timeout: 20)
        locating = false
        do {
            try recorder.recordSiteCheckin(gps: gps, capturedAt: at)
            message = (T.saved, false)
            model.refresh()
            Task { await model.sync(force: true); await model.refreshSiteCheckins() }
        } catch let FieldRecorderError.notAllowed(text), let FieldRecorderError.invalid(text) {
            message = (text, true)
        } catch {
            message = (String(describing: error), true)
        }
    }
}
#endif
