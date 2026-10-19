// In-memory PCM loopback check for the installed TapSay Audio device.
import AudioToolbox
import CoreAudio
import Foundation

struct LoopbackError: Error, CustomStringConvertible {
    let description: String
}

struct ChannelStats {
    var sumSquares = 0.0
    var peak = 0.0
    var sine = 0.0
    var cosine = 0.0
    var invalidSamples = 0

    mutating func capture(_ sample: Float, phase: Double) {
        let value = Double(sample)
        guard value.isFinite else {
            invalidSamples += 1
            return
        }
        sumSquares += value * value
        peak = max(peak, abs(value))
        sine += value * sin(phase)
        cosine += value * cos(phase)
    }

    func rms(frames: UInt64) -> Double {
        frames > 0 ? sqrt(sumSquares / Double(frames)) : 0
    }

    func toneFraction(frames: UInt64) -> Double {
        guard frames > 0, sumSquares > 0 else { return 0 }
        return 2 * (sine * sine + cosine * cosine) / (Double(frames) * sumSquares)
    }
}

final class LoopbackContext {
    let rate: Double
    let frequencies = [1000.0, 1500.0]
    let lock = NSLock()
    var phase = 0.0
    var capturedFrames: UInt64 = 0
    var channels = [ChannelStats(), ChannelStats()]
    var callbackStatus: OSStatus = noErr

    init(rate: Double) { self.rate = rate }

    func render(_ buffer: AudioQueueBufferRef) {
        let frameBytes = UInt32(2 * MemoryLayout<Float>.size)
        let frames = Int(buffer.pointee.mAudioDataBytesCapacity / frameBytes)
        let samples = buffer.pointee.mAudioData.assumingMemoryBound(to: Float.self)
        for frame in 0..<frames {
            for channel in 0..<2 {
                samples[frame * 2 + channel] = Float(0.25 * sin(2 * .pi * frequencies[channel] * phase / rate))
            }
            phase += 1
            if phase >= rate { phase -= rate }
        }
        buffer.pointee.mAudioDataByteSize = UInt32(frames) * frameBytes
    }

    func capture(_ buffer: AudioQueueBufferRef) {
        let count = Int(buffer.pointee.mAudioDataByteSize) / MemoryLayout<Float>.size
        let samples = buffer.pointee.mAudioData.assumingMemoryBound(to: Float.self)
        lock.lock()
        for frame in 0..<(count / 2) {
            let time = Double(capturedFrames + UInt64(frame)) / rate
            for channel in 0..<2 {
                channels[channel].capture(
                    samples[frame * 2 + channel],
                    phase: 2 * .pi * frequencies[channel] * time
                )
            }
        }
        capturedFrames += UInt64(count / 2)
        lock.unlock()
    }

    func enqueue(_ queue: AudioQueueRef, _ buffer: AudioQueueBufferRef) {
        let status = AudioQueueEnqueueBuffer(queue, buffer, 0, nil)
        if status != noErr {
            lock.lock()
            callbackStatus = status
            lock.unlock()
        }
    }
}

let outputCallback: AudioQueueOutputCallback = { userData, queue, buffer in
    guard let userData else { return }
    let context = Unmanaged<LoopbackContext>.fromOpaque(userData).takeUnretainedValue()
    context.render(buffer)
    context.enqueue(queue, buffer)
}

let inputCallback: AudioQueueInputCallback = { userData, queue, buffer, _, _, _ in
    guard let userData else { return }
    let context = Unmanaged<LoopbackContext>.fromOpaque(userData).takeUnretainedValue()
    context.capture(buffer)
    context.enqueue(queue, buffer)
}

func fail(_ message: String) throws -> Never {
    throw LoopbackError(description: message)
}

func check(_ status: OSStatus, _ operation: String) throws {
    guard status == noErr else { throw LoopbackError(description: "\(operation)，音频状态 \(status)") }
}

func installedDevice(uid: String) throws -> AudioDeviceID {
    var address = AudioObjectPropertyAddress(
        mSelector: kAudioHardwarePropertyDevices,
        mScope: kAudioObjectPropertyScopeGlobal,
        mElement: kAudioObjectPropertyElementMain
    )
    let system = AudioObjectID(kAudioObjectSystemObject)
    var size: UInt32 = 0
    try check(AudioObjectGetPropertyDataSize(system, &address, 0, nil, &size), "读取设备列表大小")
    var devices = [AudioDeviceID](repeating: 0, count: Int(size) / MemoryLayout<AudioDeviceID>.size)
    try check(AudioObjectGetPropertyData(system, &address, 0, nil, &size, &devices), "读取设备列表")
    address.mSelector = kAudioDevicePropertyDeviceUID
    for device in devices {
        var value: CFString?
        size = UInt32(MemoryLayout<CFString?>.size)
        let status = withUnsafeMutablePointer(to: &value) {
            AudioObjectGetPropertyData(device, &address, 0, nil, &size, $0)
        }
        if status == noErr,
           value as String? == uid {
            return device
        }
    }
    try fail("CoreAudio 未枚举 TapSay Audio UID")
}

func nominalRate(_ device: AudioDeviceID) throws -> Double {
    var address = AudioObjectPropertyAddress(
        mSelector: kAudioDevicePropertyNominalSampleRate,
        mScope: kAudioObjectPropertyScopeGlobal,
        mElement: kAudioObjectPropertyElementMain
    )
    var rate: Float64 = 0
    var size = UInt32(MemoryLayout<Float64>.size)
    try check(AudioObjectGetPropertyData(device, &address, 0, nil, &size, &rate), "读取设备实际采样率")
    return rate
}

func setRate(_ device: AudioDeviceID, _ rate: Double) throws {
    var address = AudioObjectPropertyAddress(
        mSelector: kAudioDevicePropertyNominalSampleRate,
        mScope: kAudioObjectPropertyScopeGlobal,
        mElement: kAudioObjectPropertyElementMain
    )
    var value = rate
    try check(AudioObjectSetPropertyData(device, &address, 0, nil, UInt32(MemoryLayout<Float64>.size), &value), "切换设备实际采样率")
    let deadline = Date().addingTimeInterval(3)
    repeat {
        if try nominalRate(device) == rate { return }
        Thread.sleep(forTimeInterval: 0.02)
    } while Date() < deadline
    try fail("设备实际采样率未切换至 \(Int(rate)) Hz")
}

func verifyStreamFormats(_ device: AudioDeviceID, rate: Double) throws {
    for scope in [kAudioDevicePropertyScopeInput, kAudioDevicePropertyScopeOutput] {
        var address = AudioObjectPropertyAddress(
            mSelector: kAudioDevicePropertyStreams,
            mScope: scope,
            mElement: kAudioObjectPropertyElementMain
        )
        var size: UInt32 = 0
        try check(AudioObjectGetPropertyDataSize(device, &address, 0, nil, &size), "读取流列表大小")
        guard size == MemoryLayout<AudioStreamID>.size else { try fail("目标方向不是单个音频流") }
        var stream: AudioStreamID = 0
        try check(AudioObjectGetPropertyData(device, &address, 0, nil, &size, &stream), "读取音频流")
        for selector in [kAudioStreamPropertyVirtualFormat, kAudioStreamPropertyPhysicalFormat] {
            address.mSelector = selector
            address.mScope = kAudioObjectPropertyScopeGlobal
            var format = AudioStreamBasicDescription()
            size = UInt32(MemoryLayout<AudioStreamBasicDescription>.size)
            try check(AudioObjectGetPropertyData(stream, &address, 0, nil, &size, &format), "读取实际流格式")
            guard format.mSampleRate == rate, format.mFormatID == kAudioFormatLinearPCM,
                  format.mChannelsPerFrame == 2, format.mBitsPerChannel == 32,
                  format.mBytesPerFrame == 8, format.mFramesPerPacket == 1,
                  format.mFormatFlags & kAudioFormatFlagIsFloat != 0,
                  format.mFormatFlags & kAudioFormatFlagIsNonInterleaved == 0 else {
                try fail("输入或输出流不是目标采样率的双声道 Float32 PCM")
            }
        }
    }
    print("输入/输出流的虚拟与物理格式：\(Int(rate)) Hz、双声道 Float32 PCM")
}

func selectDevice(_ queue: AudioQueueRef, uid: String) throws {
    var deviceUID = uid as CFString
    let status = withUnsafePointer(to: &deviceUID) {
        AudioQueueSetProperty(
            queue,
            kAudioQueueProperty_CurrentDevice,
            $0,
            UInt32(MemoryLayout<CFString>.size)
        )
    }
    try check(status, "选择 TapSay Audio 设备")
    var actualUID: CFString?
    var size = UInt32(MemoryLayout<CFString?>.size)
    let readStatus = withUnsafeMutablePointer(to: &actualUID) {
        AudioQueueGetProperty(queue, kAudioQueueProperty_CurrentDevice, $0, &size)
    }
    try check(readStatus, "回读队列设备")
    guard actualUID as String? == uid else { try fail("音频队列未绑定目标 UID") }
}

func makeFormat(rate: Double) -> AudioStreamBasicDescription {
    AudioStreamBasicDescription(
        mSampleRate: rate,
        mFormatID: kAudioFormatLinearPCM,
        mFormatFlags: kAudioFormatFlagIsFloat | kAudioFormatFlagIsPacked | kAudioFormatFlagsNativeEndian,
        mBytesPerPacket: 8,
        mFramesPerPacket: 1,
        mBytesPerFrame: 8,
        mChannelsPerFrame: 2,
        mBitsPerChannel: 32,
        mReserved: 0
    )
}

func main() throws {
    let args = Array(CommandLine.arguments.dropFirst())
    guard args.count <= 2,
          let rate = Double(args.first ?? "16000"),
          [16000.0, 44100.0, 48000.0].contains(rate) else {
        try fail("用法：TapSayAudioLoopback [16000|44100|48000] [1 到 30 秒]")
    }
    guard let duration = Double(args.dropFirst().first ?? "3"), duration >= 1 && duration <= 30 else {
        try fail("时长只接受 1 到 30 秒")
    }

    let uid = "com.leafney.tapsay.audio.device.2ch"
    let device = try installedDevice(uid: uid)
    let originalRate = try nominalRate(device)
    // Restore after queue disposal, including failures during setup or capture.
    defer {
        if (try? nominalRate(device)) != originalRate {
            do { try setRate(device, originalRate) }
            catch { fputs("警告：恢复原采样率失败：\(error)\n", stderr) }
        }
    }
    try setRate(device, rate)
    let context = LoopbackContext(rate: rate)
    let retainedContext = Unmanaged.passRetained(context)
    defer { retainedContext.release() }
    let userData = retainedContext.toOpaque()
    var format = makeFormat(rate: rate)
    var output: AudioQueueRef?
    var input: AudioQueueRef?

    try check(AudioQueueNewOutput(&format, outputCallback, userData, nil, nil, 0, &output), "创建输出队列")
    guard let output else { try fail("创建输出队列后未返回句柄") }
    defer { AudioQueueDispose(output, true) }
    try check(AudioQueueNewInput(&format, inputCallback, userData, nil, nil, 0, &input), "创建输入队列")
    guard let input else { try fail("创建输入队列后未返回句柄") }
    defer {
        AudioQueueStop(input, true)
        AudioQueueStop(output, true)
        AudioQueueDispose(input, true)
    }

    try selectDevice(output, uid: uid)
    try selectDevice(input, uid: uid)
    let bytes = UInt32(1024 * format.mBytesPerFrame)
    for _ in 0..<3 {
        var buffer: AudioQueueBufferRef?
        try check(AudioQueueAllocateBuffer(output, bytes, &buffer), "分配输出缓冲")
        guard let buffer else { try fail("输出缓冲为空") }
        context.render(buffer)
        try check(AudioQueueEnqueueBuffer(output, buffer, 0, nil), "排入输出缓冲")
    }
    for _ in 0..<3 {
        var buffer: AudioQueueBufferRef?
        try check(AudioQueueAllocateBuffer(input, bytes, &buffer), "分配输入缓冲")
        guard let buffer else { try fail("输入缓冲为空") }
        try check(AudioQueueEnqueueBuffer(input, buffer, 0, nil), "排入输入缓冲")
    }

    try check(AudioQueueStart(input, nil), "启动输入队列")
    try check(AudioQueueStart(output, nil), "启动输出队列")
    Thread.sleep(forTimeInterval: duration)

    context.lock.lock()
    let frames = context.capturedFrames
    let channels = context.channels
    let callbackStatus = context.callbackStatus
    context.lock.unlock()

    try check(callbackStatus, "音频回调重新排入缓冲")
    let actualRate = try nominalRate(device)
    try verifyStreamFormats(device, rate: rate)
    try check(AudioQueueStop(input, true), "停止输入队列")
    try check(AudioQueueStop(output, true), "停止输出队列")
    // Restore explicitly on success so a restoration failure is a failed run.
    try setRate(device, originalRate)
    print("设备 UID：\(uid)")
    print("请求/设备实际采样率：\(Int(rate))/\(Int(actualRate)) Hz；时长：\(duration) 秒；采集帧数：\(frames)")
    for channel in 0..<2 {
        let stats = channels[channel]
        print("声道 \(channel + 1)：\(Int(context.frequencies[channel])) Hz；RMS：\(String(format: "%.5f", stats.rms(frames: frames)))；峰值：\(String(format: "%.5f", stats.peak))；目标频率能量比例：\(String(format: "%.5f", stats.toneFraction(frames: frames)))")
    }
    guard actualRate == rate,
          abs(Double(frames) / rate - duration) < 0.5,
          channels.allSatisfy({
              $0.invalidSamples == 0 && $0.rms(frames: frames) > 0.12 &&
              abs($0.peak - 0.25) < 0.04 && $0.toneFraction(frames: frames) > 0.8
          }) else {
        try fail("PCM 帧数、幅度、频率或声道映射不符合合成测试信号")
    }
    print("已恢复原采样率：\(Int(try nominalRate(device))) Hz")
    print("PCM 回环通过；未保存音频样本")
}

do { try main() }
catch {
    fputs("回环检查失败：\(error)\n", stderr)
    exit(1)
}
