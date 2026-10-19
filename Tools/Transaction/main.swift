// TapSay Audio installation transaction. Copyright 2026 TapSay contributors.
// SPDX-License-Identifier: GPL-3.0-only
import Foundation
import Darwin

@_silgen_name("flock") func fileLock(_ fd: Int32, _ operation: Int32) -> Int32
struct Failure: Error, CustomStringConvertible {
    let description: String
    init(_ text: String) { description = text }
}
let fm = FileManager.default
func require(_ value: Bool, _ text: String) throws { if !value { throw Failure(text) } }
func exists(_ url: URL) -> Bool { fm.fileExists(atPath: url.path) }
func json(_ url: URL) throws -> [String: Any] {
    guard let result = try JSONSerialization.jsonObject(with: Data(contentsOf: url)) as? [String: Any] else {
        throw Failure("无法读取对象：\(url.path)")
    }
    return result
}
func writeJSON(_ value: [String: Any], _ url: URL) throws {
    try JSONSerialization.data(withJSONObject: value, options: [.prettyPrinted, .sortedKeys]).write(to: url, options: .atomic)
}
func rejectLinks(_ url: URL) throws {
    var path = url.standardizedFileURL
    while path.path != "/" {
        if path.path == "/var" || path.path == "/tmp" {
            path.deleteLastPathComponent()
            continue
        }
        if let attributes = try? fm.attributesOfItem(atPath: path.path) {
            try require(attributes[.type] as? FileAttributeType != .typeSymbolicLink, "拒绝符号链接：\(path.path)")
        }
        path.deleteLastPathComponent()
    }
}
func move(_ from: URL, _ to: URL) throws {
    guard rename(from.path, to.path) == 0 else { throw Failure("移动失败：\(from.path) → \(to.path)，\(String(cString: strerror(errno)))") }
}
func run(_ path: String, _ arguments: [String]) throws -> (Int32, String) {
    let process = Process(), pipe = Pipe()
    process.executableURL = URL(fileURLWithPath: path)
    process.arguments = arguments
    process.standardOutput = pipe; process.standardError = pipe
    try process.run()
    let output = pipe.fileHandleForReading.readDataToEndOfFile()
    process.waitUntilExit()
    return (process.terminationStatus, String(decoding: output, as: UTF8.self))
}
struct Transaction {
    let metadata: [String: Any]
    let driver: [String: Any]
    let product: [String: Any]
    let root: URL?
    let target: URL
    let state: URL
    let lock: URL
    var testing: Bool { root != nil }
    func field(_ key: String) -> String { driver[key] as! String }
    init(metadataURL: URL, testRoot: URL?) throws {
        metadata = try json(metadataURL)
        guard let d = metadata["driver"] as? [String: Any], let p = metadata["product"] as? [String: Any],
              d["bundle_identifier"] as? String == "com.leafney.tapsay.audio.driver",
              d["device_uid"] as? String == "com.leafney.tapsay.audio.device.2ch",
              d["device_name"] as? String == "TapSay Audio 2ch",
              d["executable_name"] as? String == "TapSayAudio",
              d["package_receipt_identifier"] as? String == "com.leafney.tapsay.audio.pkg",
              d["plugin_factory_uuid"] as? String == "CC1226D1-A123-47B7-B113-5228AB089AA8",
              p["version"] is String, p["build_number"] is String else { throw Failure("产品元数据身份不匹配") }
        driver = d; product = p; root = testRoot
        if let testRoot {
            try rejectLinks(testRoot)
            let temporary = URL(fileURLWithPath: NSTemporaryDirectory()).resolvingSymlinksInPath().path + "/"
            try require(testRoot.path.hasPrefix(temporary) || testRoot.path.hasPrefix("/private/tmp/"), "测试仅允许专用临时目录")
        } else {
            try require(geteuid() == 0, "需要系统管理员授权")
            try require(ProcessInfo.processInfo.operatingSystemVersion.majorVersion >= 14, "最低支持 macOS 14")
        }
        target = (testRoot ?? URL(fileURLWithPath: "/")).appendingPathComponent("Library/Audio/Plug-Ins/HAL/TapSayAudio.driver")
        state = (testRoot ?? URL(fileURLWithPath: "/")).appendingPathComponent("Library/Application Support/TapSay Audio/install-state.json")
        lock = state.deletingLastPathComponent().deletingLastPathComponent().appendingPathComponent(".TapSayAudio.lock")
    }
    func validate(_ bundle: URL, package: Bool = false) throws -> [String: Any] {
        try rejectLinks(bundle)
        guard let enumerator = fm.enumerator(at: bundle, includingPropertiesForKeys: [.isSymbolicLinkKey]) else { throw Failure("载荷不存在") }
        for case let item as URL in enumerator { try rejectLinks(item) }
        let info = try PropertyListSerialization.propertyList(from: Data(contentsOf: bundle.appendingPathComponent("Contents/Info.plist")), format: nil) as? [String: Any] ?? [:]
        try require(info["CFBundleIdentifier"] as? String == field("bundle_identifier"), "驱动标识不匹配")
        try require(info["CFBundleExecutable"] as? String == field("executable_name"), "驱动入口不匹配")
        let factory = info["CFPlugInFactories"] as? [String: String] ?? [:]
        try require(factory[field("plugin_factory_uuid")] == "TapSayAudio_Create", "驱动工厂标识不匹配")
        let types = info["CFPlugInTypes"] as? [String: [String]] ?? [:]
        try require(types["443ABAB8-E7B3-491A-B985-BEB9187030DB"] == [field("plugin_factory_uuid")], "插件接口类型不匹配")
        if package {
            try require(info["CFBundleShortVersionString"] as? String == product["version"] as? String, "载荷版本与包元数据不一致")
            try require(info["CFBundleVersion"] as? String == product["build_number"] as? String, "载荷构建号不一致")
        }
        let binary = try Data(contentsOf: bundle.appendingPathComponent("Contents/MacOS/TapSayAudio"))
        try require(binary.count >= 32 && Array(binary.prefix(4)) == [0xcf, 0xfa, 0xed, 0xfe], "驱动不是独立架构的 Mach-O")
        let cpu = (0..<4).reduce(UInt32(0)) { partial, offset in
            partial | UInt32(binary[4 + offset]) << (offset * 8)
        }
        let expectedCPU: UInt32 = hostArchitecture() == "arm64" ? 0x0100000c : 0x01000007
        try require(cpu == expectedCPU, "安装包架构与实际主机不一致：CPU \(String(cpu, radix: 16))，期望 \(String(expectedCPU, radix: 16))")
        for key in ["device_uid", "device_name"] {
            try require(binary.range(of: Data(field(key).utf8)) != nil, "驱动缺少设备身份：\(key)")
        }
        return info
    }
    func checkState() throws {
        try rejectLinks(target); try rejectLinks(state); try rejectLinks(lock)
        if exists(state) {
            let old = try json(state)
            try require(old["target"] as? String == target.path && old["bundle_identifier"] as? String == field("bundle_identifier"), "状态身份或目标不匹配")
        }
        if exists(target) { _ = try validate(target) }
    }
    func withLock(_ body: () throws -> Void) throws {
        try rejectLinks(lock)
        try fm.createDirectory(at: lock.deletingLastPathComponent(), withIntermediateDirectories: true)
        let fd = open(lock.path, O_CREAT | O_RDWR | O_NOFOLLOW, 0o600)
        try require(fd >= 0, "无法创建事务锁")
        defer { close(fd) }
        try require(fileLock(fd, LOCK_EX | LOCK_NB) == 0, "已有安装或卸载事务正在运行")
        defer { _ = fileLock(fd, LOCK_UN) }
        try body()
    }
    func preflight(_ payload: URL) throws {
        _ = try validate(payload, package: true)
        try checkState()
        let oldVersion = exists(target) ? (try validate(target)["CFBundleShortVersionString"] as? String ?? "未知") : "未安装"
        print("预检通过：当前 \(oldVersion)，目标 \(product["version"]!)，架构 \(hostArchitecture())")
        print("将更改：\(target.path)；\(state.deletingLastPathComponent().path)。允许升级、重装和降级。")
    }
    func activate() -> String {
        if testing { return "not_run" }
        let first = try? run("/bin/launchctl", ["kickstart", "-k", "system/com.apple.audio.coreaudiod"])
        if first?.0 == 0 { return "pending_verification" }
        let second = try? run("/usr/bin/killall", ["coreaudiod"])
        return second?.0 == 0 ? "pending_verification" : "restart_required"
    }
    func receiptExists() throws -> Bool {
        if testing { return false }
        let result = try run("/usr/sbin/pkgutil", ["--pkgs"])
        try require(result.0 == 0, "无法读取安装收据，不能确认卸载状态：\(result.1)")
        return result.1.split(whereSeparator: \.isNewline).contains(Substring(field("package_receipt_identifier")))
    }
    func install(_ payload: URL, failure: String?) throws {
        try preflight(payload)
        try withLock {
            try preflight(payload)
            let pending = try TransactionRecovery.processPending(
                transactionRoot: state.deletingLastPathComponent().appendingPathComponent("transactions"),
                target: target, state: state, validateDriver: { _ = try validate($0) },
                injectCleanupFailure: failure == "pending-cleanup"
            )
            pending.messages.forEach { print($0) }
            let hadTarget = exists(target)
            let previousState = exists(state) ? try Data(contentsOf: state) : nil
            let transactionID = UUID().uuidString
            let transaction = state.deletingLastPathComponent()
                .appendingPathComponent("transactions/\(transactionID)")
            let staged = target.deletingLastPathComponent()
                .appendingPathComponent(".TapSayAudio-\(transactionID).driver")
            let previous = target.deletingLastPathComponent()
                .appendingPathComponent(".TapSayAudio-\(transactionID).previous")
            let previousStateURL = transaction.appendingPathComponent("previous-state.json")
            var record = TransactionRecord(
                transactionID: transactionID, deviceUID: field("device_uid"),
                bundleIdentifier: field("bundle_identifier"),
                receipt: field("package_receipt_identifier"), target: target.path,
                state: state.path, previous: hadTarget ? previous.path : "",
                staged: staged.path, previousState: hadTarget && previousState != nil
                    ? previousStateURL.path : "", hadTarget: hadTarget
            )
            try rejectLinks(transaction)
            try fm.createDirectory(at: transaction, withIntermediateDirectories: true)
            try record.write(to: transaction)
            try TransactionRecovery.validateRecordAfterWrite(record: record, directory: transaction)
            if let previousState, hadTarget {
                try previousState.write(to: previousStateURL, options: .atomic)
                try require(try Data(contentsOf: previousStateURL) == previousState,
                            "旧状态副本回读不一致")
            }
            if failure == "backup" {
                try TransactionRecovery.cleanPrepared(
                    record: record, directory: transaction, injectCleanupFailure: false
                )
                throw Failure("注入备份失败；未更改原驱动")
            }
            try fm.createDirectory(at: target.deletingLastPathComponent(), withIntermediateDirectories: true)
            var moved = false, deployed = false
            do {
                try fm.copyItem(at: payload, to: staged)
                _ = try validate(staged, package: true)
                if failure == "staged" { throw Failure("注入部署前失败") }
                record = try record.updating(phase: .replacing, terminal: .active,
                                             terminalResult: TransactionTerminalResult.none,
                                             cleanup: TransactionCleanup.none,
                                             cleanupRemainingPaths: [], cleanupReason: "")
                try record.write(to: transaction)
                try TransactionRecovery.validateRecordAfterWrite(record: record, directory: transaction)
                if failure == "move" { throw Failure("注入移动前失败") }
                if hadTarget {
                    try move(target, previous)
                    moved = true
                }
                try move(staged, target)
                deployed = true
                record = try record.updating(phase: .validating, terminal: .active,
                                             terminalResult: TransactionTerminalResult.none,
                                             cleanup: TransactionCleanup.none,
                                             cleanupRemainingPaths: [], cleanupReason: "")
                try record.write(to: transaction)
                try TransactionRecovery.validateRecordAfterWrite(record: record, directory: transaction)
                if ["deployed", "rollback", "cleanup-rollback"].contains(failure) {
                    throw Failure("注入部署后失败")
                }
                _ = try validate(target, package: true)
                if failure == "state-write" { throw Failure("注入状态写入前失败") }
                var result: [String: Any] = [
                    "product": "TapSay Audio", "version": product["version"]!, "build_number": product["build_number"]!,
                    "architecture": hostArchitecture(), "target": target.path,
                    "bundle_identifier": field("bundle_identifier"), "device_uid": field("device_uid"),
                    "receipt": field("package_receipt_identifier"), "transaction": transaction.path,
                    "installed_at": ISO8601DateFormatter().string(from: Date()),
                    "verification_status": "not_run", "audio_chain_status": "not_run"
                ]
                result["activation_status"] = activate()
                try writeJSON(result, state)
                record = try record.updating(phase: .committed, terminal: .success,
                                             terminalResult: .deployed, cleanup: .pending,
                                             cleanupRemainingPaths: [], cleanupReason: "")
                try record.write(to: transaction)
                try TransactionRecovery.validateRecordAfterWrite(record: record, directory: transaction)
                do {
                    try TransactionRecovery.cleanupCommitted(
                        record: record, directory: transaction,
                        injectFailure: failure == "cleanup"
                    )
                } catch {
                    if exists(transaction) {
                        try TransactionRecovery.recordCleanupFailure(
                            record: record, directory: transaction, error: error
                        )
                    }
                    throw Failure("新版本已部署，但本次临时材料清理未完成；请重新运行安装或卸载工具清理：\(error)")
                }
                print("驱动文件已部署；设备就绪待核验，真实音频链路未验证。\(result["activation_status"]!)")
            } catch {
                if record.phase == .committed {
                    throw error
                }
                if !moved && !deployed && record.phase == .prepared {
                    try TransactionRecovery.cleanPrepared(
                        record: record, directory: transaction,
                        injectCleanupFailure: failure == "cleanup-rollback"
                    )
                } else {
                    try TransactionRecovery.recoverAfterInstallFailure(
                        record: record, directory: transaction, target: target, state: state,
                        validateDriver: { _ = try validate($0) },
                        forceFailure: failure == "rollback",
                        injectCleanupFailure: failure == "cleanup-rollback"
                    )
                    if !testing && deployed { _ = activate() }
                }
                throw Failure("部署失败，\(hadTarget ? "已恢复安装前版本" : "已清理本次载荷")：\(error)")
            }
        }
    }
    func uninstall(confirmed: Bool) throws -> UninstallResult {
        try require(confirmed, "卸载需要明确确认：--yes")
        var report: UninstallResult?
        try withLock {
            try checkState()
            let receipt = try receiptExists()
            let wasInstalled = exists(target) || exists(state) || receipt
            let transactionRoot = state.deletingLastPathComponent().appendingPathComponent("transactions")
            let retainedBackups = (fm.enumerator(at: transactionRoot, includingPropertiesForKeys: nil)?
                .allObjects as? [URL] ?? []).filter { $0.lastPathComponent == "backup.driver" && exists($0) }
            if exists(target) { try fm.removeItem(at: target) }
            if receipt {
                let result = try run("/usr/sbin/pkgutil", ["--forget", field("package_receipt_identifier")])
                try require(result.0 == 0, "驱动已移除，收据清理失败：\(result.1)")
            }
            if exists(state) { try fm.removeItem(at: state) }
            let driverAbsent = !exists(target), stateAbsent = !exists(state)
            let receiptAbsent = try !receiptExists()
            let presence: UninstallDeviceStatus
            if testing { presence = .notChecked }
            else {
                let before = uninstallDeviceStatus()
                if wasInstalled || before != .absent { _ = activate() }
                presence = waitForUninstallDeviceRemoval()
            }
            report = UninstallResult.outcome(driverAbsent: driverAbsent, receiptAbsent: receiptAbsent,
                                             stateAbsent: stateAbsent, deviceStatus: presence,
                                             wasInstalled: wasInstalled, backupPaths: retainedBackups.map(\.path))
        }
        guard let report else { throw Failure("未生成卸载结果") }
        return report
    }
}

let uninstallReportRequested = CommandLine.arguments.contains("--uninstall-report")
do {
    var args = Array(CommandLine.arguments.dropFirst())
    args.removeAll { $0 == "--uninstall-report" }
    func option(_ name: String) throws -> String? {
        guard let index = args.firstIndex(of: name) else { return nil }
        try require(index + 1 < args.count, "参数缺少值：\(name)")
        let value = args[index + 1]; args.removeSubrange(index...index + 1); return value
    }
    let metadataPath = try option("--metadata") ?? URL(fileURLWithPath: CommandLine.arguments[0]).deletingLastPathComponent().appendingPathComponent("product.json").path
    let testPath = try option("--test-root")
    let failure = try option("--inject-failure")
    try require(failure == nil || testPath != nil, "故障注入只允许隔离测试")
    let transaction = try Transaction(metadataURL: URL(fileURLWithPath: metadataPath), testRoot: testPath.map { URL(fileURLWithPath: $0).standardizedFileURL })
    guard let command = args.first else { throw Failure("用法：TapSayAudioTransaction preflight|install|uninstall [载荷] [--yes]") }
    switch command {
    case "preflight", "install":
        try require(!uninstallReportRequested, "结构化卸载结果只用于卸载命令")
        try require(args.count == 2, "需要唯一载荷路径")
        let payload = URL(fileURLWithPath: args[1]).standardizedFileURL
        if command == "preflight" { try transaction.preflight(payload) }
        else { try transaction.install(payload, failure: failure) }
    case "uninstall":
        try require(args.count <= 2 && (args.count == 1 || args[1] == "--yes"), "卸载参数异常")
        let result = try transaction.uninstall(confirmed: args.contains("--yes"))
        if uninstallReportRequested {
            FileHandle.standardOutput.write(try JSONEncoder().encode(result))
            FileHandle.standardOutput.write(Data([0x0a]))
        } else { print(result.message) }
        if result.status == .failed { exit(1) }
    default: throw Failure("未知命令：\(command)")
    }
} catch {
    if uninstallReportRequested, let data = try? JSONEncoder().encode(UninstallResult.failure("操作失败：\(error)")) {
        FileHandle.standardOutput.write(data)
        FileHandle.standardOutput.write(Data([0x0a]))
    }
    fputs("操作失败：\(error)\n", stderr)
    exit(1)
}
