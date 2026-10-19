import Darwin
import Foundation

func hostArchitecture() -> String {
    var arm: Int32 = 0
    var count = MemoryLayout<Int32>.size
    if sysctlbyname("hw.optional.arm64", &arm, &count, nil, 0) == 0, arm == 1 {
        return "arm64"
    }
    let process = Process()
    process.executableURL = URL(fileURLWithPath: "/usr/bin/uname")
    process.arguments = ["-m"]
    let output = Pipe()
    process.standardOutput = output
    guard (try? process.run()) != nil else { return "unknown" }
    process.waitUntilExit()
    let result = String(decoding: output.fileHandleForReading.readDataToEndOfFile(), as: UTF8.self)
        .trimmingCharacters(in: .whitespacesAndNewlines)
    return result == "arm64" || result == "x86_64" ? result : "unknown"
}
