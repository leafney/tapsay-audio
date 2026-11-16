// SPDX-License-Identifier: GPL-3.0-only
import Foundation

enum UninstallDeviceStatus: String, Codable {
    case absent, present, unavailable, notChecked
}

enum UninstallStatus: String, Codable {
    case removed, notInstalled, restartRequired, unverified, failed
}

struct UninstallResult: Codable {
    let schemaVersion: Int
    let command: String
    let deviceUID: String
    let status: UninstallStatus
    let driverAbsent: Bool
    let receiptAbsent: Bool
    let stateAbsent: Bool
    let deviceStatus: UninstallDeviceStatus
    let cleanupStatus: CleanupStatus
    let removedMaterialCount: Int
    let remainingMaterialCount: Int
    let remainingPaths: [String]
    let message: String

    static let uid = "com.leafney.tapsay.audio.device.2ch"

    static func arguments(metadata: URL) -> [String] {
        ["uninstall", "--yes", "--metadata", metadata.path, "--uninstall-report"]
    }

    static func outcome(driverAbsent: Bool, receiptAbsent: Bool, stateAbsent: Bool,
                        deviceStatus: UninstallDeviceStatus, wasInstalled: Bool,
                        backupPaths: [String] = [],
                        cleanup: HistoricalCleanupResult? = nil) -> Self {
        let cleanup = cleanup ?? HistoricalCleanupResult(
            status: backupPaths.isEmpty ? .notNeeded : .blocked,
            removedMaterialCount: 0,
            remainingMaterialCount: backupPaths.count,
            remainingPaths: backupPaths,
            reasons: []
        )
        let clean = driverAbsent && receiptAbsent && stateAbsent
        let status: UninstallStatus
        let text: String
        let isHistoryRemainder = cleanup.status == .partial || cleanup.status == .blocked
        if !clean {
            status = .failed
            text = "卸载未完成，仍有本项目文件、安装状态或收据残留。请保留错误信息以便排查。"
        } else {
            switch deviceStatus {
            case .absent:
                if isHistoryRemainder {
                    status = .removed
                    text = "TapSay Audio 声卡和专属安装文件已卸载，但部分历史安装材料未能安全清理。"
                } else {
                    status = wasInstalled ? .removed : .notInstalled
                    text = wasInstalled ? "卸载完成：驱动文件、安装状态和收据已清理，系统中已无 TapSay Audio 设备。"
                                        : "TapSay Audio 当前未安装，系统中也未发现该设备。"
                }
            case .present:
                status = .restartRequired
                text = "驱动文件、安装状态和收据已清理，但系统仍保留 TapSay Audio 设备。请保存工作并手动重新启动 Mac，重启后再检查输入和输出设备列表。工具不会自动重启。"
            case .unavailable, .notChecked:
                status = .unverified
                text = "驱动文件、安装状态和收据已清理，但无法确认系统设备是否移除。请保存工作并手动重新启动 Mac，重启后再检查设备列表；当前不能确认卸载完全生效。"
            }
        }
        let cleanupText: String
        switch cleanup.status {
        case .partial, .blocked:
            let paths = cleanup.remainingPaths.isEmpty
                ? cleanup.reasons.joined(separator: "；")
                : cleanup.remainingPaths.joined(separator: "\n")
            cleanupText = "\n\n历史清理未全部完成，以下内容已保留：\n" + paths
        case .pendingDeviceRemoval:
            cleanupText = "\n\n历史安装材料暂未清理。请在系统重启后再次打开卸载工具，以完成清理。"
        case .notNeeded, .complete:
            cleanupText = ""
        }
        return .init(schemaVersion: 2, command: "uninstall", deviceUID: uid, status: status,
                     driverAbsent: driverAbsent, receiptAbsent: receiptAbsent, stateAbsent: stateAbsent,
                     deviceStatus: deviceStatus,
                     cleanupStatus: cleanup.status,
                     removedMaterialCount: cleanup.removedMaterialCount,
                     remainingMaterialCount: cleanup.remainingMaterialCount,
                     remainingPaths: cleanup.remainingPaths,
                     message: text + cleanupText)
    }

    static func failure(_ message: String) -> Self {
        .init(schemaVersion: 2, command: "uninstall", deviceUID: uid, status: .failed,
              driverAbsent: false, receiptAbsent: false, stateAbsent: false,
              deviceStatus: .notChecked, cleanupStatus: .blocked,
              removedMaterialCount: 0, remainingMaterialCount: 0, remainingPaths: [],
              message: message)
    }

    // Launching the privileged process is not evidence that its work succeeded.
    static func decode(_ data: Data) throws -> Self {
        let result = try JSONDecoder().decode(Self.self, from: data)
        guard result.schemaVersion == 2, result.command == "uninstall",
              result.deviceUID == uid, !result.message.isEmpty else {
            throw NSError(domain: "TapSayAudioUninstall", code: 1)
        }
        guard result.removedMaterialCount >= 0, result.remainingMaterialCount >= 0,
              result.remainingMaterialCount == result.remainingPaths.count,
              Set(result.remainingPaths).count == result.remainingPaths.count,
              result.remainingPaths.allSatisfy({ !$0.isEmpty && $0.hasPrefix("/") }) else {
            throw NSError(domain: "TapSayAudioUninstall", code: 4)
        }
        if result.status != .failed {
            guard result.driverAbsent && result.receiptAbsent && result.stateAbsent else {
                throw NSError(domain: "TapSayAudioUninstall", code: 2)
            }
            let valid: Bool
            switch result.status {
            case .removed, .notInstalled: valid = result.deviceStatus == .absent
            case .restartRequired: valid = result.deviceStatus == .present
            case .unverified: valid = [.unavailable, .notChecked].contains(result.deviceStatus)
            case .failed: valid = false
            }
            guard valid else { throw NSError(domain: "TapSayAudioUninstall", code: 3) }
            let cleanupValid: Bool
            switch result.status {
            case .removed:
                cleanupValid = result.deviceStatus == .absent
                    && (([.notNeeded, .complete].contains(result.cleanupStatus)
                         && result.remainingMaterialCount == 0)
                        || ([.partial, .blocked].contains(result.cleanupStatus)
                            && result.remainingMaterialCount > 0))
            case .notInstalled:
                cleanupValid = result.deviceStatus == .absent
                    && [.notNeeded, .complete].contains(result.cleanupStatus)
                    && result.remainingMaterialCount == 0
            case .restartRequired:
                cleanupValid = result.cleanupStatus == .pendingDeviceRemoval
            case .unverified:
                cleanupValid = [.pendingDeviceRemoval, .blocked, .partial]
                    .contains(result.cleanupStatus)
            case .failed:
                cleanupValid = false
            }
            guard cleanupValid else { throw NSError(domain: "TapSayAudioUninstall", code: 5) }
        } else {
            guard result.cleanupStatus == .blocked else {
                throw NSError(domain: "TapSayAudioUninstall", code: 5)
            }
        }
        if result.driverAbsent && result.receiptAbsent && result.stateAbsent
            && result.deviceStatus != .absent
            && [UninstallStatus.removed, .notInstalled].contains(result.status) {
            throw NSError(domain: "TapSayAudioUninstall", code: 7)
        }
        if result.status != .failed && [.partial, .blocked].contains(result.cleanupStatus) {
            guard result.remainingMaterialCount > 0 else {
                throw NSError(domain: "TapSayAudioUninstall", code: 6)
            }
        }
        return result
    }

    var title: String {
        switch status {
        case .removed:
            return [.partial, .blocked].contains(cleanupStatus)
                ? "声卡已卸载，部分历史材料未清理"
                : "卸载完成"
        case .notInstalled: return "当前未安装"
        case .restartRequired: return "卸载待重启生效"
        case .unverified: return "卸载生效状态待确认"
        case .failed: return "卸载未完成"
        }
    }
}

func verifyInstallDeviceAppearance(read: () -> UninstallDeviceStatus,
                                   now: () -> TimeInterval,
                                   pause: () -> Void) -> UninstallDeviceStatus {
    let deadline = now() + 5
    repeat {
        if read() == .present { return .present }
        pause()
    } while now() < deadline
    return read()
}

func verifyUninstallDeviceRemoval(read: () -> UninstallDeviceStatus,
                                  now: () -> TimeInterval,
                                  pause: () -> Void) -> UninstallDeviceStatus {
    let deadline = now() + 5
    var previous: UninstallDeviceStatus = .unavailable
    repeat {
        let current = read()
        if current == .absent && previous == .absent { return .absent }
        previous = current
        pause()
    } while now() < deadline
    let last = read()
    return last == .absent && previous != .absent ? .unavailable : last
}
