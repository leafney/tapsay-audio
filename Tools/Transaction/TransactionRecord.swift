// SPDX-License-Identifier: GPL-3.0-only
import Foundation

enum TransactionRecordError: Error, CustomStringConvertible {
    case invalid(String)

    var description: String {
        switch self {
        case .invalid(let message): return message
        }
    }
}

enum TransactionPhase: String, Codable {
    case prepared
    case replacing
    case validating
    case committed
    case rolledBack = "rolled_back"
    case recoveryRequired = "recovery_required"
}

enum TransactionTerminal: String, Codable {
    case active
    case success
    case rolledBack = "rolled_back"
    case recoveryRequired = "recovery_required"
    case cleanupPending = "cleanup_pending"
}

enum TransactionTerminalResult: String, Codable {
    case none
    case deployed
    case rolledBack = "rolled_back"
}

enum TransactionCleanup: String, Codable {
    case none
    case pending
    case partial
    case complete
}

struct TransactionRecord: Codable {
    static let fileName = "transaction.json"
    static let schemaVersion = 1

    let schemaVersion: Int
    let product: String
    let transactionID: String
    let deviceUID: String
    let bundleIdentifier: String
    let receipt: String
    let target: String
    let state: String
    let previous: String
    let staged: String
    let previousState: String
    let hadTarget: Bool
    let phase: TransactionPhase
    let terminal: TransactionTerminal
    let terminalResult: TransactionTerminalResult
    let cleanup: TransactionCleanup
    let cleanupRemainingPaths: [String]
    let cleanupReason: String
    let updatedAt: String

    enum CodingKeys: String, CodingKey {
        case schemaVersion = "schema_version"
        case product
        case transactionID = "transaction_id"
        case deviceUID = "device_uid"
        case bundleIdentifier = "bundle_identifier"
        case receipt
        case target
        case state
        case previous
        case staged
        case previousState = "previous_state"
        case hadTarget = "had_target"
        case phase
        case terminal
        case terminalResult = "terminal_result"
        case cleanup
        case cleanupRemainingPaths = "cleanup_remaining_paths"
        case cleanupReason = "cleanup_reason"
        case updatedAt = "updated_at"
    }

    init(transactionID: String, deviceUID: String, bundleIdentifier: String, receipt: String,
         target: String, state: String, previous: String, staged: String,
         previousState: String, hadTarget: Bool) {
        schemaVersion = Self.schemaVersion
        product = "TapSay Audio"
        self.transactionID = transactionID
        self.deviceUID = deviceUID
        self.bundleIdentifier = bundleIdentifier
        self.receipt = receipt
        self.target = target
        self.state = state
        self.previous = previous
        self.staged = staged
        self.previousState = previousState
        self.hadTarget = hadTarget
        phase = .prepared
        terminal = .active
        terminalResult = .none
        cleanup = .none
        cleanupRemainingPaths = []
        cleanupReason = ""
        updatedAt = Self.timestamp()
    }

    init(from decoder: Decoder) throws {
        let dynamic = try decoder.container(keyedBy: AnyCodingKey.self)
        let expected: Set<String> = [
            "schema_version", "product", "transaction_id", "device_uid",
            "bundle_identifier", "receipt", "target", "state", "previous", "staged",
            "previous_state", "had_target", "phase", "terminal", "terminal_result",
            "cleanup", "cleanup_remaining_paths", "cleanup_reason", "updated_at",
        ]
        let actual = Set(dynamic.allKeys.map(\.stringValue))
        guard actual == expected else {
            throw TransactionRecordError.invalid("事务记录字段缺失或包含未知字段")
        }
        let container = try decoder.container(keyedBy: CodingKeys.self)
        schemaVersion = try container.decode(Int.self, forKey: .schemaVersion)
        product = try container.decode(String.self, forKey: .product)
        transactionID = try container.decode(String.self, forKey: .transactionID)
        deviceUID = try container.decode(String.self, forKey: .deviceUID)
        bundleIdentifier = try container.decode(String.self, forKey: .bundleIdentifier)
        receipt = try container.decode(String.self, forKey: .receipt)
        target = try container.decode(String.self, forKey: .target)
        state = try container.decode(String.self, forKey: .state)
        previous = try container.decode(String.self, forKey: .previous)
        staged = try container.decode(String.self, forKey: .staged)
        previousState = try container.decode(String.self, forKey: .previousState)
        hadTarget = try container.decode(Bool.self, forKey: .hadTarget)
        phase = try container.decode(TransactionPhase.self, forKey: .phase)
        terminal = try container.decode(TransactionTerminal.self, forKey: .terminal)
        terminalResult = try container.decode(TransactionTerminalResult.self, forKey: .terminalResult)
        cleanup = try container.decode(TransactionCleanup.self, forKey: .cleanup)
        cleanupRemainingPaths = try container.decode([String].self, forKey: .cleanupRemainingPaths)
        cleanupReason = try container.decode(String.self, forKey: .cleanupReason)
        updatedAt = try container.decode(String.self, forKey: .updatedAt)
        try validate()
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(schemaVersion, forKey: .schemaVersion)
        try container.encode(product, forKey: .product)
        try container.encode(transactionID, forKey: .transactionID)
        try container.encode(deviceUID, forKey: .deviceUID)
        try container.encode(bundleIdentifier, forKey: .bundleIdentifier)
        try container.encode(receipt, forKey: .receipt)
        try container.encode(target, forKey: .target)
        try container.encode(state, forKey: .state)
        try container.encode(previous, forKey: .previous)
        try container.encode(staged, forKey: .staged)
        try container.encode(previousState, forKey: .previousState)
        try container.encode(hadTarget, forKey: .hadTarget)
        try container.encode(phase, forKey: .phase)
        try container.encode(terminal, forKey: .terminal)
        try container.encode(terminalResult, forKey: .terminalResult)
        try container.encode(cleanup, forKey: .cleanup)
        try container.encode(cleanupRemainingPaths, forKey: .cleanupRemainingPaths)
        try container.encode(cleanupReason, forKey: .cleanupReason)
        try container.encode(updatedAt, forKey: .updatedAt)
    }

    func updating(phase: TransactionPhase? = nil, terminal: TransactionTerminal? = nil,
                   terminalResult: TransactionTerminalResult? = nil,
                   cleanup: TransactionCleanup? = nil,
                   cleanupRemainingPaths: [String]? = nil,
                   cleanupReason: String? = nil) throws -> TransactionRecord {
        let updated = TransactionRecord(
            schemaVersion: schemaVersion, product: product, transactionID: transactionID,
            deviceUID: deviceUID, bundleIdentifier: bundleIdentifier, receipt: receipt,
            target: target, state: state, previous: previous, staged: staged,
            previousState: previousState, hadTarget: hadTarget,
            phase: phase ?? self.phase, terminal: terminal ?? self.terminal,
            terminalResult: terminalResult ?? self.terminalResult,
            cleanup: cleanup ?? self.cleanup,
            cleanupRemainingPaths: cleanupRemainingPaths ?? self.cleanupRemainingPaths,
            cleanupReason: cleanupReason ?? self.cleanupReason,
            updatedAt: Self.timestamp()
        )
        try updated.validate()
        return updated
    }

    func write(to directory: URL) throws {
        try validate()
        let data = try JSONEncoder.pretty.encode(self)
        try data.write(to: directory.appendingPathComponent(Self.fileName), options: .atomic)
    }

    static func read(from directory: URL) throws -> TransactionRecord {
        let data = try Data(contentsOf: directory.appendingPathComponent(fileName))
        return try JSONDecoder().decode(TransactionRecord.self, from: data)
    }

    func validate() throws {
        try check(schemaVersion == Self.schemaVersion, "事务记录版本不受支持")
        try check(product == "TapSay Audio", "事务记录产品身份不匹配")
        try check(UUID(uuidString: transactionID)?.uuidString == transactionID,
                   "事务记录 UUID 不是标准大写格式")
        try check(deviceUID == "com.leafney.tapsay.audio.device.2ch",
                  "事务记录设备 UID 不匹配")
        try check(bundleIdentifier == "com.leafney.tapsay.audio.driver",
                  "事务记录 Bundle ID 不匹配")
        try check(receipt == "com.leafney.tapsay.audio.pkg", "事务记录收据标识不匹配")
        try check(target.hasSuffix("/Library/Audio/Plug-Ins/HAL/TapSayAudio.driver"),
                  "事务记录驱动路径越界")
        try check(state.hasSuffix("/Library/Application Support/TapSay Audio/install-state.json"),
                  "事务记录状态路径越界")
        try check(staged == URL(fileURLWithPath: target).deletingLastPathComponent()
            .appendingPathComponent(".TapSayAudio-\(transactionID).driver").path,
                  "事务记录暂存路径与 UUID 不一致")
        if hadTarget {
            try check(previous == URL(fileURLWithPath: target).deletingLastPathComponent()
                .appendingPathComponent(".TapSayAudio-\(transactionID).previous").path,
                      "事务记录旧驱动路径与 UUID 不一致")
        } else {
            try check(previous.isEmpty && previousState.isEmpty,
                      "首装事务不得伪造旧驱动或旧状态路径")
        }
        if !previousState.isEmpty {
            try check(previousState == URL(fileURLWithPath: state).deletingLastPathComponent()
                .appendingPathComponent("transactions/\(transactionID)/previous-state.json").path,
                      "事务记录旧状态路径与 UUID 不一致")
        }
        try check(!updatedAt.isEmpty, "事务记录缺少更新时间")

        switch phase {
        case .prepared, .replacing, .validating:
            try check(terminal == .active && terminalResult == .none && cleanup == .none,
                      "活动事务的终态、结果或清理状态矛盾")
        case .committed:
            try check(terminalResult == .deployed, "已提交事务必须记录部署结果")
            try check([.success, .cleanupPending].contains(terminal),
                      "已提交事务终态矛盾")
        case .rolledBack:
            try check(terminalResult == .rolledBack, "已回滚事务必须记录回滚结果")
            try check([.rolledBack, .cleanupPending].contains(terminal),
                      "已回滚事务终态矛盾")
        case .recoveryRequired:
            try check(terminal == .recoveryRequired && terminalResult == .none,
                      "待恢复事务必须保留恢复状态")
        }

        switch terminal {
        case .active:
            try check([.prepared, .replacing, .validating].contains(phase) && cleanup == .none,
                      "活动终态与阶段或清理状态矛盾")
        case .success:
            try check(phase == .committed && [.pending, .partial, .complete].contains(cleanup),
                      "成功终态与阶段或清理状态矛盾")
        case .rolledBack:
            try check(phase == .rolledBack && [.pending, .partial, .complete].contains(cleanup),
                      "回滚终态与阶段或清理状态矛盾")
        case .cleanupPending:
            try check([.committed, .rolledBack].contains(phase)
                      && [.pending, .partial].contains(cleanup),
                      "待清理终态与阶段或清理状态矛盾")
        case .recoveryRequired:
            try check(phase == .recoveryRequired && cleanup == .none,
                      "恢复终态与阶段或清理状态矛盾")
        }

        if cleanup == .partial {
            try check(!cleanupRemainingPaths.isEmpty || !cleanupReason.isEmpty,
                      "部分清理必须记录剩余路径或原因")
        } else {
            try check(cleanupRemainingPaths.isEmpty,
                      "非部分清理状态不得携带残留路径")
        }
    }

    private func check(_ value: Bool, _ message: String) throws {
        if !value { throw TransactionRecordError.invalid(message) }
    }

    private static func timestamp() -> String {
        ISO8601DateFormatter().string(from: Date())
    }

    private init(schemaVersion: Int, product: String, transactionID: String,
                 deviceUID: String, bundleIdentifier: String, receipt: String,
                 target: String, state: String, previous: String, staged: String,
                 previousState: String, hadTarget: Bool, phase: TransactionPhase,
                 terminal: TransactionTerminal, terminalResult: TransactionTerminalResult,
                 cleanup: TransactionCleanup, cleanupRemainingPaths: [String],
                 cleanupReason: String, updatedAt: String) {
        self.schemaVersion = schemaVersion
        self.product = product
        self.transactionID = transactionID
        self.deviceUID = deviceUID
        self.bundleIdentifier = bundleIdentifier
        self.receipt = receipt
        self.target = target
        self.state = state
        self.previous = previous
        self.staged = staged
        self.previousState = previousState
        self.hadTarget = hadTarget
        self.phase = phase
        self.terminal = terminal
        self.terminalResult = terminalResult
        self.cleanup = cleanup
        self.cleanupRemainingPaths = cleanupRemainingPaths
        self.cleanupReason = cleanupReason
        self.updatedAt = updatedAt
    }
}

private struct AnyCodingKey: CodingKey {
    let stringValue: String
    let intValue: Int?

    init(stringValue: String) {
        self.stringValue = stringValue
        intValue = nil
    }

    init?(intValue: Int) {
        stringValue = String(intValue)
        self.intValue = intValue
    }
}

private extension JSONEncoder {
    static var pretty: JSONEncoder {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        return encoder
    }
}
