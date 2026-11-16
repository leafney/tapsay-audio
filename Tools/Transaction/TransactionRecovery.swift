// SPDX-License-Identifier: GPL-3.0-only
import Darwin
import Foundation

enum PendingTransactionAction: String {
    case none
    case cleanedCommitted
    case cleanedRolledBack
    case recoveredRollback
    case blocked
}

struct PendingTransactionResult {
    let action: PendingTransactionAction
    let messages: [String]
}

enum TransactionRecovery {
    static let fm = FileManager.default

    static func processPending(transactionRoot: URL, target: URL, state: URL,
                               validateDriver: (URL) throws -> Void,
                               injectCleanupFailure: Bool = false) throws -> PendingTransactionResult {
        var messages: [String] = []
        var action = PendingTransactionAction.none
        var handledPaths = Set<String>()
        let entries = try directoryEntries(transactionRoot)
        for entry in entries where entry.hasDirectoryPath || isDirectory(entry) {
            let name = entry.lastPathComponent
            guard UUID(uuidString: name)?.uuidString == name else {
                throw Failure("事务目录名不是标准 UUID，停止自动处理：\(entry.path)")
            }
            let recordURL = entry.appendingPathComponent(TransactionRecord.fileName)
            if !fm.fileExists(atPath: recordURL.path) {
                if isLegacyHistory(entry) {
                    messages.append("保留旧版历史材料，等待卸载清理：\(entry.path)")
                    continue
                }
                throw Failure("事务目录缺少事务记录，停止自动处理：\(entry.path)")
            }
            let record = try TransactionRecord.read(from: entry)
            try validateLocation(record: record, directory: entry, target: target, state: state)
            handledPaths.insert(record.previous)
            handledPaths.insert(record.staged)

            switch (record.phase, record.terminal) {
            case (.committed, .success), (.committed, .cleanupPending):
                try cleanupCommitted(record: record, directory: entry,
                                     injectFailure: injectCleanupFailure)
                messages.append("已清理已提交事务的临时材料：\(record.transactionID)")
                action = .cleanedCommitted
            case (.rolledBack, .rolledBack), (.rolledBack, .cleanupPending):
                try cleanupRolledBack(record: record, directory: entry,
                                      injectFailure: injectCleanupFailure)
                messages.append("已清理已回滚事务的临时材料：\(record.transactionID)")
                action = .cleanedRolledBack
            case (.recoveryRequired, _):
                throw Failure("发现待人工恢复事务，停止新安装：\(entry.path)；恢复材料：\(record.previous)")
            case (_, .recoveryRequired):
                throw Failure("发现待人工恢复事务，停止新安装：\(entry.path)；恢复材料：\(record.previous)")
            case (.prepared, .active), (.replacing, .active), (.validating, .active):
                do {
                    try recoverActive(record: record, directory: entry, target: target,
                                      state: state, validateDriver: validateDriver)
                } catch {
                    try markRecoveryRequired(record: record, directory: entry, error: error)
                    throw Failure("异常事务自动恢复失败，请保留固定材料：\(entry.path)；\(error)")
                }
                messages.append("已恢复异常中断的安装事务：\(record.transactionID)")
                action = .recoveredRollback
            default:
                throw Failure("事务阶段与终态无法唯一解释，停止自动处理：\(entry.path)")
            }
        }

        let halEntries = try directoryEntries(target.deletingLastPathComponent())
        for entry in halEntries where entry.lastPathComponent.hasPrefix(".TapSayAudio-") {
            guard handledPaths.contains(entry.path) else {
                throw Failure("发现没有事务记录归属的临时对象，停止自动处理：\(entry.path)")
            }
        }
        return PendingTransactionResult(action: action, messages: messages)
    }

    static func cleanupCommitted(record: TransactionRecord, directory: URL,
                                 injectFailure: Bool) throws {
        try cleanupTerminal(record: record, directory: directory,
                            terminal: .success, result: .deployed,
                            injectFailure: injectFailure)
    }

    static func cleanupRolledBack(record: TransactionRecord, directory: URL,
                                  injectFailure: Bool) throws {
        try cleanupTerminal(record: record, directory: directory,
                            terminal: .rolledBack, result: .rolledBack,
                            injectFailure: injectFailure)
    }

    static func recoverAfterInstallFailure(record: TransactionRecord, directory: URL,
                                           target: URL, state: URL,
                                           validateDriver: (URL) throws -> Void,
                                           forceFailure: Bool,
                                           injectCleanupFailure: Bool) throws {
        if forceFailure {
            let failed = try record.updating(phase: .recoveryRequired,
                                             terminal: .recoveryRequired,
                                             terminalResult: TransactionTerminalResult.none,
                                             cleanup: TransactionCleanup.none,
                                             cleanupRemainingPaths: [],
                                             cleanupReason: "注入恢复失败")
            try failed.write(to: directory)
            throw Failure("安装失败且恢复未完成；恢复材料保留于：\(record.previous)")
        }
        do {
            try restoreOriginal(record: record, target: target, state: state,
                                validateDriver: validateDriver)
        } catch {
            try markRecoveryRequired(record: record, directory: directory, error: error)
            throw Failure("安装失败且恢复未完成；恢复材料保留于：\(record.previous)；\(error)")
        }
        let rolledBack = try record.updating(phase: .rolledBack, terminal: .rolledBack,
                                             terminalResult: .rolledBack,
                                             cleanup: .pending,
                                             cleanupRemainingPaths: [],
                                             cleanupReason: "")
        try rolledBack.write(to: directory)
        do {
            try cleanupRolledBack(record: rolledBack, directory: directory,
                                  injectFailure: injectCleanupFailure)
        } catch {
            try recordCleanupFailure(record: rolledBack, directory: directory, error: error)
            throw Failure("安装失败，原版本已恢复，但临时材料清理未完成：\(error)")
        }
    }

    static func cleanPrepared(record: TransactionRecord, directory: URL,
                              injectCleanupFailure: Bool) throws {
        do {
            if injectCleanupFailure { throw Failure("注入回滚清理失败") }
            try removeOwned(record.staged)
            if !record.previousState.isEmpty { try removeOwned(record.previousState) }
            try requireOnlyTransactionRecord(directory)
            let complete = try record.updating(phase: .rolledBack, terminal: .rolledBack,
                                               terminalResult: .rolledBack, cleanup: .complete,
                                               cleanupRemainingPaths: [], cleanupReason: "")
            try complete.write(to: directory)
            try validateRecordAfterWrite(record: complete, directory: directory)
            try removeOwned(directory.appendingPathComponent(TransactionRecord.fileName).path)
            try removeDirectory(directory)
        } catch {
            let pending = try record.updating(phase: .rolledBack, terminal: .cleanupPending,
                                              terminalResult: .rolledBack, cleanup: .partial,
                                              cleanupRemainingPaths: remaining(record: record,
                                                                                directory: directory),
                                              cleanupReason: "清理失败：\(error)")
            try pending.write(to: directory)
            throw Failure("安装未修改原驱动，但临时材料清理未完成：\(error)")
        }
    }

    static func recordCleanupFailure(record: TransactionRecord, directory: URL,
                                     error: Error) throws {
        let pending = try record.updating(terminal: .cleanupPending, cleanup: .partial,
                                          cleanupRemainingPaths: remaining(record: record,
                                                                            directory: directory),
                                          cleanupReason: "清理失败：\(error)")
        try pending.write(to: directory)
    }

    static func validateRecordAfterWrite(record: TransactionRecord, directory: URL) throws {
        let reread = try TransactionRecord.read(from: directory)
        try require(reread.transactionID == record.transactionID
                    && reread.phase == record.phase
                    && reread.terminal == record.terminal
                    && reread.terminalResult == record.terminalResult
                    && reread.cleanup == record.cleanup,
                    "事务记录写入后回读不一致")
    }

    private static func cleanupTerminal(record: TransactionRecord, directory: URL,
                                        terminal: TransactionTerminal,
                                        result: TransactionTerminalResult,
                                        injectFailure: Bool) throws {
        do {
            if injectFailure { throw Failure("注入清理失败") }
            if !record.previous.isEmpty { try removeOwned(record.previous) }
            try removeOwned(record.staged)
            if !record.previousState.isEmpty { try removeOwned(record.previousState) }
            try requireOnlyTransactionRecord(directory)
            if terminal == .success {
                // A committed install remains deployed even if metadata cleanup fails.
                try validateCommittedTarget(record: record)
            }
            let complete = try record.updating(terminal: terminal, terminalResult: result,
                                               cleanup: .complete, cleanupRemainingPaths: [],
                                               cleanupReason: "")
            try complete.write(to: directory)
            try validateRecordAfterWrite(record: complete, directory: directory)
            try removeOwned(directory.appendingPathComponent(TransactionRecord.fileName).path)
            try removeDirectory(directory)
        } catch {
            if fm.fileExists(atPath: directory.path) {
                try recordCleanupFailure(record: record, directory: directory, error: error)
            }
            throw error
        }
    }

    private static func recoverActive(record: TransactionRecord, directory: URL,
                                      target: URL, state: URL,
                                      validateDriver: (URL) throws -> Void) throws {
        try restoreOriginal(record: record, target: target, state: state,
                            validateDriver: validateDriver)
        let rolledBack = try record.updating(phase: .rolledBack, terminal: .rolledBack,
                                             terminalResult: .rolledBack,
                                             cleanup: .pending,
                                             cleanupRemainingPaths: [],
                                             cleanupReason: "")
        try rolledBack.write(to: directory)
        try validateRecordAfterWrite(record: rolledBack, directory: directory)
        try cleanupRolledBack(record: rolledBack, directory: directory, injectFailure: false)
    }

    private static func restoreOriginal(record: TransactionRecord, target: URL, state: URL,
                                        validateDriver: (URL) throws -> Void) throws {
        let previous = record.previous.isEmpty ? nil : URL(fileURLWithPath: record.previous)
        let hadPrevious = previous.map { fm.fileExists(atPath: $0.path) } ?? false
        let hasTarget = fm.fileExists(atPath: target.path)

        if record.phase == .prepared {
            // No original driver or state move is permitted before replacing.
            return
        }

        if record.hadTarget {
            guard hadPrevious else {
                if record.phase == .replacing && hasTarget {
                    try validateDriver(target)
                    return
                }
                throw Failure("缺少安装前驱动，无法自动恢复；请保留事务记录：\(record.previous)")
            }
            if hasTarget {
                try validateDriver(target)
                try removeOwned(target.path)
            }
            try moveOwned(previous!.path, target.path)
            try validateDriver(target)
        } else if hasTarget {
            try validateDriver(target)
            try removeOwned(target.path)
        }

        if !record.previousState.isEmpty {
            let source = URL(fileURLWithPath: record.previousState)
            if !fm.fileExists(atPath: source.path) {
                if record.phase == .replacing && hasTarget {
                    // Old state copy may not have been written when replacement started.
                    return
                }
                throw Failure("缺少安装前状态副本，无法自动恢复：\(source.path)")
            }
            let data = try Data(contentsOf: source)
            try data.write(to: state, options: .atomic)
        } else if fm.fileExists(atPath: state.path) {
            try removeOwned(state.path)
        }
    }

    private static func validateLocation(record: TransactionRecord, directory: URL,
                                         target: URL, state: URL) throws {
        try require(directory.lastPathComponent == record.transactionID,
                    "事务目录 UUID 与记录不一致")
        try require(URL(fileURLWithPath: record.target).standardizedFileURL == target.standardizedFileURL,
                    "事务驱动目标与当前产品路径不一致")
        try require(URL(fileURLWithPath: record.state).standardizedFileURL == state.standardizedFileURL,
                    "事务状态目标与当前产品路径不一致")
        let transactionRoot = URL(fileURLWithPath: record.state).deletingLastPathComponent()
            .appendingPathComponent("transactions")
        try require(directory.deletingLastPathComponent().standardizedFileURL
                    == transactionRoot.standardizedFileURL,
                    "事务目录越界")
        let transactionDirectory = URL(fileURLWithPath: record.target).deletingLastPathComponent()
        try require(URL(fileURLWithPath: record.staged).deletingLastPathComponent()
            .standardizedFileURL == transactionDirectory.standardizedFileURL,
                    "事务暂存路径越界")
        if !record.previous.isEmpty {
            try require(URL(fileURLWithPath: record.previous).deletingLastPathComponent()
                .standardizedFileURL == transactionDirectory.standardizedFileURL,
                        "事务旧驱动路径越界")
        }
        if !record.previousState.isEmpty {
            try require(URL(fileURLWithPath: record.previousState).deletingLastPathComponent()
                .standardizedFileURL == directory.standardizedFileURL,
                        "事务旧状态路径越界")
        }
    }

    private static func isLegacyHistory(_ directory: URL) -> Bool {
        guard let entries = try? directoryEntries(directory) else { return false }
        let names = Set(entries.map(\.lastPathComponent))
        return !names.isEmpty && names.isSubset(of: ["backup.driver", "previous-state.json"])
    }

    private static func directoryEntries(_ directory: URL) throws -> [URL] {
        guard fm.fileExists(atPath: directory.path) else { return [] }
        return try fm.contentsOfDirectory(
            at: directory,
            includingPropertiesForKeys: [.isDirectoryKey, .isSymbolicLinkKey],
            options: []
        )
    }

    private static func isDirectory(_ url: URL) -> Bool {
        (try? url.resourceValues(forKeys: [.isDirectoryKey]).isDirectory) == true
    }

    private static func removeOwned(_ path: String) throws {
        guard !path.isEmpty else { return }
        let url = URL(fileURLWithPath: path)
        guard fm.fileExists(atPath: path) else { return }
        if (try? url.resourceValues(forKeys: [.isSymbolicLinkKey]).isSymbolicLink) == true {
            throw Failure("拒绝删除符号链接：\(path)")
        }
        try fm.removeItem(at: url)
    }

    private static func removeDirectory(_ directory: URL) throws {
        guard fm.fileExists(atPath: directory.path) else { return }
        try fm.removeItem(at: directory)
    }

    private static func moveOwned(_ from: String, _ to: String) throws {
        guard rename(from, to) == 0 else {
            throw Failure("恢复移动失败：\(from) → \(to)，\(String(cString: strerror(errno)))")
        }
    }

    private static func remaining(record: TransactionRecord, directory: URL) -> [String] {
        var paths = [record.previous, record.staged, record.previousState]
        paths.append(contentsOf: (try? directoryEntries(directory))?.map(\.path) ?? [])
        paths.removeAll { $0.isEmpty || !fm.fileExists(atPath: $0) }
        return paths
    }

    private static func requireOnlyTransactionRecord(_ directory: URL) throws {
        let names = try directoryEntries(directory).map(\.lastPathComponent)
        let unexpected = names.filter { $0 != TransactionRecord.fileName }
        try require(unexpected.isEmpty,
                    "事务目录仍有未知或未清理对象：\(unexpected.joined(separator: "、"))")
    }

    private static func markRecoveryRequired(record: TransactionRecord, directory: URL,
                                             error: Error) throws {
        let failed = try record.updating(phase: .recoveryRequired,
                                         terminal: .recoveryRequired,
                                         terminalResult: TransactionTerminalResult.none,
                                         cleanup: TransactionCleanup.none,
                                         cleanupRemainingPaths: [],
                                         cleanupReason: "恢复失败：\(error)")
        try failed.write(to: directory)
    }

    private static func validateCommittedTarget(record: TransactionRecord) throws {
        let target = URL(fileURLWithPath: record.target)
        try require(fm.fileExists(atPath: target.path),
                    "已提交事务的正式驱动不存在，不能继续清理记录")
        let info = try PropertyListSerialization.propertyList(
            from: Data(contentsOf: target.appendingPathComponent("Contents/Info.plist")),
            format: nil
        ) as? [String: Any] ?? [:]
        try require(info["CFBundleIdentifier"] as? String == record.bundleIdentifier,
                    "已提交事务的正式驱动身份不匹配")
    }
}
