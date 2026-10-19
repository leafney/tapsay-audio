// SPDX-License-Identifier: GPL-3.0-only
import Foundation

@main struct TransactionRecordTests {
    static func check(_ condition: Bool, _ message: String) {
        if !condition { fatalError(message) }
    }

    static func main() throws {
        let id = "11111111-2222-3333-4444-555555555555"
        let target = "/Library/Audio/Plug-Ins/HAL/TapSayAudio.driver"
        let state = "/Library/Application Support/TapSay Audio/install-state.json"
        let record = TransactionRecord(
            transactionID: id, deviceUID: "com.leafney.tapsay.audio.device.2ch",
            bundleIdentifier: "com.leafney.tapsay.audio.driver",
            receipt: "com.leafney.tapsay.audio.pkg", target: target, state: state,
            previous: "/Library/Audio/Plug-Ins/HAL/.TapSayAudio-\(id).previous",
            staged: "/Library/Audio/Plug-Ins/HAL/.TapSayAudio-\(id).driver",
            previousState: "/Library/Application Support/TapSay Audio/transactions/\(id)/previous-state.json",
            hadTarget: true
        )
        let encoded = try JSONEncoder().encode(record)
        let object = try JSONSerialization.jsonObject(with: encoded) as! [String: Any]
        var invalid: [Data] = [Data(), Data("{}".utf8)]
        for key in object.keys {
            var changed = object
            changed.removeValue(forKey: key)
            invalid.append(try JSONSerialization.data(withJSONObject: changed))
        }
        for (key, value) in [
            ("schema_version", 2 as Any),
            ("transaction_id", "not-a-uuid" as Any),
            ("device_uid", "other" as Any),
            ("target", "/tmp/TapSayAudio.driver" as Any),
            ("previous", "/tmp/previous" as Any),
            ("phase", "unknown" as Any),
            ("terminal_result", "deployed" as Any),
            ("cleanup", "partial" as Any),
        ] {
            var changed = object
            changed[key] = value
            invalid.append(try JSONSerialization.data(withJSONObject: changed))
        }
        var unknown = object
        unknown["unexpected"] = true
        invalid.append(try JSONSerialization.data(withJSONObject: unknown))

        for data in invalid {
            do {
                _ = try JSONDecoder().decode(TransactionRecord.self, from: data)
                fatalError("无效事务记录必须拒绝")
            } catch {}
        }
        print("事务记录严格解码测试通过")
    }
}
