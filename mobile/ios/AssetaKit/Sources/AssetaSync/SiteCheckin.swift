import AssetaModel
import AssetaNetwork
import AssetaStore
import Foundation

// DEC-031 Phase 5 (M3) in the Supervisor app: check in at the site by GPS at the tenant's times. The check-in is
// queued offline (`SITE_CHECKIN`, GPS from the same capture as meter readings; a failed attempt is sent as such) and
// the person's own schedule (`GET /site-checkins/mine`) is read online and saved for offline use. Same as Android.

extension FieldAccess {
    /// Site check-ins are on: not switched off in `/me` (SITE_CHECKIN, off unless the tenant requires check-ins).
    public var siteCheckinOn: Bool { !disabledCapabilities.contains(TenantCapability.siteCheckin) }

    /// The Check in action: the server takes `SITE_CHECKIN` (announced only while the tenant requires check-ins), the
    /// user may record check-ins, and the capability is on.
    public var siteCheckin: Bool {
        capabilities?.contains(SyncCapability.siteCheckin) == true && permissions.contains(Self.siteCheckinRecord) && siteCheckinOn
    }

    public static let siteCheckinRecord = "tenant.site_checkin.record"
}

extension AccountabilityKey {
    static let siteCheckins = "site_checkins_mine_cache"
}

extension FieldRecorder {
    /// Queues a `SITE_CHECKIN` with the GPS attempt as it came out (`gps` is a FIX or the failed status, never
    /// invented coordinates). `clientID` (one per check-in) makes a replay return the same check-in; the server infers
    /// the job and site.
    @discardableResult
    public func recordSiteCheckin(gps: GpsPayload, capturedAt: Date, jobSiteID: UUID? = nil,
                                  clientID: UUID = UUID()) throws -> ClientOperation {
        try requireCapability(SyncCapability.siteCheckin)
        if try alreadySaved(.siteCheckin, clientID: clientID) { throw FieldRecorderError.notAllowed(FieldAccountabilityTexts.alreadySaved) }
        let payload = SiteCheckinPayload(clientID: clientID, capturedAt: capturedAt, gps: gps, jobSiteID: jobSiteID)
        return try enqueue(.siteCheckin, entityType: "site_checkin", entityID: clientID, payload: payload, dependsOn: [],
                           createdAt: capturedAt)
    }
}

/// One check-in as the field app lists it: the server's copy and/or the operation queued on this phone.
public struct CheckinItem: Identifiable, Sendable, Equatable {
    /// The client id (the server keeps it as `client_id`).
    public let id: UUID
    public let capturedAt: Date
    public let gpsStatus: String
    public let jobNumber: String?
    public let jobSiteName: String?
    public let distanceM: Double?
    public let withinDistance: Bool?
    /// The outbox state while the server does not have it yet (nil = from the server).
    public let syncStatus: ClientOperationStatus?
    public let errorCode: String?
    /// Recorded on this phone (queued, possibly acknowledged already).
    public let fromPhone: Bool
    /// On the server's saved list (`GET /site-checkins/mine`).
    public let onServerList: Bool

    /// Not accepted (failed, held or in conflict): it counts for no slot (as Android).
    public var refused: Bool { syncStatus == .conflict || syncStatus == .failed || syncStatus == .quarantined }

    init(server: SiteCheckinDTO) {
        id = server.clientID
        capturedAt = server.capturedAt
        gpsStatus = server.gpsStatus
        jobNumber = server.jobNumber
        jobSiteName = server.jobSiteName
        distanceM = server.distanceM
        withinDistance = server.withinDistance
        syncStatus = nil
        errorCode = nil
        fromPhone = false
        onServerList = true
    }

    init(local op: ClientOperation, payload: SiteCheckinPayload, server: SiteCheckinDTO?, onServerList: Bool) {
        id = op.entityID
        capturedAt = server?.capturedAt ?? payload.capturedAt
        gpsStatus = server?.gpsStatus ?? payload.gps.status.rawValue
        jobNumber = server?.jobNumber
        jobSiteName = server?.jobSiteName
        distanceM = server?.distanceM
        withinDistance = server?.withinDistance
        syncStatus = op.status == .acked ? nil : op.status
        errorCode = op.errorCode
        fromPhone = true
        self.onServerList = onServerList
    }
}

extension AccountabilityDirectory {
    /// My schedule and check-ins from the last online read (nil when never read), and when it was read.
    public var siteCheckins: SavedOnline<MySiteCheckinsDTO>? { SavedOnline.read(store, tenantID, AccountabilityKey.siteCheckins) }

    /// My check-ins, newest first: the saved server copies merged with the check-ins this phone queued (matched by
    /// client id); a queued one shows its sync state until the server has it.
    public func myCheckins() -> [CheckinItem] {
        let server = siteCheckins?.value?.checkins ?? []
        var items: [CheckinItem] = []
        var seen = Set<UUID>()
        let ops = (try? store.outbox.operations(tenantID: tenantID, owner: owner?.subject,
                                                statuses: Set(ClientOperationStatus.allCases))) ?? []
        for op in ops where op.opType == OperationType.siteCheckin.rawValue {
            guard let payload = try? JSONValue.parse(op.payloadJSON).decode(as: SiteCheckinPayload.self) else { continue }
            let acked = Self.ackedEntity(op).flatMap { try? $0.decode(as: SiteCheckinDTO.self) }
            let listed = server.first { $0.clientID == op.entityID }
            seen.insert(op.entityID)
            items.append(CheckinItem(local: op, payload: payload, server: listed ?? acked, onServerList: listed != nil))
        }
        items += server.filter { !seen.contains($0.clientID) }.map(CheckinItem.init(server:))
        return items.sorted { $0.capturedAt > $1.capturedAt }
    }
}

extension SupervisorOnline {
    /// Reads my check-in schedule of the last 7 days (`GET /site-checkins/mine`) and saves it for offline use. A
    /// refusal is saved as such; any other failure keeps the saved copy.
    public func refreshSiteCheckins() async {
        await saveSiteCheckins(APIRequest<MySiteCheckinsDTO>.get("\(Self.tenant)/site-checkins/mine"))
    }

    /// Deletes the saved schedule and check-ins (the check-in gate closed: nothing is kept, as Android).
    public func clearSiteCheckins() {
        try? store.syncState.setValue(nil, for: AccountabilityKey.siteCheckins, tenant: tenantID.uuidString.lowercased())
    }

    private func saveSiteCheckins(_ request: APIRequest<MySiteCheckinsDTO>) async {
        do {
            let response = try await client.send(request)
            try SavedOnline.write(SavedOnline(value: response, forbidden: false, fetchedAt: now()), store, tenantID,
                                  AccountabilityKey.siteCheckins)
        } catch let error as APIError where error.httpStatus == 403 || error.httpStatus == 404 || error.httpStatus == 422 {
            try? SavedOnline<MySiteCheckinsDTO>.write(SavedOnline(value: nil, forbidden: true, fetchedAt: now()), store, tenantID,
                                                      AccountabilityKey.siteCheckins)
        } catch {
            // Offline or server trouble: keep the saved copy.
        }
    }
}

/// Wording of the site check-in screens (strings doc "DEC-031 Phase 5 — oversight", `field.checkin.*`).
public enum SiteCheckinTexts {
    public static let entry = "Site check-in"
    public static let title = "Site check-ins"
    public static func due(until time: String) -> String { "Check-in due now, until \(time)" }
    public static func next(at time: String) -> String { "Next check-in at \(time)" }
    public static let noneLeft = "No more check-ins today"
    public static let today = "Today"
    public static let todayEmpty = "No check-ins are scheduled for you today."
    public static func window(from: String, to: String) -> String { "Between \(from) and \(to)" }
    public static let action = "Check in now"
    public static let locating = "Getting your location…"
    public static let saved = "Check-in saved. It is sent when the phone is online."
    public static let footer = "Your company asks you to check in at the site at these times. Your location is recorded with each check-in. Check-ins are saved on the phone and sent when you are online."
    public static func distanceFooter(_ metres: Int) -> String { "Check in within \(metres) m of the site." }
    public static let mine = "My check-ins"
    public static let mineEmpty = "No check-ins in the last 7 days."
    public static let noSite = "No site"
    public static func distance(_ metres: Int) -> String { "\(metres) m from the site" }
    public static let outside = "Further from the site than allowed"
    public static let noLocation = "Recorded without location"
    public static let waiting = "Waiting to sync"
    public static let notAccepted = "Not accepted"
    public static func savedAt(_ time: String) -> String { "Schedule from \(time). Connect to update it." }
    public static let never = "Your check-in times appear here after you connect."
    public static let outbox = "Site check-in"

    /// `field.checkin.status.*` (SAVED: a check-in on this phone covers the slot, not yet confirmed by the server).
    public static func status(_ status: SlotState) -> String {
        switch status {
        case .made: "Checked in"
        case .missed: "Missed"
        case .due: "Due now"
        case .upcoming: "Upcoming"
        case .saved: "Saved on this phone"
        }
    }

    /// `field.checkin.conflict.*`; nil for other codes.
    public static func conflict(_ code: String?) -> String? {
        switch code {
        case "SITE_CHECKIN_DISABLED": "Your company has switched off site check-ins, so this check-in was not accepted."
        case "CHECKIN_ID_CONFLICT": "This check-in could not be saved because its id is already used. Check in again."
        case "STAFF_NOT_LINKED": "Your account is not linked to a staff record, so check-ins cannot be saved. Ask the office."
        case "CHECKIN_IN_FUTURE":
            "The phone's clock is ahead, so this check-in was not accepted. Correct the phone's time and check in again."
        case "JOB_SITE_NOT_FOUND": "The site of this check-in no longer exists. Check in again."
        default: nil
        }
    }
}

/// A slot's state as the phone shows it: the server's status recomputed from the saved slots and this phone's
/// check-ins (SAVED = covered by a check-in on this phone the server has not confirmed yet).
public enum SlotState: String, Sendable, Equatable {
    case made, missed, due, upcoming, saved
}

/// One of today's slots as shown: time, window caption and state.
public struct SlotRow: Sendable, Equatable {
    public let scheduledAt: Date
    public let time: String
    public let window: String
    public let state: SlotState
}

/// How a check-in row's caption is shown.
public enum CheckinTone: Sendable, Equatable {
    case plain, info, warning, bad
}

/// One "My check-ins" row: date-time, site, caption and its tone.
public struct CheckinRow: Sendable, Equatable, Identifiable {
    public let id: UUID
    public let label: String
    public let value: String
    public let caption: String?
    public let tone: CheckinTone
}

/// The check-in screens' logic (same as Android `SiteCheckinPresentation`).
public enum SiteCheckinPresentation {
    typealias T = SiteCheckinTexts

    static func formatter(_ format: String, _ timeZone: TimeZone) -> DateFormatter {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = timeZone
        f.dateFormat = format
        return f
    }

    /// The schedule's time zone (the tenant's), else the phone's.
    public static func timeZone(_ schedule: MySiteCheckinsDTO?) -> TimeZone {
        schedule.flatMap { TimeZone(identifier: $0.timezone) } ?? .current
    }

    /// "14:05" in `timeZone`.
    public static func time(_ date: Date, timeZone: TimeZone) -> String { formatter("HH:mm", timeZone).string(from: date) }

    /// "26 Oct 2026, 14:05" in `timeZone`.
    public static func dateTime(_ date: Date, timeZone: TimeZone) -> String {
        formatter("d MMM yyyy, HH:mm", timeZone).string(from: date)
    }

    /// The slot's state now: MADE when the server says so or a check-in the server has (its list, or this phone's
    /// acknowledged ones) falls in its window (scheduled ± window); SAVED when a check-in only on this phone (not
    /// refused) does; else MISSED once the window has ended, DUE while it is open, UPCOMING before.
    public static func state(_ slot: CheckinSlotDTO, items: [CheckinItem], now: Date) -> SlotState {
        let window = TimeInterval(max(0, slot.windowMinutes) * 60)
        let start = slot.scheduledAt.addingTimeInterval(-window), end = slot.scheduledAt.addingTimeInterval(window)
        let inside = items.filter { $0.capturedAt >= start && $0.capturedAt <= end }
        if slot.status == .made || inside.contains(where: { $0.syncStatus == nil }) { return .made }
        if inside.contains(where: { !$0.refused }) { return .saved }
        if now >= end { return .missed }
        if now >= start { return .due }
        return .upcoming
    }

    /// Today's slots (in the schedule's time zone), in time order.
    public static func today(_ schedule: MySiteCheckinsDTO?, items: [CheckinItem], now: Date) -> [SlotRow] {
        guard let schedule else { return [] }
        let zone = timeZone(schedule)
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = zone
        return schedule.slots.filter { calendar.isDate($0.scheduledAt, inSameDayAs: now) }
            .sorted { $0.scheduledAt < $1.scheduledAt }
            .map { slot in
                let window = TimeInterval(slot.windowMinutes * 60)
                return SlotRow(scheduledAt: slot.scheduledAt, time: time(slot.scheduledAt, timeZone: zone),
                               window: T.window(from: time(slot.scheduledAt.addingTimeInterval(-window), timeZone: zone),
                                                to: time(slot.scheduledAt.addingTimeInterval(window), timeZone: zone)),
                               state: state(slot, items: items, now: now))
            }
    }

    /// The Jobs tab row's subtitle: the due slot (until its window ends), else the next one today, else none left.
    public static func jobsSubtitle(_ schedule: MySiteCheckinsDTO?, items: [CheckinItem], now: Date) -> String {
        guard let schedule else { return T.never }
        let zone = timeZone(schedule)
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = zone
        let slots = schedule.slots.filter { calendar.isDate($0.scheduledAt, inSameDayAs: now) }.sorted { $0.scheduledAt < $1.scheduledAt }
        if let due = slots.first(where: { state($0, items: items, now: now) == .due }) {
            return T.due(until: time(due.scheduledAt.addingTimeInterval(TimeInterval(due.windowMinutes * 60)), timeZone: zone))
        }
        if let next = slots.first(where: { state($0, items: items, now: now) == .upcoming }) {
            return T.next(at: time(next.scheduledAt, timeZone: zone))
        }
        return T.noneLeft
    }

    /// "My check-ins" rows, newest first: the server's check-ins (site, distance or no location; further than allowed
    /// in warning) and this phone's not on the server list yet (waiting, or not accepted with the reason). This phone's
    /// acknowledged ones appear once the list is read again (as Android).
    public static func rows(_ items: [CheckinItem], timeZone: TimeZone) -> [CheckinRow] {
        items.compactMap { item in
            let label = dateTime(item.capturedAt, timeZone: timeZone)
            if item.onServerList {
                let caption: String? = if item.gpsStatus != GpsStatus.fix.rawValue {
                    T.noLocation
                } else {
                    item.distanceM.map { T.distance(Int($0.rounded())) + (item.withinDistance == false ? " · " + T.outside : "") }
                }
                return CheckinRow(id: item.id, label: label, value: item.jobSiteName ?? T.noSite, caption: caption,
                                  tone: item.withinDistance == false ? .warning : .plain)
            }
            guard item.syncStatus != nil else { return nil }
            if item.refused {
                return CheckinRow(id: item.id, label: label, value: "",
                                  caption: [T.notAccepted, T.conflict(item.errorCode)].compactMap { $0 }.joined(separator: " · "),
                                  tone: .bad)
            }
            return CheckinRow(id: item.id, label: label, value: "", caption: T.waiting, tone: .info)
        }
    }

    /// The footer: why and how, the distance rule when set, and the saved-copy note when shown offline.
    public static func footer(_ schedule: MySiteCheckinsDTO?, savedAt: Date?, timeZone: TimeZone) -> String {
        var parts = [T.footer]
        if let metres = schedule?.maxDistanceM { parts.append(T.distanceFooter(metres)) }
        if let savedAt { parts.append(T.savedAt(dateTime(savedAt, timeZone: timeZone))) }
        return parts.joined(separator: " ")
    }
}
