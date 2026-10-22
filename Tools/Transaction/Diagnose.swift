// SPDX-License-Identifier: GPL-3.0-only
// Read-only inspection: never writes CoreAudio properties or starts audio IO.
import CoreAudio
import CryptoKit
import Foundation

func readProperty<T>(_ id: AudioObjectID, _ selector: AudioObjectPropertySelector,
                     _ scope: AudioObjectPropertyScope = kAudioObjectPropertyScopeGlobal,
                     as type: T.Type) -> T? {
    var address = AudioObjectPropertyAddress(mSelector: selector, mScope: scope,
                                            mElement: kAudioObjectPropertyElementMain)
    let value = UnsafeMutablePointer<T>.allocate(capacity: 1)
    defer { value.deallocate() }
    var size = UInt32(MemoryLayout<T>.size)
    let status = AudioObjectGetPropertyData(id, &address, 0, nil, &size, value)
    return status == noErr && size == MemoryLayout<T>.size ? value.pointee : nil
}

func ids(_ id: AudioObjectID, _ selector: AudioObjectPropertySelector,
         _ scope: AudioObjectPropertyScope = kAudioObjectPropertyScopeGlobal) -> [AudioObjectID]? {
    var address = AudioObjectPropertyAddress(mSelector: selector, mScope: scope,
                                            mElement: kAudioObjectPropertyElementMain)
    var size: UInt32 = 0
    guard AudioObjectGetPropertyDataSize(id, &address, 0, nil, &size) == noErr,
          size % 4 == 0 else { return nil }
    if size == 0 { return [] }
    let capacity = size
    var result = [AudioObjectID](repeating: 0, count: Int(size) / 4)
    let status = result.withUnsafeMutableBytes {
        AudioObjectGetPropertyData(id, &address, 0, nil, &size, $0.baseAddress!)
    }
    guard status == noErr, size <= capacity, size % 4 == 0 else { return nil }
    return Array(result.prefix(Int(size) / 4))
}

func format(_ value: AudioStreamBasicDescription?) -> Any {
    guard let v = value else { return NSNull() }
    return ["sample_rate_hz": v.mSampleRate, "format_id": v.mFormatID,
            "format_flags": v.mFormatFlags, "bytes_per_packet": v.mBytesPerPacket,
            "frames_per_packet": v.mFramesPerPacket, "bytes_per_frame": v.mBytesPerFrame,
            "channels_per_frame": v.mChannelsPerFrame, "bits_per_channel": v.mBitsPerChannel] as [String: Any]
}

func streams(_ id: AudioDeviceID, _ scope: AudioObjectPropertyScope) -> Any {
    guard let streams = ids(id, kAudioDevicePropertyStreams, scope) else { return NSNull() }
    return streams.map { stream in
        ["stream_id": stream,
         "physical_format": format(readProperty(stream, kAudioStreamPropertyPhysicalFormat, as: AudioStreamBasicDescription.self)),
         "virtual_format": format(readProperty(stream, kAudioStreamPropertyVirtualFormat, as: AudioStreamBasicDescription.self))] as [String: Any]
    }
}

func main() throws {
    guard CommandLine.arguments.count == 1 else {
        throw NSError(domain: "TapSayAudioDiagnose", code: 1,
                      userInfo: [NSLocalizedDescriptionKey: "用法：TapSayAudioDiagnose；只读诊断不支持控制写入参数"])
    }
    let expectedUID = "com.leafney.tapsay.audio.device.2ch"
    let devices = ids(AudioObjectID(kAudioObjectSystemObject), kAudioHardwarePropertyDevices)
    var unreadableUID = false
    var reports = [[String: Any]]()
    for id in devices ?? [] {
        guard let uid = readProperty(id, kAudioDevicePropertyDeviceUID, as: CFString.self) else {
            unreadableUID = true
            continue
        }
        guard uid as String == expectedUID else { continue }
        let name = readProperty(id, kAudioObjectPropertyName, as: CFString.self)
        let rate = readProperty(id, kAudioDevicePropertyNominalSampleRate, as: Float64.self)
        reports.append(["device_id": id, "uid": uid as String,
                        "name": name.map { $0 as String } as Any? ?? NSNull(),
                        "nominal_rate_hz": rate as Any? ?? NSNull(),
                        "input_streams": streams(id, kAudioDevicePropertyScopeInput),
                        "output_streams": streams(id, kAudioDevicePropertyScopeOutput)])
    }
    let bundle = URL(fileURLWithPath: "/Library/Audio/Plug-Ins/HAL/TapSayAudio.driver")
    let plistData = try? Data(contentsOf: bundle.appendingPathComponent("Contents/Info.plist"))
    let info = plistData.flatMap { try? PropertyListSerialization.propertyList(from: $0, format: nil) as? [String: Any] }
    let binary = try? Data(contentsOf: bundle.appendingPathComponent("Contents/MacOS/TapSayAudio"))
    let report: [String: Any] = [
        "schema_version": 1,
        "generated_at": ISO8601DateFormatter().string(from: Date()),
        "system_version": ProcessInfo.processInfo.operatingSystemVersionString,
        "expected_device_uid": expectedUID,
        "device_status": !reports.isEmpty ? "present" : (devices == nil || unreadableUID ? "unavailable" : "absent"),
        "devices": reports,
        "disk_driver": ["path": bundle.path,
                        "version": info?["CFBundleShortVersionString"] ?? NSNull(),
                        "build_number": info?["CFBundleVersion"] ?? NSNull(),
                        "sha256": binary.map { SHA256.hash(data: $0).map { String(format: "%02x", $0) }.joined() } as Any? ?? NSNull()],
        "audio_chain_status": "not_run",
        "loaded_instance_status": "unverified",
        "limitations": "只读快照；null 表示读取失败或文件不存在。磁盘版本和散列不能证明系统已加载同一驱动实例；设备出现不代表真实音频链路通过。"
    ]
    FileHandle.standardOutput.write(try JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys]))
    FileHandle.standardOutput.write(Data([10]))
}

do { try main() }
catch {
    fputs("诊断失败：\(error.localizedDescription)\n", stderr)
    exit(1)
}
