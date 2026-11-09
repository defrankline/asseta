import AssetaModel
import Foundation

/// One figure row of a management group (or employee / lookup list): label, value, optional caption and where it opens.
public struct ManagementRow: Hashable, Sendable, Identifiable {
    public let id: String
    public let label: String
    public let value: String
    public var caption: String? = nil
    public var target: FigureTarget? = nil
}

/// A block of rows under an optional heading.
public struct ManagementBlock: Hashable, Sendable, Identifiable {
    public var id: String { heading ?? "main" }
    public var heading: String? = nil
    public let rows: [ManagementRow]
    public var footer: String? = nil
}

public struct ManagementGroup: Hashable, Sendable, Identifiable {
    public let id: String
    public let title: String
    public let blocks: [ManagementBlock]
}

/// The four guideline groups of the Accountability dashboard (strings doc "DEC-032 Phase 4 — management view").
public enum ManagementDashboard {
    typealias T = ManagementTexts

    public static func hours(_ f: HoursFigureDTO) -> String { OwnerFormat.hours(f.hours) }

    public static func money(_ lines: [MoneyLineDTO]) -> String {
        lines.isEmpty ? T.none : lines.map { OwnerFormat.money($0.amount, currency: $0.currency) }.joined(separator: ", ")
    }

    static func moneyCaption(_ lines: [MoneyLineDTO]) -> String? { lines.isEmpty ? nil : money(lines) }

    static func row(_ id: String, _ label: String, hours figure: HoursFigureDTO, features: OwnerFeatures) -> ManagementRow {
        ManagementRow(id: id, label: label, value: hours(figure), target: ManagementRoutes.target(figure.route, features: features))
    }

    static func row(_ id: String, _ label: String, money figure: MoneyFigureDTO, features: OwnerFeatures) -> ManagementRow {
        ManagementRow(id: id, label: label, value: money(figure.lines), target: ManagementRoutes.target(figure.route, features: features))
    }

    static func row(_ id: String, _ label: String, count figure: CountFigureDTO, features: OwnerFeatures) -> ManagementRow {
        ManagementRow(id: id, label: label, value: "\(figure.count)", target: ManagementRoutes.target(figure.route, features: features))
    }

    static func row(_ id: String, _ label: String, queue q: PurchaseQueueDTO, features: OwnerFeatures) -> ManagementRow {
        ManagementRow(id: id, label: label, value: "\(q.count) · \(OwnerFormat.hours(q.hours))", caption: moneyCaption(q.amounts),
                      target: ManagementRoutes.target(q.route, features: features))
    }

    static func nonZero(_ value: DecimalString?, _ currency: String) -> String? {
        guard let value, value.value != 0 else { return nil }
        return OwnerFormat.money(value, currency: currency)
    }

    public static func groups(_ s: AccountabilitySummaryDTO, features: OwnerFeatures, timeZone: TimeZone = .current) -> [ManagementGroup] {
        [s.hoursSection.map { hoursGroup($0, features) }, s.operationsSection.map { operationsGroup($0, features) },
         s.cashSection.map { cashGroup($0, features) }, s.exceptionsSection.map { exceptionsGroup($0, features, timeZone: timeZone) }]
            .compactMap { $0 }
    }

    static func hoursGroup(_ h: CustomerHoursSectionDTO, _ f: OwnerFeatures) -> ManagementGroup {
        let customers = h.remainingByCustomer.map { c in
            ManagementRow(id: "customer.\(c.customerID)", label: c.customerName ?? "—", value: OwnerFormat.hours(c.remaining),
                          target: ManagementRoutes.target(c.route, features: f))
        }
        var blocks = [ManagementBlock(rows: [
            row("purchased", T.hoursPurchased, hours: h.purchased, features: f),
            row("purchasedValue", T.hoursPurchasedValue, money: h.purchasedValue, features: f),
            row("activated", T.hoursActivated, hours: h.activated, features: f),
            row("consumed", T.hoursConsumed, hours: h.consumed, features: f),
            row("remaining", T.hoursRemaining, hours: h.remaining, features: f),
            row("unpaid", T.hoursUnpaid, queue: h.unpaidPurchases, features: f),
            row("unconfirmed", T.hoursUnconfirmed, queue: h.unconfirmedPurchases, features: f),
            row("awaiting", T.hoursAwaiting, queue: h.awaitingActivation, features: f),
        ])]
        if !customers.isEmpty {
            let shown = customers.count < h.remainingCustomersTotal ? T.hoursCustomersShown(customers.count, h.remainingCustomersTotal) : nil
            blocks.append(ManagementBlock(heading: T.hoursByCustomer, rows: customers, footer: shown))
        }
        return ManagementGroup(id: "hours_section", title: T.hoursTitle, blocks: blocks)
    }

    static func operationsGroup(_ o: ExcavatorOperationsSectionDTO, _ f: OwnerFeatures) -> ManagementGroup {
        var main = [
            row("operating", T.opsOperating, hours: o.operatingHours, features: f),
            row("customer", T.opsCustomer, hours: o.customerHours, features: f),
            row("authorized", T.opsAuthorized, hours: o.authorizedNonCustomerHours, features: f),
            row("unexplained", T.opsUnexplained, hours: o.unexplainedHours, features: f),
            ManagementRow(id: "discrepancies", label: T.opsDiscrepancies, value: "\(o.meterDiscrepancies.count)",
                          target: ManagementRoutes.target(o.meterDiscrepancies.route, features: f)),
        ]
        main += o.meterDiscrepancies.byType.map {
            ManagementRow(id: "discrepancy.\($0.type)", label: T.opsDiscrepancy($0.type), value: "\($0.count)",
                          target: ManagementRoutes.target($0.route, features: f))
        }
        main += [row("pendingReports", T.opsPendingReports, count: o.pendingReports, features: f),
                 row("returnedReports", T.opsReturnedReports, count: o.returnedReports, features: f)]
        var blocks = [ManagementBlock(rows: main)]
        if !o.byExcavator.isEmpty {
            blocks.append(ManagementBlock(heading: T.opsByExcavator, rows: o.byExcavator.map { e in
                let name = [e.machineCode, e.machineName].compactMap { $0 }.joined(separator: " · ")
                return ManagementRow(id: "excavator.\(e.machineID)", label: name.isEmpty ? "—" : name, value: OwnerFormat.hours(e.operatingHours),
                                     caption: T.opsExcavatorRow(customer: OwnerFormat.hoursNumber(e.customerHours),
                                                                authorized: OwnerFormat.hoursNumber(e.authorizedHours),
                                                                unexplained: OwnerFormat.hoursNumber(e.unexplainedHours)),
                                     target: ManagementRoutes.excavatorTarget(machineID: e.machineID, route: e.route, features: f))
            }))
        }
        return ManagementGroup(id: "operations_section", title: T.opsTitle, blocks: blocks)
    }

    static func cashGroup(_ c: CashSectionDTO, _ f: OwnerFeatures) -> ManagementGroup {
        var blocks = [ManagementBlock(rows: [
            row("collected", T.cashCollected, money: c.collected, features: f),
            row("transferred", T.cashTransferred, money: c.transferred, features: f),
            row("inTransit", T.cashInTransit, money: c.inTransit, features: f),
            row("declared", T.cashDeclared, money: c.declaredForRemittance, features: f),
            row("confirmed", T.cashConfirmed, money: c.confirmedByCompany, features: f),
            row("outstanding", T.cashOutstanding, money: c.outstanding, features: f),
            row("unconfirmed", T.cashUnconfirmed, money: c.unconfirmedRemittances, features: f),
            row("disputedRemittances", T.cashDisputedRemittances, money: c.disputedRemittances, features: f),
            row("disputedTransfers", T.cashDisputedTransfers, money: c.disputedTransfers, features: f),
        ])]
        if !c.heldByEmployee.isEmpty {
            blocks.append(ManagementBlock(heading: T.cashHeld, rows: c.heldByEmployee.map { e in
                ManagementRow(id: "held.\(e.staffMemberID).\(e.currency)", label: e.staffMemberName ?? "—",
                              value: OwnerFormat.money(e.outstanding, currency: e.currency),
                              caption: T.heldCaption(transit: nonZero(e.inTransitOut, e.currency), claimed: nonZero(e.claimedUnverifiedHandovers, e.currency),
                                                     float: nonZero(e.pendingFloats, e.currency), retained: nonZero(e.approvedRetention, e.currency)),
                              target: ManagementRoutes.target(e.route, features: f))
            }))
        }
        return ManagementGroup(id: "cash_section", title: T.cashTitle, blocks: blocks)
    }

    static func exceptionsGroup(_ e: ExceptionsSectionDTO, _ f: OwnerFeatures, timeZone: TimeZone) -> ManagementGroup {
        let attempts = e.unauthorizedAttempts
        let changeover = e.changeoverJobsAwaitingApproval
        var main = [
            row("unexplained", T.excUnexplained, hours: e.unexplainedEngineHours, features: f),
            row("shortages", T.excShortages, money: e.shortages, features: f),
            row("overages", T.excOverages, money: e.overages, features: f),
            row("shortagesPeriod", T.excShortagesPeriod, money: e.shortagesOpenedInPeriod, features: f),
            row("overagesPeriod", T.excOveragesPeriod, money: e.overagesOpenedInPeriod, features: f),
            row("unconfirmedPayments", T.excUnconfirmedPayments, money: e.unconfirmedPayments, features: f),
            ManagementRow(id: "attempts", label: T.excAttempts, value: "\(attempts.permissionDenied + attempts.segregationOfDuties)",
                          caption: T.excAttemptsCaption(denied: attempts.permissionDenied, sod: attempts.segregationOfDuties),
                          target: ManagementRoutes.target(attempts.route, features: f)),
            row("missingReports", T.excMissingReports, count: e.overdueReports.missingDailyReports, features: f),
            row("overdueRemittances", T.excOverdueRemittances, count: e.overdueReports.remittancesOverdueToday, features: f),
            ManagementRow(id: "changeover", label: T.excChangeover, value: "\(changeover.count)",
                          caption: changeover.oldestDays.map(T.excChangeoverCaption)),
        ]
        main += changeover.items.map { job in
            ManagementRow(id: "changeover.\(job.jobID)",
                          label: T.excChangeoverRow(job: job.jobNumber ?? "—", machine: job.machineCode ?? job.machineName ?? "—", customer: job.customerName ?? "—"),
                          value: T.excChangeoverDays(job.daysWaiting), target: ManagementRoutes.target(job.route, features: f))
        }
        var blocks = [ManagementBlock(rows: main)]
        let kinds = { (items: [KindCountDTO]) in items.map { k in
            ManagementRow(id: "kind.\(k.kind)", label: T.kind(k.kind), value: "\(k.count)",
                          caption: k.oldestAt.map { T.oldest(OwnerFormat.stamp($0, timeZone: timeZone)) },
                          target: ManagementRoutes.target(k.route, features: f))
        } }
        if !e.outstandingApprovals.byKind.isEmpty {
            blocks.append(ManagementBlock(heading: T.excApprovals(e.outstandingApprovals.total), rows: kinds(e.outstandingApprovals.byKind)))
        }
        if !e.pendingAdjustments.byKind.isEmpty {
            blocks.append(ManagementBlock(heading: T.excPending(e.pendingAdjustments.total), rows: kinds(e.pendingAdjustments.byKind)))
        }
        if !e.unresolvedVariances.bySource.isEmpty {
            blocks.append(ManagementBlock(heading: T.excVariances(e.unresolvedVariances.total), rows: e.unresolvedVariances.bySource.map { v in
                ManagementRow(id: "variance.\(v.source)", label: T.excVariance(v.source), value: "\(v.count)",
                              caption: v.unit == "MONEY" ? moneyCaption(v.amounts) : nil, target: ManagementRoutes.target(v.route, features: f))
            }))
        }
        return ManagementGroup(id: "exceptions_section", title: T.excTitle, blocks: blocks)
    }
}

/// Employee accountability rows (strings doc): figures, cash held, then one list per non-empty group, DTO order.
public enum EmployeePresentation {
    typealias T = ManagementTexts

    public struct RecordList: Hashable, Sendable, Identifiable {
        public var id: String { title }
        public let title: String
        public let rows: [ManagementRow]
    }

    static func lists(_ d: EmployeeAccountabilityDTO) -> [(String, [EmployeeRecordDTO])] {
        var out: [(String, [EmployeeRecordDTO])] = [
            (T.employeeListCollections, d.collections), (T.employeeListFloats, d.floats), (T.employeeListTransfersIn, d.transfersIn),
            (T.employeeListTransfersOut, d.transfersOut), (T.employeeListRemittances, d.remittances), (T.employeeListSpending, d.spending),
            (T.employeeListRetentions, d.retentions), (T.employeeListDifferences, d.differences),
            (T.employeeListCustodyAdjustments, d.custodyAdjustments), (T.employeeListReports, d.reportsSubmitted),
            (T.employeeListApprovals, d.approvalsMade), (T.employeeListAdjustmentsRequested, d.adjustmentsRequested),
            (T.employeeListAdjustmentsDecided, d.adjustmentsDecided),
        ]
        if d.scorecardVisible { out.append((T.employeeListScorecard, d.scorecardItems)) }
        return out
    }

    /// "{count}" or "{count} · {money}" with money totals per currency (only rows with an amount in a currency).
    public static func figureRows(_ d: EmployeeAccountabilityDTO) -> [ManagementRow] {
        lists(d).map { title, records in
            var totals: [String: Decimal] = [:]
            for record in records {
                if let amount = record.amount?.value, let currency = record.currency, record.unit != "HOURS" { totals[currency, default: 0] += amount }
            }
            let money = totals.sorted { $0.key < $1.key }.map { OwnerFormat.money($0.value, currency: $0.key) }.joined(separator: ", ")
            return ManagementRow(id: title, label: title, value: money.isEmpty ? "\(records.count)" : T.employeeCountMoney(records.count, money))
        }
    }

    public static func cashHeld(_ d: EmployeeAccountabilityDTO) -> [ManagementRow] {
        d.cashHeld.map { c in
            let nz = ManagementDashboard.nonZero
            return ManagementRow(id: c.currency, label: c.currency, value: OwnerFormat.money(c.outstanding, currency: c.currency),
                                 caption: T.heldCaption(transit: nz(c.inTransitOut, c.currency), claimed: nz(c.claimedUnverifiedHandovers, c.currency),
                                                        float: nz(c.pendingFloats, c.currency), retained: nz(c.approvedRetention, c.currency)))
        }
    }

    public static func recordLists(_ d: EmployeeAccountabilityDTO, features: OwnerFeatures, timeZone: TimeZone = .current) -> [RecordList] {
        lists(d).compactMap { title, records in
            records.isEmpty ? nil : RecordList(title: title, rows: records.enumerated().map { index, r in
                let when = OwnerFormat.stamp(r.occurredAt, timeZone: timeZone)
                let status = r.status.map(OwnerFormat.humanize)
                let amount: String? = if let a = r.amount { r.unit == "HOURS" || r.currency == nil ? OwnerFormat.hours(a) : OwnerFormat.money(a, currency: r.currency!) } else { nil }
                let parts: [String?] = [r.label, r.counterpartyStaffName]
                return ManagementRow(id: "\(title).\(index)", label: r.reference ?? r.label ?? OwnerFormat.humanize(r.recordType), value: amount ?? "",
                                     caption: ([status.map { "\(when) · \($0)" } ?? when] + parts.compactMap { $0 }.filter { $0 != r.reference }).joined(separator: "\n"),
                                     target: ManagementRoutes.target(r.route, features: features))
            })
        }
    }
}

/// One Find a reference match (card).
public enum LookupPresentation {
    typealias T = ManagementTexts

    public struct Card: Hashable, Sendable, Identifiable {
        public let id: UUID
        public let title: String
        public let reference: String?
        public let status: String?
        public let rows: [ManagementRow]
        public let target: FigureTarget?
    }

    public static func card(_ m: LookupMatchDTO, features: OwnerFeatures, timeZone: TimeZone = .current) -> Card {
        func who(_ name: String?, _ at: Date?) -> String? {
            let when = at.map { OwnerFormat.stamp($0, timeZone: timeZone) }
            let joined = [name, when].compactMap { $0 }.joined(separator: " · ")
            return joined.isEmpty ? nil : joined
        }
        let balance: String? = m.balanceOutstanding.map { value in
            if m.balanceUnit == "HOURS" { return OwnerFormat.hours(value) }
            return m.currency.map { OwnerFormat.money(value, currency: $0) } ?? OwnerFormat.hoursNumber(value)
        }
        let amount = m.amount.flatMap { value in m.currency.map { OwnerFormat.money(value, currency: $0) } }
        let machine = [m.machineCode, m.machineName].compactMap { $0 }.joined(separator: " · ")
        let pairs: [(String, String?)] = [
            (T.lookupRecordedBy, who(m.recordedByName, m.recordedAt)), (T.lookupDecidedBy, who(m.decidedByName, m.decidedAt)),
            (T.lookupCustomer, m.customerName), (T.lookupMachine, machine.isEmpty ? nil : machine), (T.lookupStaff, m.staffMemberName),
            (T.lookupAmount, amount), (T.lookupBalance, balance), (T.lookupHoursRemaining, m.hoursRemaining.map { OwnerFormat.hours($0) }),
        ]
        let rows = pairs.compactMap { label, value in value.map { ManagementRow(id: label, label: label, value: $0) } }
        return Card(id: m.id, title: T.lookupType(m.recordType), reference: m.reference, status: m.status.map(OwnerFormat.humanize), rows: rows,
                    target: ManagementRoutes.target(m.route, features: features))
    }
}
