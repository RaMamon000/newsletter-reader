import Foundation
import CryptoKit

enum DataCrypto {
    enum Failure: Error { case badKey, badBase64 }

    /// base64( nonce(12) || ciphertext || tag(16) ) を復号して UTF-8 JSON の Data を返す
    static func decrypt(_ encoded: Data) throws -> Data {
        guard let keyData = Data(base64Encoded: Secrets.dataKeyBase64), keyData.count == 32 else { throw Failure.badKey }
        let text = String(decoding: encoded, as: UTF8.self).trimmingCharacters(in: .whitespacesAndNewlines)
        guard let raw = Data(base64Encoded: text) else { throw Failure.badBase64 }
        let box = try AES.GCM.SealedBox(combined: raw)
        return try AES.GCM.open(box, using: SymmetricKey(data: keyData))
    }
}
