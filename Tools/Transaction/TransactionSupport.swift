// SPDX-License-Identifier: GPL-3.0-only
import Foundation

struct Failure: Error, CustomStringConvertible {
    let description: String

    init(_ text: String) {
        description = text
    }
}

func require(_ value: Bool, _ text: String) throws {
    if !value { throw Failure(text) }
}
