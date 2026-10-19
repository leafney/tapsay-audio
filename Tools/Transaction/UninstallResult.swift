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
    let message: String

    static let uid = "com.leafney.tapsay.audio.device.2ch"

    static func arguments(metadata: URL) -> [String] {
        ["uninstall", "--yes", "--metadata", metadata.path, "--uninstall-report"]
    }

    static func outcome(driverAbsent: Bool, receiptAbsent: Bool, stateAbsent: Bool,
                        deviceStatus: UninstallDeviceStatus, wasInstalled: Bool,
                        backupPaths: [String] = []) -> Self {
        let clean = driverAbsent && receiptAbsent && stateAbsent
        let status: UninstallStatus
        let text: String
        if !clean {
            status = .failed
            text = "卸载未完成，仍有本项目文件、安装状态或收据残留。请保留错误信息以便排查。"
        } else {
            switch deviceStatus {
            case .absent:
                status = wasInstalled ? .removed : .notInstalled
                text = wasInstalled ? "卸载完成：驱动文件、安装状态和收据已清理，系统中已无 TapSay Audio 设备。"
                                    : "TapSay Audio 当前未安装，系统中也未发现该设备。"
            case .present:
                status = .restartRequired
                text = "驱动文件、安装状态和收据已清理，但系统仍保留 TapSay Audio 设备。请保存工作并手动重新启动 Mac，重启后再检查输入和输出设备列表。工具不会自动重启。"
            case .unavailable, .notChecked:
                status = .unverified
                text = "驱动文件、安装状态和收据已清理，但无法确认系统设备是否移除。请保存工作并手动重新启动 Mac，重启后再检查设备列表；当前不能确认卸载完全生效。"
            }
        }
        let backups = backupPaths.isEmpty ? "" : "\n\n恢复备份仍保留于：\n" + backupPaths.joined(separator: "\n")
        return .init(schemaVersion: 1, command: "uninstall", deviceUID: uid, status: status,
                     driverAbsent: driverAbsent, receiptAbsent: receiptAbsent, stateAbsent: stateAbsent,
                     deviceStatus: deviceStatus, message: text + backups)
    }

    static func failure(_ message: String) -> Self {
        .init(schemaVersion: 1, command: "uninstall", deviceUID: uid, status: .failed,
              driverAbsent: false, receiptAbsent: false, stateAbsent: false,
              deviceStatus: .notChecked, message: message)
    }

    // Launching the privileged process is not evidence that its work succeeded.
    static func decode(_ data: Data) throws -> Self {
        let result = try JSONDecoder().decode(Self.self, from: data)
        guard result.schemaVersion == 1, result.command == "uninstall",
              result.deviceUID == uid, !result.message.isEmpty else {
            throw NSError(domain: "TapSayAudioUninstall", code: 1)
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
        }
        return result
    }

    var title: String {
        switch status {
        case .removed: return "卸载完成"
        case .notInstalled: return "当前未安装"
        case .restartRequired: return "卸载待重启生效"
        case .unverified: return "卸载生效状态待确认"
        case .failed: return "卸载未完成"
        }
    }
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
