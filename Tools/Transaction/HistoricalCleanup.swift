// SPDX-License-Identifier: GPL-3.0-only
import Foundation

enum CleanupStatus: String, Codable {
    case notNeeded = "notNeeded"
    case complete
    case partial
    case blocked
    case pendingDeviceRemoval
}

struct HistoricalCleanupResult {
    let status: CleanupStatus
    let removedMaterialCount: Int
    let remainingMaterialCount: Int
    let remainingPaths: [String]
    let reasons: [String]
}

enum HistoricalCleanup {
    static let fm = FileManager.default

    static func clean(transactionRoot: URL, injectFailureOnOrdinal: Int? = nil,
                      block: Bool = false) -> HistoricalCleanupResult {
        guard !block else {
            return result(.pendingDeviceRemoval, removed: [], remaining: [transactionRoot.path],
                          reasons: ["设备移除状态尚未确认"])
        }
        guard fm.fileExists(atPath: transactionRoot.path) else {
            return result(.notNeeded, removed: [], remaining: [], reasons: [])
        }
        let directories: [URL]
        do {
            directories = try fm.contentsOfDirectory(
                at: transactionRoot,
                includingPropertiesForKeys: [.isDirectoryKey, .isSymbolicLinkKey],
                options: []
            ).sorted { $0.lastPathComponent < $1.lastPathComponent }
        } catch {
            return result(.blocked, removed: [], remaining: [transactionRoot.path],
                          reasons: ["无法枚举事务目录：\(error)"])
        }

        var removed: [String] = []
        var remaining: [String] = []
        var reasons: [String] = []
        var deletionOrdinal = 0

        for directory in directories {
            let name = directory.lastPathComponent
            guard UUID(uuidString: name)?.uuidString == name else {
                remaining.append(directory.path)
                reasons.append("事务目录名不是标准 UUID，已保留")
                continue
            }
            let values: URLResourceValues
            do {
                values = try directory.resourceValues(forKeys: [.isDirectoryKey, .isSymbolicLinkKey])
            } catch {
                remaining.append(directory.path)
                reasons.append("无法检查事务目录：\(error)")
                continue
            }
            guard values.isDirectory == true, values.isSymbolicLink != true else {
                remaining.append(directory.path)
                reasons.append("事务目录不是普通目录或经过链接，已保留")
                continue
            }

            let entries: [URL]
            do {
                entries = try fm.contentsOfDirectory(
                    at: directory,
                    includingPropertiesForKeys: [.isDirectoryKey, .isSymbolicLinkKey],
                    options: []
                )
            } catch {
                remaining.append(directory.path)
                reasons.append("无法枚举事务目录内容：\(error)")
                continue
            }
            let names = Set(entries.map(\.lastPathComponent))
            let unknown = names.subtracting(["backup.driver", "previous-state.json"])
            if !unknown.isEmpty {
                remaining.append(directory.path)
                reasons.append("事务目录含未知或活动对象，已整体保留")
                continue
            }

            do {
                let previousState = entries.first { $0.lastPathComponent == "previous-state.json" }
                if let previousState {
                    try verifyPreviousState(previousState)
                }
                guard let backup = entries.first(where: { $0.lastPathComponent == "backup.driver" }) else {
                    // Empty directories are harmless and do not need manual intervention.
                    if entries.isEmpty {
                        try fm.removeItem(at: directory)
                        removed.append(directory.path)
                    } else {
                        remaining.append(directory.path)
                        reasons.append("事务目录没有可核验的历史驱动，已保留")
                    }
                    continue
                }
                try verifyBackup(backup)
                deletionOrdinal += 1
                if injectFailureOnOrdinal == deletionOrdinal {
                    remaining.append(directory.path)
                    reasons.append("注入删除失败，保留候选")
                    continue
                }
                try removeOrdinary(backup)
                removed.append(backup.path)
                if let previousState {
                    try removeOrdinary(previousState)
                    removed.append(previousState.path)
                }
                let leftovers = try fm.contentsOfDirectory(atPath: directory.path)
                if leftovers.isEmpty {
                    try fm.removeItem(at: directory)
                    removed.append(directory.path)
                } else {
                    remaining.append(directory.path)
                    reasons.append("事务目录仍有未知内容，已保留")
                }
            } catch {
                remaining.append(directory.path)
                reasons.append("历史材料核验或删除失败：\(error)")
            }
        }
        let status: CleanupStatus
        if remaining.isEmpty {
            status = removed.isEmpty ? .notNeeded : .complete
        } else if removed.isEmpty {
            status = .blocked
        } else {
            status = .partial
        }
        return result(status, removed: removed, remaining: remaining, reasons: reasons)
    }

    static func hasCandidates(transactionRoot: URL) -> Bool {
        guard let directories = try? fm.contentsOfDirectory(
            at: transactionRoot, includingPropertiesForKeys: nil, options: []
        ) else { return false }
        return !directories.isEmpty
    }

    private static func verifyBackup(_ backup: URL) throws {
        let values = try backup.resourceValues(forKeys: [.isDirectoryKey, .isSymbolicLinkKey])
        try require(values.isDirectory == true && values.isSymbolicLink != true,
                    "历史驱动不是普通目录或经过链接")
        let infoURL = backup.appendingPathComponent("Contents/Info.plist")
        guard let enumerator = fm.enumerator(
            at: backup,
            includingPropertiesForKeys: [.isSymbolicLinkKey],
            options: []
        ) else {
            throw Failure("无法枚举历史驱动")
        }
        for case let item as URL in enumerator {
            try require(
                (try item.resourceValues(forKeys: [.isSymbolicLinkKey])).isSymbolicLink != true,
                "历史驱动内部包含符号链接：\(item.path)"
            )
        }
        let info = try PropertyListSerialization.propertyList(
            from: Data(contentsOf: infoURL), format: nil
        ) as? [String: Any] ?? [:]
        try require(info["CFBundleIdentifier"] as? String == "com.leafney.tapsay.audio.driver",
                    "历史驱动 Bundle ID 不匹配")
        try require(info["CFBundleExecutable"] as? String == "TapSayAudio",
                    "历史驱动入口不匹配")
        let factories = info["CFPlugInFactories"] as? [String: String] ?? [:]
        try require(factories["CC1226D1-A123-47B7-B113-5228AB089AA8"] == "TapSayAudio_Create",
                    "历史驱动工厂 UUID 不匹配")
        let types = info["CFPlugInTypes"] as? [String: [String]] ?? [:]
        try require(types["443ABAB8-E7B3-491A-B985-BEB9187030DB"]
                    == ["CC1226D1-A123-47B7-B113-5228AB089AA8"],
                    "历史驱动插件接口类型不匹配")
        try require(info["CFBundleShortVersionString"] is String && info["CFBundleVersion"] is String,
                    "历史驱动版本信息不可读")

        let binary = try Data(contentsOf: backup.appendingPathComponent("Contents/MacOS/TapSayAudio"))
        try require(binary.count >= 32
                    && Set([Array(binary.prefix(4)), [0xfe, 0xed, 0xfa, 0xcf],
                            [0xca, 0xfe, 0xba, 0xbe]]).contains(Array(binary.prefix(4))),
                    "历史驱动不是可识别 Mach-O")
        try require(binary.range(of: Data("com.leafney.tapsay.audio.device.2ch".utf8)) != nil,
                    "历史驱动缺少设备 UID")
        try require(binary.range(of: Data("TapSay Audio".utf8)) != nil,
                    "历史驱动缺少产品名称")
    }

    private static func verifyPreviousState(_ url: URL) throws {
        let values = try url.resourceValues(forKeys: [.isSymbolicLinkKey])
        try require(values.isSymbolicLink != true, "旧状态副本经过链接")
        let object = try JSONSerialization.jsonObject(with: Data(contentsOf: url))
        guard let state = object as? [String: Any] else {
            throw Failure("旧状态副本不是 JSON 对象")
        }
        try require((state["target"] as? String)?.hasSuffix(
            "/Library/Audio/Plug-Ins/HAL/TapSayAudio.driver") == true,
                    "旧状态目标不匹配")
        try require(state["bundle_identifier"] as? String == "com.leafney.tapsay.audio.driver",
                    "旧状态 Bundle ID 不匹配")
        try require(state["device_uid"] as? String == "com.leafney.tapsay.audio.device.2ch",
                    "旧状态设备 UID 不匹配")
    }

    private static func removeOrdinary(_ url: URL) throws {
        try require((try url.resourceValues(forKeys: [.isSymbolicLinkKey])).isSymbolicLink != true,
                    "拒绝删除符号链接：\(url.path)")
        try fm.removeItem(at: url)
    }

    private static func result(_ status: CleanupStatus, removed: [String],
                               remaining: [String], reasons: [String]) -> HistoricalCleanupResult {
        HistoricalCleanupResult(
            status: status,
            removedMaterialCount: removed.count,
            remainingMaterialCount: remaining.count,
            remainingPaths: Array(Set(remaining)).sorted(),
            reasons: Array(Set(reasons)).sorted()
        )
    }
}
