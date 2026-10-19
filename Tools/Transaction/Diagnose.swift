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

struct AcceptanceError: Error, CustomStringConvertible {
    let description: String
}

func readProperty<T>(_ id: AudioObjectID, _ selector: AudioObjectPropertySelector, _ scope: AudioObjectPropertyScope, as type: T.Type) -> T? {
    var address = AudioObjectPropertyAddress(
        mSelector: selector,
        mScope: scope,
        mElement: kAudioObjectPropertyElementMain
    )
    // CoreAudio writes T, not Optional<T>; scalar optionals have extra tag bytes.
    let value = UnsafeMutablePointer<T>.allocate(capacity: 1)
    defer { value.deallocate() }
    var size = UInt32(MemoryLayout<T>.size)
    let status = AudioObjectGetPropertyData(id, &address, 0, nil, &size, value)
    return status == noErr && size == MemoryLayout<T>.size ? value.pointee : nil
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

func verifyControls(_ device: AudioDeviceID) throws {
    let system = AudioObjectID(kAudioObjectSystemObject)
    let routes = [kAudioHardwarePropertyDefaultInputDevice, kAudioHardwarePropertyDefaultOutputDevice, kAudioHardwarePropertyDefaultSystemOutputDevice]
    let originalRoutes = routes.map { readProperty(system, $0, kAudioObjectPropertyScopeGlobal, as: AudioDeviceID.self) }
    guard originalRoutes.allSatisfy({ $0 != nil }) else {
        throw AcceptanceError(description: "无法读取系统默认路由")
    }
    for scope in [kAudioDevicePropertyScopeInput, kAudioDevicePropertyScopeOutput] {
        let label = scope == kAudioDevicePropertyScopeInput ? "输入" : "输出"
        try verifyControl(device, kAudioDevicePropertyMute, scope, initial: UInt32(0), probe: UInt32(1), label: "\(label)静音")
        try verifyControl(device, kAudioDevicePropertyVolumeScalar, scope, initial: Float32(1), probe: Float32(0.5), label: "\(label)音量")
    }
    guard routes.map({ readProperty(system, $0, kAudioObjectPropertyScopeGlobal, as: AudioDeviceID.self) }) == originalRoutes else {
        throw AcceptanceError(description: "验证前后系统默认路由不同；本工具未设置默认路由")
    }
    print("输入、输出、提示音默认路由保持不变")
}

func verifyControl<T: Equatable>(_ device: AudioDeviceID, _ selector: AudioObjectPropertySelector, _ scope: AudioObjectPropertyScope, initial: T, probe: T, label: String) throws {
    var address = AudioObjectPropertyAddress(mSelector: selector, mScope: scope, mElement: kAudioObjectPropertyElementMain)
    var settable: DarwinBoolean = false
    guard AudioObjectIsPropertySettable(device, &address, &settable) == noErr, settable.boolValue,
          let original = readProperty(device, selector, scope, as: T.self) else {
        throw AcceptanceError(description: "\(label)不可读写")
    }
    func write(_ value: T) throws {
        var value = value
        let status = withUnsafePointer(to: &value) {
            AudioObjectSetPropertyData(device, &address, 0, nil, UInt32(MemoryLayout<T>.size), $0)
        }
        guard status == noErr, readProperty(device, selector, scope, as: T.self) == value else {
            throw AcceptanceError(description: "\(label)写入或回读失败，状态 \(status)")
        }
    }
    defer {
        if readProperty(device, selector, scope, as: T.self) != original {
            do { try write(original) }
            catch { fputs("警告：恢复\(label)失败：\(error)\n", stderr) }
        }
    }
    try write(probe)
    try write(original)
    print("\(label)：初值 \(original)；合同默认值 \(initial)；写入 \(probe) 并回读通过；已恢复 \(original)")
}

func main() throws {
    let args = Array(CommandLine.arguments.dropFirst())
    guard args.isEmpty || args == ["--verify-controls"] else {
        throw AcceptanceError(description: "用法：TapSayAudioDiagnose [--verify-controls]")
    }
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
    guard let index = reports.firstIndex(where: { $0.uid == expectedUID }) else {
        fputs("检查失败：CoreAudio 未枚举 TapSay Audio UID\n", stderr)
        exit(2)
    }
    let device = reports[index]
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
    if !args.isEmpty { try verifyControls(devices[index]) }
}

do { try main() }
catch {
    fputs("诊断失败：\(error)\n", stderr)
    exit(1)
}
