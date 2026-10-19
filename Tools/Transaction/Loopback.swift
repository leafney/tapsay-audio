// In-memory PCM loopback check for the installed TapSay Audio device.
import AudioToolbox
import CoreAudio
import Foundation

final class LoopbackContext {
    let rate: Double
    let lock = NSLock()
    var phase = 0.0
    var capturedFrames: UInt64 = 0
    var sumSquares = 0.0
    var peak = 0.0

    init(rate: Double) { self.rate = rate }

    func render(_ buffer: AudioQueueBufferRef) {
        let frameBytes = UInt32(2 * MemoryLayout<Float>.size)
        let frames = Int(buffer.pointee.mAudioDataBytesCapacity / frameBytes)
        let samples = buffer.pointee.mAudioData.assumingMemoryBound(to: Float.self)
        for frame in 0..<frames {
            let value = Float(0.25 * sin(2.0 * .pi * 1000.0 * phase / rate))
            samples[frame * 2] = value
            samples[frame * 2 + 1] = value
            phase += 1
            if phase >= rate { phase -= rate }
        }
        buffer.pointee.mAudioDataByteSize = UInt32(frames) * frameBytes
    }

    func capture(_ buffer: AudioQueueBufferRef) {
        let count = Int(buffer.pointee.mAudioDataByteSize) / MemoryLayout<Float>.size
        let samples = buffer.pointee.mAudioData.assumingMemoryBound(to: Float.self)
        lock.lock()
        for index in 0..<count {
            let value = Double(samples[index])
            sumSquares += value * value
            peak = max(peak, abs(value))
        }
        capturedFrames += UInt64(count / 2)
        lock.unlock()
    }
}

let outputCallback: AudioQueueOutputCallback = { userData, queue, buffer in
    guard let userData else { return }
    let context = Unmanaged<LoopbackContext>.fromOpaque(userData).takeUnretainedValue()
    context.render(buffer)
    _ = AudioQueueEnqueueBuffer(queue, buffer, 0, nil)
}

let inputCallback: AudioQueueInputCallback = { userData, queue, buffer, _, _, _ in
    guard let userData else { return }
    let context = Unmanaged<LoopbackContext>.fromOpaque(userData).takeUnretainedValue()
    context.capture(buffer)
    _ = AudioQueueEnqueueBuffer(queue, buffer, 0, nil)
}

func fail(_ message: String, _ status: OSStatus? = nil) -> Never {
    if let status {
        fputs("回环检查失败：\(message)，AudioQueue 状态 \(status)\n", stderr)
    } else {
        fputs("回环检查失败：\(message)\n", stderr)
    }
    exit(1)
}

func check(_ status: OSStatus, _ operation: String) {
    guard status == noErr else { fail(operation, status) }
}

func selectDevice(_ queue: AudioQueueRef, uid: String) {
    var deviceUID = uid as CFString
    let status = withUnsafePointer(to: &deviceUID) {
        AudioQueueSetProperty(
            queue,
            kAudioQueueProperty_CurrentDevice,
            $0,
            UInt32(MemoryLayout<CFString>.size)
        )
    }
    check(status, "选择 TapSay Audio 设备")
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
    let rate = args.first.flatMap(Double.init) ?? 16000
    let duration = args.dropFirst().first.flatMap(Double.init) ?? 3
    guard [16000.0, 44100.0, 48000.0].contains(rate) else {
        fail("采样率只接受 16000、44100 或 48000")
    }
    guard duration >= 1 && duration <= 30 else { fail("时长只接受 1 到 30 秒") }

    let uid = "com.leafney.tapsay.audio.device.2ch"
    let context = LoopbackContext(rate: rate)
    let userData = Unmanaged.passUnretained(context).toOpaque()
    var format = makeFormat(rate: rate)
    var output: AudioQueueRef?
    var input: AudioQueueRef?

    check(AudioQueueNewOutput(&format, outputCallback, userData, nil, nil, 0, &output), "创建输出队列")
    guard let output else { fail("创建输出队列后未返回句柄") }
    check(AudioQueueNewInput(&format, inputCallback, userData, nil, nil, 0, &input), "创建输入队列")
    guard let input else {
        AudioQueueDispose(output, true)
        fail("创建输入队列后未返回句柄")
    }
    defer {
        AudioQueueStop(input, true)
        AudioQueueStop(output, true)
        AudioQueueDispose(input, true)
        AudioQueueDispose(output, true)
    }

    selectDevice(output, uid: uid)
    selectDevice(input, uid: uid)
    let bytes = UInt32(1024 * format.mBytesPerFrame)
    var outputBuffers: [AudioQueueBufferRef] = []
    for _ in 0..<3 {
        var buffer: AudioQueueBufferRef?
        check(AudioQueueAllocateBuffer(output, bytes, &buffer), "分配输出缓冲")
        guard let buffer else { fail("输出缓冲为空") }
        context.render(buffer)
        check(AudioQueueEnqueueBuffer(output, buffer, 0, nil), "排入输出缓冲")
        outputBuffers.append(buffer)
    }
    for _ in 0..<3 {
        var buffer: AudioQueueBufferRef?
        check(AudioQueueAllocateBuffer(input, bytes, &buffer), "分配输入缓冲")
        guard let buffer else { fail("输入缓冲为空") }
        check(AudioQueueEnqueueBuffer(input, buffer, 0, nil), "排入输入缓冲")
    }

    check(AudioQueueStart(input, nil), "启动输入队列")
    check(AudioQueueStart(output, nil), "启动输出队列")
    Thread.sleep(forTimeInterval: duration)

    context.lock.lock()
    let frames = context.capturedFrames
    let samples = Double(frames * 2)
    let rms = samples > 0 ? sqrt(context.sumSquares / samples) : 0
    let peak = context.peak
    context.lock.unlock()

    print("设备 UID：\(uid)")
    print("采样率：\(Int(rate)) Hz；时长：\(duration) 秒")
    print("采集帧数：\(frames)；RMS：\(String(format: "%.5f", rms))；峰值：\(String(format: "%.5f", peak))")
    guard frames > UInt64(rate), rms > 0.01, peak < 0.99 else {
        fail("未收到有效回环 PCM；检查安装、设备格式、静音和音量")
    }
    print("PCM 回环通过；未保存音频样本")
}

do { try main() }
catch { fail(String(describing: error)) }
