import Foundation

// 對話歷史持久化：寫到 Documents/conversation_log/YYYY-MM-DD.jsonl
// 每行一個 JSON：{ts, role, text, audio?, action?}
class ConversationLog {
    static let shared = ConversationLog()

    private let queue = DispatchQueue(label: "alfred.conversation.log")
    private let isoFormatter: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f
    }()

    func log(role: String, text: String, audioPath: String? = nil, action: String? = nil) {
        let ts = isoFormatter.string(from: Date())
        var entry: [String: Any] = ["ts": ts, "role": role, "text": text]
        if let a = audioPath { entry["audio"] = a }
        if let act = action { entry["action"] = act }

        queue.async {
            let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            let logDir = docs.appendingPathComponent("conversation_log", isDirectory: true)
            try? FileManager.default.createDirectory(at: logDir, withIntermediateDirectories: true)

            let day = String(ts.prefix(10))   // "2026-04-26"
            let file = logDir.appendingPathComponent("\(day).jsonl")

            guard let data = try? JSONSerialization.data(withJSONObject: entry),
                  let line = String(data: data, encoding: .utf8) else { return }
            let final = (line + "\n").data(using: .utf8)!

            if FileManager.default.fileExists(atPath: file.path) {
                if let h = try? FileHandle(forWritingTo: file) {
                    defer { try? h.close() }
                    h.seekToEndOfFile()
                    try? h.write(contentsOf: final)
                }
            } else {
                try? final.write(to: file)
            }
        }
    }
}
