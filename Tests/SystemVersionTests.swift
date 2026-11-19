import Foundation

@main struct SystemVersionTests {
    static func main() {
        let versions = ["arm64": "14.0", "x86_64": "13.0"]
        precondition(!supportsSystem(architecture: "x86_64", majorVersion: 12, versions: versions))
        precondition(supportsSystem(architecture: "x86_64", majorVersion: 13, versions: versions))
        precondition(!supportsSystem(architecture: "arm64", majorVersion: 13, versions: versions))
        precondition(supportsSystem(architecture: "arm64", majorVersion: 14, versions: versions))
        precondition(!supportsSystem(architecture: "unknown", majorVersion: 99, versions: versions))
        precondition(!supportsSystem(architecture: "x86_64", majorVersion: 13, versions: [:]))
    }
}
