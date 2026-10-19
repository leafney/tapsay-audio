// TapSay Audio graphical uninstaller. Copyright 2026 TapSay contributors.
// SPDX-License-Identifier: GPL-3.0-only
import AppKit
import Foundation
import Security
import Darwin

typealias PrivilegedExec = @convention(c) (
    AuthorizationRef, UnsafePointer<CChar>, AuthorizationFlags,
    UnsafePointer<UnsafePointer<CChar>?>,
    UnsafeMutablePointer<UnsafeMutablePointer<FILE>?>?
) -> OSStatus

func alert(_ title: String, _ message: String, buttons: [String]) -> Int {
    let box = NSAlert()
    box.messageText = title
    box.informativeText = message
    box.alertStyle = .warning
    for button in buttons { box.addButton(withTitle: button) }
    return box.runModal().rawValue
}
func stop(_ title: String, _ message: String, status: Int32) -> Never {
    _ = alert(title, message, buttons: ["好"])
    exit(status)
}
@main struct Uninstaller {
static func main() {
let args = Array(CommandLine.arguments.dropFirst())
let app = Bundle.main.bundleURL
let resources = app.appendingPathComponent("Contents/Resources")
let arch = hostArchitecture()
let tool = app.appendingPathComponent("Contents/MacOS/TapSayAudioTransaction-\(arch)")
let metadata = resources.appendingPathComponent("product.json")
guard FileManager.default.isExecutableFile(atPath: tool.path), FileManager.default.fileExists(atPath: metadata.path) else {
    stop("卸载工具不完整", "缺少内置卸载程序或产品信息，请重新下载安装包。", status: 1)
}
if args.first == "--privileged-uninstall" {
    let process = Process()
    process.executableURL = tool
    process.arguments = ["uninstall", "--yes", "--metadata", metadata.path]
    do { try process.run(); process.waitUntilExit(); exit(process.terminationStatus) }
    catch { stop("卸载失败", String(describing: error), status: 1) }
}
NSApplication.shared.setActivationPolicy(.regular)
NSApplication.shared.activate(ignoringOtherApps: true)
let summary = "只清理 TapSay Audio 驱动、专属安装状态和安装收据。\n\n操作期间系统音频可能短暂中断。恢复备份会保留。不会修改 TapSay 主程序、其他声卡或系统默认音频设备。"
guard alert("卸载 TapSay Audio 2ch？", summary, buttons: ["取消", "卸载"]) == NSApplication.ModalResponse.alertSecondButtonReturn.rawValue else { exit(0) }
var authorization: AuthorizationRef?
let createStatus = AuthorizationCreate(nil, nil, [], &authorization)
guard createStatus == errAuthorizationSuccess, let authorization else { stop("无法请求管理员授权", "请稍后重试。", status: 1) }
defer { AuthorizationFree(authorization, []) }
var output = Data()
let status = String(kAuthorizationRightExecute).withCString { rightName -> OSStatus in
    var item = AuthorizationItem(name: rightName, valueLength: 0, value: nil, flags: 0)
    return withUnsafeMutablePointer(to: &item) { itemPointer in
        var rights = AuthorizationRights(count: 1, items: itemPointer)
        let authStatus = AuthorizationCopyRights(authorization, &rights, nil, [.interactionAllowed, .extendRights, .preAuthorize], nil)
        guard authStatus == errAuthorizationSuccess else { return authStatus }
        let command = strdup("--privileged-uninstall")!
        defer { free(command) }
        let argv: [UnsafePointer<CChar>?] = [UnsafePointer(command), nil]
        var pipe: UnsafeMutablePointer<FILE>?
        let executeStatus = tool.path.withCString { path in
            guard let symbol = dlsym(UnsafeMutableRawPointer(bitPattern: -2), "AuthorizationExecuteWithPrivileges") else {
                return OSStatus(errAuthorizationToolExecuteFailure)
            }
            let execute = unsafeBitCast(symbol, to: PrivilegedExec.self)
            return argv.withUnsafeBufferPointer { buffer in
                execute(authorization, path, [], buffer.baseAddress!, &pipe)
            }
        }
        guard executeStatus == errAuthorizationSuccess else { return executeStatus }
        if let pipe {
            var buffer = [UInt8](repeating: 0, count: 4096)
            while true {
                let count = fread(&buffer, 1, buffer.count, pipe)
                if count == 0 { break }
                output.append(contentsOf: buffer[..<count])
            }
            fclose(pipe)
        }
        return executeStatus
    }
}
guard status == errAuthorizationSuccess else {
    if status == errAuthorizationCanceled { exit(0) }
    stop("未获得管理员授权", "未删除任何文件。错误代码：\(status)", status: 1)
}
let result = String(decoding: output, as: UTF8.self).trimmingCharacters(in: .whitespacesAndNewlines)
if result.contains("操作失败：") || result.contains("恢复") && result.contains("失败") {
    stop("卸载未完成", result, status: 1)
}
_ = alert("卸载已执行", result.isEmpty ? "已提交卸载操作；请重新打开音频设置核实设备状态。" : result, buttons: ["好"])
}
}
