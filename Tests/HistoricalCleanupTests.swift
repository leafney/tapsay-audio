// SPDX-License-Identifier: GPL-3.0-only
import Foundation

@main struct HistoricalCleanupTests {
    static let fm = FileManager.default

    static func check(_ condition: Bool, _ message: String) {
        if !condition { fatalError(message) }
    }

    static func main() throws {
        check(CommandLine.arguments.count == 2, "需要历史驱动测试载荷路径")
        let driver = URL(fileURLWithPath: CommandLine.arguments[1])
        let root = URL(fileURLWithPath: NSTemporaryDirectory())
            .appendingPathComponent("TapSayHistoricalCleanupTests-\(UUID().uuidString)")
        defer { try? fm.removeItem(at: root) }
        let transactions = root.appendingPathComponent(
            "Library/Application Support/TapSay Audio/transactions"
        )
        try fm.createDirectory(at: transactions, withIntermediateDirectories: true)

        let firstID = "11111111-1111-4111-8111-111111111111"
        let secondID = "22222222-2222-4222-8222-222222222222"
        let first = try makeLegacy(transactions, id: firstID, driver: driver)
        let second = try makeLegacy(transactions, id: secondID, driver: driver)
        var cleanup = HistoricalCleanup.clean(transactionRoot: transactions,
                                              injectFailureOnOrdinal: 2)
        check(cleanup.status == .partial, "第二个候选失败时必须返回部分清理")
        check(cleanup.removedMaterialCount > 0, "必须保留第一次成功删除计数")
        check(!fm.fileExists(atPath: first.path), "第一个合法候选应删除")
        check(fm.fileExists(atPath: second.path), "注入失败候选必须保留")

        cleanup = HistoricalCleanup.clean(transactionRoot: transactions)
        check(cleanup.status == .complete, "重试应清理剩余合法候选")
        check(!fm.fileExists(atPath: second.path), "重试必须清理剩余候选")
        check((try fm.contentsOfDirectory(atPath: transactions.path)).isEmpty,
              "合法历史清理后不得创建或遗留目录")

        let unknownID = "33333333-3333-4333-8333-333333333333"
        let unknown = try makeLegacy(transactions, id: unknownID, driver: driver)
        try Data("unknown".utf8).write(to: unknown.appendingPathComponent("keep.txt"))
        cleanup = HistoricalCleanup.clean(transactionRoot: transactions)
        check(cleanup.status == .blocked, "未知对象必须阻止清理")
        check(fm.fileExists(atPath: unknown.path)
              && fm.fileExists(atPath: unknown.appendingPathComponent("backup.driver").path),
              "未知对象必须整体保留")

        let badID = "44444444-4444-4444-8444-444444444444"
        let bad = transactions.appendingPathComponent(badID)
        try fm.createDirectory(at: bad, withIntermediateDirectories: true)
        try Data("not a driver".utf8).write(to: bad.appendingPathComponent("backup.driver"))
        cleanup = HistoricalCleanup.clean(transactionRoot: transactions)
        check(cleanup.status == .blocked, "身份错误必须阻止清理")
        check(fm.fileExists(atPath: bad.appendingPathComponent("backup.driver").path),
              "身份错误对象不得删除")

        let activeID = "55555555-5555-4555-8555-555555555555"
        let active = try makeLegacy(transactions, id: activeID, driver: driver)
        try Data("{}".utf8).write(to: active.appendingPathComponent("transaction.json"))
        cleanup = HistoricalCleanup.clean(transactionRoot: transactions)
        check(cleanup.status == .blocked, "活动或异常事务必须阻止清理")
        check(fm.fileExists(atPath: active.path), "活动事务目录不得删除")

        print("历史材料身份核验、部分失败重试和保护测试通过")
    }

    static func makeLegacy(_ root: URL, id: String, driver: URL) throws -> URL {
        let directory = root.appendingPathComponent(id)
        try fm.createDirectory(at: directory, withIntermediateDirectories: true)
        try fm.copyItem(at: driver, to: directory.appendingPathComponent("backup.driver"))
        let state: [String: Any] = [
            "target": "/Library/Audio/Plug-Ins/HAL/TapSayAudio.driver",
            "bundle_identifier": "com.leafney.tapsay.audio.driver",
            "device_uid": "com.leafney.tapsay.audio.device.2ch",
        ]
        let data = try JSONSerialization.data(withJSONObject: state)
        try data.write(to: directory.appendingPathComponent("previous-state.json"))
        return directory
    }
}
