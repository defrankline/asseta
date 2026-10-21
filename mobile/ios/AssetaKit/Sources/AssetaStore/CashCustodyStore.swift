import Foundation

/// The supervisor's custody balance in one currency, as the server sent it (raw JSON).
public struct StoredCustodyBalance: Equatable, Sendable {
    public let staffMemberID: UUID
    public let currency: String
    public let json: String
    public let asOf: Date

    public init(staffMemberID: UUID, currency: String, json: String, asOf: Date) {
        self.staffMemberID = staffMemberID
        self.currency = currency
        self.json = json
        self.asOf = asOf
    }
}

extension SyncStateStore {
    /// Replaces the tenant's custody balances with a complete server list. A list older than the
    /// stored one (a late or replayed page) is ignored. Returns whether it was applied.
    @discardableResult
    public func replaceCustody(_ balances: [StoredCustodyBalance], asOf: Date, tenantID: UUID) throws -> Bool {
        try db.transaction {
            let newest = try db.query("SELECT max(as_of) FROM cash_custody_balance WHERE tenant_id = ?",
                                      [.text(tenantID.lowercased)]) { $0.isNull(0) ? nil : $0.int(0) }.first ?? nil
            if let newest, newest > asOf.millisecondsSince1970 { return false }
            try db.execute("DELETE FROM cash_custody_balance WHERE tenant_id = ?", [.text(tenantID.lowercased)])
            for balance in balances {
                try db.execute(
                    """
                    INSERT INTO cash_custody_balance (tenant_id, staff_member_id, currency, json, as_of)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    [.text(tenantID.lowercased), .text(balance.staffMemberID.lowercased), .text(balance.currency),
                     .text(balance.json), .integer(balance.asOf.millisecondsSince1970)]
                )
            }
            return true
        }
    }

    public func custody(tenantID: UUID) throws -> [StoredCustodyBalance] {
        try db.query(
            """
            SELECT staff_member_id, currency, json, as_of FROM cash_custody_balance
            WHERE tenant_id = ? ORDER BY currency
            """,
            [.text(tenantID.lowercased)]
        ) { row in
            guard let staff = row.string(0).flatMap(UUID.init(uuidString:)) else {
                throw DatabaseError.step(code: -1, message: "Corrupt cash_custody_balance row")
            }
            return StoredCustodyBalance(staffMemberID: staff, currency: row.string(1) ?? "", json: row.string(2) ?? "{}",
                                        asOf: Date(millisecondsSince1970: row.int(3)))
        }
    }
}
