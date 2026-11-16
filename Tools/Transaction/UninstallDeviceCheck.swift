// SPDX-License-Identifier: GPL-3.0-only
import CoreAudio
import Foundation

func uninstallDeviceStatus() -> UninstallDeviceStatus {
    var address = AudioObjectPropertyAddress(mSelector: kAudioHardwarePropertyDevices,
                                            mScope: kAudioObjectPropertyScopeGlobal,
                                            mElement: kAudioObjectPropertyElementMain)
    let system = AudioObjectID(kAudioObjectSystemObject)
    var size: UInt32 = 0
    guard AudioObjectGetPropertyDataSize(system, &address, 0, nil, &size) == noErr,
          size % UInt32(MemoryLayout<AudioDeviceID>.size) == 0 else { return .unavailable }
    if size == 0 { return .unavailable }
    var devices = [AudioDeviceID](repeating: 0, count: Int(size) / MemoryLayout<AudioDeviceID>.size)
    let capacity = size
    let status = devices.withUnsafeMutableBytes {
        AudioObjectGetPropertyData(system, &address, 0, nil, &size, $0.baseAddress!)
    }
    guard status == noErr, size <= capacity,
          size % UInt32(MemoryLayout<AudioDeviceID>.size) == 0 else { return .unavailable }
    var unreadable = false
    for device in devices.prefix(Int(size) / MemoryLayout<AudioDeviceID>.size) {
        var uidAddress = AudioObjectPropertyAddress(mSelector: kAudioDevicePropertyDeviceUID,
                                                   mScope: kAudioObjectPropertyScopeGlobal,
                                                   mElement: kAudioObjectPropertyElementMain)
        let uid = UnsafeMutablePointer<CFString?>.allocate(capacity: 1)
        uid.initialize(to: nil)
        defer { uid.deinitialize(count: 1); uid.deallocate() }
        var uidSize = UInt32(MemoryLayout<CFString?>.size)
        guard AudioObjectGetPropertyData(device, &uidAddress, 0, nil, &uidSize, uid) == noErr,
              uidSize == MemoryLayout<CFString?>.size, let value = uid.pointee else { unreadable = true; continue }
        if value as String == UninstallResult.uid { return .present }
    }
    return unreadable ? .unavailable : .absent
}

func waitForUninstallDeviceRemoval() -> UninstallDeviceStatus {
    verifyUninstallDeviceRemoval(read: uninstallDeviceStatus,
                                now: { ProcessInfo.processInfo.systemUptime },
                                pause: {
                                    Thread.sleep(forTimeInterval: 0.25)
                                    _ = CFRunLoopRunInMode(.defaultMode, 0.001, true)
                                })
}

func waitForInstallDeviceAppearance() -> UninstallDeviceStatus {
    verifyInstallDeviceAppearance(read: uninstallDeviceStatus,
                                 now: { ProcessInfo.processInfo.systemUptime },
                                 pause: {
                                     Thread.sleep(forTimeInterval: 0.25)
                                     _ = CFRunLoopRunInMode(.defaultMode, 0.001, true)
                                 })
}
