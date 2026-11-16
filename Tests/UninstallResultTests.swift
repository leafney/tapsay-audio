// SPDX-License-Identifier: GPL-3.0-only
import Foundation

@main struct UninstallResultTests {
    static func check(_ condition: Bool, _ message: String) {
        if !condition { fatalError(message) }
    }
    static func main() throws {
        let args = Array(CommandLine.arguments.dropFirst())
        if args.count == 2 && args[0] == "--arguments" {
            FileHandle.standardOutput.write(try JSONEncoder().encode(UninstallResult.arguments(metadata: URL(fileURLWithPath: args[1]))))
            return
        }
        if args == ["--device-status"] {
            print(uninstallDeviceStatus().rawValue)
            return
        }
        let metadata = URL(fileURLWithPath: "/private/tmp/含 空格/product.json")
        check(UninstallResult.arguments(metadata: metadata) == ["uninstall", "--yes", "--metadata", metadata.path, "--uninstall-report"],
              "必须把正确的命令及配置路径传给事务程序")
        let complete = HistoricalCleanupResult(
            status: .complete, removedMaterialCount: 2,
            remainingMaterialCount: 0, remainingPaths: [], reasons: []
        )
        for presence in [UninstallDeviceStatus.absent, .present, .unavailable, .notChecked] {
            for installed in [true, false] {
                let result = UninstallResult.outcome(driverAbsent: true, receiptAbsent: true, stateAbsent: true,
                                                     deviceStatus: presence, wasInstalled: installed,
                                                     cleanup: presence == .absent ? complete
                                                        : HistoricalCleanupResult(
                                                            status: .pendingDeviceRemoval,
                                                            removedMaterialCount: 0,
                                                            remainingMaterialCount: 0,
                                                            remainingPaths: [], reasons: []
                                                        ))
                let decoded = try UninstallResult.decode(JSONEncoder().encode(result))
                let expected: UninstallStatus = presence == .absent ? (installed ? .removed : .notInstalled)
                    : (presence == .present ? .restartRequired : .unverified)
                check(decoded.status == expected, "不能把文件清理当成设备消失")
                if presence != .absent { check(decoded.message.contains("重新启动 Mac"), "必须提示重启及待确认状态") }
            }
        }
        for fields in [(false, true, true), (true, false, true), (true, true, false)] {
            let result = UninstallResult.outcome(driverAbsent: fields.0, receiptAbsent: fields.1, stateAbsent: fields.2,
                                                 deviceStatus: .absent, wasInstalled: true)
            check(result.status == .failed, "残留必须失败")
        }
        let good = UninstallResult.outcome(driverAbsent: true, receiptAbsent: true, stateAbsent: true,
                                           deviceStatus: .absent, wasInstalled: true,
                                           cleanup: complete)
        let object = try JSONSerialization.jsonObject(with: JSONEncoder().encode(good)) as! [String: Any]
        var invalid: [Data] = [Data(), Data("卸载已执行".utf8), Data("{}".utf8)]
        for (key, value) in [("schemaVersion", 1 as Any), ("command", "install" as Any),
                             ("deviceUID", "other" as Any), ("driverAbsent", false as Any),
                             ("deviceStatus", "present" as Any), ("status", "unknown" as Any),
                             ("cleanupStatus", "partial" as Any),
                             ("remainingMaterialCount", 1 as Any)] {
            var changed = object; changed[key] = value
            invalid.append(try JSONSerialization.data(withJSONObject: changed))
        }
        var missing = object
        missing.removeValue(forKey: "cleanupStatus")
        invalid.append(try JSONSerialization.data(withJSONObject: missing))
        var truncated = try JSONEncoder().encode(good)
        truncated.removeLast()
        invalid.append(truncated)
        let partial = HistoricalCleanupResult(
            status: .partial, removedMaterialCount: 1, remainingMaterialCount: 1,
            remainingPaths: ["/Library/Application Support/TapSay Audio/transactions/EXAMPLE"],
            reasons: ["未知对象已保留"]
        )
        let removedWithPartial = UninstallResult.outcome(
            driverAbsent: true, receiptAbsent: true, stateAbsent: true,
            deviceStatus: .absent, wasInstalled: true, cleanup: partial
        )
        check(removedWithPartial.status == .removed, "历史部分清理应保持声卡已卸载状态")
        check(removedWithPartial.title == "声卡已卸载，部分历史材料未清理",
              "部分清理标题必须准确")
        check(removedWithPartial.message.contains("历史清理未全部完成"),
              "部分清理必须显示保留路径说明")
        let blocked = HistoricalCleanupResult(
            status: .blocked, removedMaterialCount: 0, remainingMaterialCount: 1,
            remainingPaths: ["/Library/Application Support/TapSay Audio/transactions/EXAMPLE"],
            reasons: ["身份不符"]
        )
        let unverified = UninstallResult.outcome(
            driverAbsent: true, receiptAbsent: true, stateAbsent: true,
            deviceStatus: .unavailable, wasInstalled: true, cleanup: blocked
        )
        for cleanup in [partial, blocked, complete] {
            for installed in [true, false] {
                let result = UninstallResult.outcome(
                    driverAbsent: true, receiptAbsent: true, stateAbsent: true,
                    deviceStatus: .absent, wasInstalled: installed, cleanup: cleanup)
                let decoded = try UninstallResult.decode(JSONEncoder().encode(result))
                check(decoded.title == result.title && decoded.remainingPaths == result.remainingPaths,
                      "历史清理结果必须可往返解码并保留真实路径")
            }
        }
        _ = try UninstallResult.decode(JSONEncoder().encode(unverified))
        for presence in [UninstallDeviceStatus.absent, .unavailable, .notChecked] {
            for cleanup in [partial, blocked] {
                let result = UninstallResult.outcome(
                    driverAbsent: true, receiptAbsent: true, stateAbsent: true,
                    deviceStatus: presence, wasInstalled: true, cleanup: cleanup)
                _ = try UninstallResult.decode(JSONEncoder().encode(result))
            }
        }
        let partialObject = try JSONSerialization.jsonObject(
            with: JSONEncoder().encode(removedWithPartial)) as! [String: Any]
        for paths in [["relative/path"], [""], ["/one", "/one"]] {
            var changed = partialObject
            changed["remainingPaths"] = paths
            changed["remainingMaterialCount"] = paths.count
            invalid.append(try JSONSerialization.data(withJSONObject: changed))
        }
        check(unverified.status == .unverified && unverified.title == "卸载生效状态待确认",
              "设备状态不明不得显示完成")
        var contradictory = object
        contradictory["status"] = "removed"
        contradictory["deviceStatus"] = "present"
        invalid.append(try JSONSerialization.data(withJSONObject: contradictory))
        for data in invalid {
            do { _ = try UninstallResult.decode(data); fatalError("无效或自相矛盾的结果不得显示成功") }
            catch { }
        }
        let failed = try UninstallResult.decode(JSONEncoder().encode(UninstallResult.failure("配置读取失败")))
        check(failed.status == .failed, "事务错误必须可见")
        let pending = UninstallResult.outcome(
            driverAbsent: true, receiptAbsent: true, stateAbsent: true,
            deviceStatus: .present, wasInstalled: true,
            cleanup: HistoricalCleanupResult(
                status: .pendingDeviceRemoval, removedMaterialCount: 0,
                remainingMaterialCount: 0, remainingPaths: [], reasons: []
            )
        )
        _ = try UninstallResult.decode(JSONEncoder().encode(pending))
        var badPartial = object
        badPartial["cleanupStatus"] = "partial"
        badPartial["remainingMaterialCount"] = 1
        badPartial["remainingPaths"] = []
        do {
            _ = try UninstallResult.decode(try JSONSerialization.data(withJSONObject: badPartial))
            fatalError("部分清理必须列出剩余路径")
        } catch {}

        func poll(_ sequence: [UninstallDeviceStatus]) -> UninstallDeviceStatus {
            var clock: TimeInterval = 0
            var index = 0
            return verifyUninstallDeviceRemoval(read: {
                defer { index += 1 }
                return sequence[min(index, sequence.count - 1)]
            }, now: { clock }, pause: { clock += 0.25 })
        }
        check(poll([.present]) == .present, "设备始终存在不得通过")
        check(poll([.unavailable]) == .unavailable, "无法枚举不得通过")
        check(poll([.absent, .present]) == .present, "不能以瞬间消失作为完成")
        check(poll([.present, .unavailable, .absent, .absent]) == .absent, "最终稳定消失应通过")
        check(poll(Array(repeating: .present, count: 20) + [.absent]) == .unavailable,
              "截止时仅一次消失不能确认")
        func installPoll(_ sequence: [UninstallDeviceStatus]) -> UninstallDeviceStatus {
            var clock: TimeInterval = 0
            var index = 0
            return verifyInstallDeviceAppearance(read: {
                defer { index += 1 }
                return sequence[min(index, sequence.count - 1)]
            }, now: { clock }, pause: { clock += 0.25 })
        }
        check(installPoll([.present]) == .present, "已枚举应立即返回")
        check(installPoll([.absent, .unavailable, .present]) == .present, "延迟枚举应识别")
        check(installPoll([.absent]) == .absent, "超时未出现不能当作成功")
        check(installPoll([.unavailable]) == .unavailable, "读取失败不能当作设备不存在")
        check(installPoll(Array(repeating: .absent, count: 20) + [.present]) == .present,
              "截止时出现仍应识别")
        print("卸载参数、结果判定、异常响应及设备等待测试通过")
    }
}
