// Read-only CoreAudio inspection for installed-device acceptance.
import CoreAudio
import Foundation

struct DeviceReport: Codable {
    var name: String?
    var uid: String?
    var transport: String?
    var inputStreamCount: Int
    var outputStreamCount: Int
    var nominalRate: Double?
    var availableRates: [Double]
}

func readProperty<T>(_ id: AudioObjectID, _ selector: AudioObjectPropertySelector, _ scope: AudioObjectPropertyScope, as type: T.Type) -> T? {
    var address = AudioObjectPropertyAddress(
        mSelector: selector,
        mScope: scope,
        mElement: kAudioObjectPropertyElementMain
    )
    var value: T?
    var size = UInt32(MemoryLayout<T>.size)
    let status = withUnsafeMutablePointer(to: &value) { pointer in
        AudioObjectGetPropertyData(id, &address, 0, nil, &size, pointer)
    }
    return status == noErr ? value : nil
}

func streamCount(_ id: AudioObjectID, _ scope: AudioObjectPropertyScope) -> Int {
    var address = AudioObjectPropertyAddress(
        mSelector: kAudioDevicePropertyStreams,
        mScope: scope,
        mElement: kAudioObjectPropertyElementMain
    )
    var size: UInt32 = 0
    guard AudioObjectGetPropertyDataSize(id, &address, 0, nil, &size) == noErr else { return 0 }
    return Int(size) / MemoryLayout<AudioStreamID>.size
}

func availableRates(_ id: AudioObjectID) -> [Double] {
    var address = AudioObjectPropertyAddress(
        mSelector: kAudioDevicePropertyAvailableNominalSampleRates,
        mScope: kAudioObjectPropertyScopeGlobal,
        mElement: kAudioObjectPropertyElementMain
    )
    var size: UInt32 = 0
    guard AudioObjectGetPropertyDataSize(id, &address, 0, nil, &size) == noErr,
          size > 0 else { return [] }
    var ranges = [AudioValueRange](repeating: AudioValueRange(mMinimum: 0, mMaximum: 0), count: Int(size) / MemoryLayout<AudioValueRange>.size)
    guard AudioObjectGetPropertyData(id, &address, 0, nil, &size, &ranges) == noErr else { return [] }
    return ranges.filter { $0.mMinimum == $0.mMaximum }.map(\.mMinimum)
}

func main() throws {
    let expectedUID = "com.leafney.tapsay.audio.device.2ch"
    var address = AudioObjectPropertyAddress(
        mSelector: kAudioHardwarePropertyDevices,
        mScope: kAudioObjectPropertyScopeGlobal,
        mElement: kAudioObjectPropertyElementMain
    )
    var size: UInt32 = 0
    let system = AudioObjectID(kAudioObjectSystemObject)
    guard AudioObjectGetPropertyDataSize(system, &address, 0, nil, &size) == noErr else {
        throw NSError(domain: NSOSStatusErrorDomain, code: -1, userInfo: [NSLocalizedDescriptionKey: "无法读取 CoreAudio 设备列表"])
    }
    var devices = [AudioDeviceID](repeating: 0, count: Int(size) / MemoryLayout<AudioDeviceID>.size)
    guard AudioObjectGetPropertyData(system, &address, 0, nil, &size, &devices) == noErr else {
        throw NSError(domain: NSOSStatusErrorDomain, code: -2, userInfo: [NSLocalizedDescriptionKey: "无法取得 CoreAudio 设备"])
    }
    var reports: [DeviceReport] = []
    for id in devices {
        let uid: String? = readProperty(id, kAudioDevicePropertyDeviceUID, kAudioObjectPropertyScopeGlobal, as: CFString.self).map { $0 as String }
        let name: String? = readProperty(id, kAudioObjectPropertyName, kAudioObjectPropertyScopeGlobal, as: CFString.self).map { $0 as String }
        let rawTransport: UInt32? = readProperty(id, kAudioDevicePropertyTransportType, kAudioObjectPropertyScopeGlobal, as: UInt32.self)
        let transport: String? = rawTransport.map { String(format: "0x%08x", $0) }
        let rate: Float64? = readProperty(id, kAudioDevicePropertyNominalSampleRate, kAudioObjectPropertyScopeGlobal, as: Float64.self)
        reports.append(DeviceReport(
            name: name,
            uid: uid,
            transport: transport,
            inputStreamCount: streamCount(id, kAudioDevicePropertyScopeInput),
            outputStreamCount: streamCount(id, kAudioDevicePropertyScopeOutput),
            nominalRate: rate,
            availableRates: availableRates(id)
        ))
    }
    let output = try JSONEncoder().encode(reports)
    FileHandle.standardOutput.write(output)
    FileHandle.standardOutput.write(Data([0x0a]))
    guard let device = reports.first(where: { $0.uid == expectedUID }) else {
        fputs("检查失败：CoreAudio 未枚举 TapSay Audio UID\n", stderr)
        exit(2)
    }
    guard device.name == "TapSay Audio 2ch",
          device.transport == String(format: "0x%08x", kAudioDeviceTransportTypeUSB),
          device.inputStreamCount == 1,
          device.outputStreamCount == 1,
          device.availableRates.contains(16000),
          device.availableRates.contains(44100),
          device.availableRates.contains(48000) else {
        fputs("检查失败：TapSay Audio 设备名称、流数量或采样率不符合合同\n", stderr)
        exit(3)
    }
    print("设备已枚举；音频数据链路尚未验证")
}

do { try main() }
catch {
    fputs("诊断失败：\(error)\n", stderr)
    exit(1)
}
