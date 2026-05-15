import Foundation

struct AmbientChunkResponse: Decodable {
    let ok: Bool
    let skipped: Bool?
    let reason: String?
    let commandDetected: Bool?
    let commandText: String?
    let controlAction: String?
    let replyText: String?

    enum CodingKeys: String, CodingKey {
        case ok
        case skipped
        case reason
        case commandDetected = "command_detected"
        case commandText = "command_text"
        case controlAction = "control_action"
        case replyText = "reply_text"
    }
}

// MARK: - Alfred API Client (完整版)

class AlfredAPI {
    static let shared = AlfredAPI()
    private let base = "https://alfred.31.97.221.240.nip.io/alfred/api"
    private let session = URLSession.shared

    // MARK: - Token（UserDefaults，app 內共享）
    var token: String? {
        get { UserDefaults.standard.string(forKey: "alfred_jwt_token") }
        set {
            if let t = newValue { UserDefaults.standard.set(t, forKey: "alfred_jwt_token") }
            else { UserDefaults.standard.removeObject(forKey: "alfred_jwt_token") }
        }
    }

    private func authorized(_ req: inout URLRequest) {
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let t = token { req.setValue("Bearer \(t)", forHTTPHeaderField: "Authorization") }
    }

    // MARK: - Device Auth（無密碼，用 identifierForVendor）
    func deviceLogin(deviceId: String) async throws -> String {
        var req = URLRequest(url: URL(string: "\(base)/auth/device")!)
        req.httpMethod = "POST"
        authorized(&req)
        req.httpBody = try JSONSerialization.data(withJSONObject: ["device_id": deviceId])
        let (data, _) = try await session.data(for: req)
        guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let t = json["token"] as? String else {
            throw URLError(.badServerResponse)
        }
        token = t
        await AuthManager.shared.saveToken(t)
        return t
    }

    // MARK: - Account Deletion (App Store 5.1.1(v))
    /// 完整刪除帳號。後端會：
    /// 1. 從 auth.db 移除 user / encrypted_credentials / device_registry
    /// 2. 刪除 per-user DB 檔案
    /// 不可復原。
    func deleteAccount() async throws {
        var req = URLRequest(url: URL(string: "\(base)/auth/account")!)
        req.httpMethod = "DELETE"
        authorized(&req)
        let (_, resp) = try await session.data(for: req)
        guard let http = resp as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw URLError(.badServerResponse)
        }
        // 清除本機 token
        token = nil
        AuthManager.shared.deleteToken()
    }

    // MARK: - Greet
    func greet() async throws -> GreetResponse {
        var req = URLRequest(url: URL(string: "\(base)/greet")!)
        authorized(&req)
        let (data, _) = try await session.data(for: req)
        return try JSONDecoder().decode(GreetResponse.self, from: data)
    }

    // MARK: - Chat (SSE Stream)
    func chatStream(message: String, history: [[String: String]]) async throws -> AsyncThrowingStream<StreamChunk, Error> {
        var req = URLRequest(url: URL(string: "\(base)/chat/stream")!)
        req.httpMethod = "POST"
        authorized(&req)
        req.httpBody = try JSONSerialization.data(withJSONObject: [
            "message": message,
            "history": history
        ])

        return AsyncThrowingStream { continuation in
            Task {
                do {
                    let (bytes, _) = try await session.bytes(for: req)
                    for try await line in bytes.lines {
                        guard line.hasPrefix("data: ") else { continue }
                        let json = String(line.dropFirst(6))
                        guard let data = json.data(using: .utf8),
                              let chunk = try? JSONDecoder().decode(StreamChunk.self, from: data)
                        else { continue }
                        continuation.yield(chunk)
                        if chunk.done == true { break }
                    }
                    continuation.finish()
                } catch {
                    continuation.finish(throwing: error)
                }
            }
        }
    }

    // MARK: - Chat (非 stream，備用)
    func chat(message: String, history: [[String: String]]) async throws -> ChatResponse {
        let body: [String: Any] = ["message": message, "history": history]
        var req = URLRequest(url: URL(string: "\(base)/chat")!)
        req.httpMethod = "POST"
        authorized(&req)
        req.httpBody = try JSONSerialization.data(withJSONObject: body)
        let (data, resp) = try await session.data(for: req)
        try validate(resp)
        return try JSONDecoder().decode(ChatResponse.self, from: data)
    }

    // MARK: - TTS
    func tts(text: String) async throws -> Data {
        var req = URLRequest(url: URL(string: "\(base)/tts")!)
        req.httpMethod = "POST"
        authorized(&req)
        req.httpBody = try JSONEncoder().encode(["text": text])
        let (data, resp) = try await session.data(for: req)
        if let http = resp as? HTTPURLResponse, !(200...299).contains(http.statusCode) {
            throw URLError(.badServerResponse)
        }
        return data
    }

    // MARK: - Transcribe
    func transcribe(audioData: Data) async throws -> String {
        let boundary = UUID().uuidString
        var req = URLRequest(url: URL(string: "\(base)/transcribe")!)
        req.httpMethod = "POST"
        req.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        if let t = token { req.setValue("Bearer \(t)", forHTTPHeaderField: "Authorization") }

        var body = Data()
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"file\"; filename=\"audio.m4a\"\r\n".data(using: .utf8)!)
        body.append("Content-Type: audio/m4a\r\n\r\n".data(using: .utf8)!)
        body.append(audioData)
        body.append("\r\n--\(boundary)--\r\n".data(using: .utf8)!)
        req.httpBody = body

        let (data, _) = try await session.data(for: req)
        let result = try JSONDecoder().decode([String: String].self, from: data)
        return result["transcript"] ?? ""
    }

    // MARK: - Translation TTS
    func translateAndSpeak(text: String, targetLang: String) async throws -> Data {
        let boundary = UUID().uuidString
        var req = URLRequest(url: URL(string: "\(base)/translate/tts")!)
        req.httpMethod = "POST"
        req.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        if let t = token { req.setValue("Bearer \(t)", forHTTPHeaderField: "Authorization") }

        var body = Data()
        for (key, value) in ["text": text, "target_lang": targetLang, "mode": "interpret"] {
            body.append("--\(boundary)\r\n".data(using: .utf8)!)
            body.append("Content-Disposition: form-data; name=\"\(key)\"\r\n\r\n".data(using: .utf8)!)
            body.append("\(value)\r\n".data(using: .utf8)!)
        }
        body.append("--\(boundary)--\r\n".data(using: .utf8)!)
        req.httpBody = body

        let (data, _) = try await session.data(for: req)
        return data
    }

    // MARK: - Location
    func uploadLocation(points: [[String: Any]]) async throws {
        var req = URLRequest(url: URL(string: "\(base)/location/update")!)
        req.httpMethod = "POST"
        authorized(&req)
        req.httpBody = try JSONSerialization.data(withJSONObject: ["points": points])
        let (_, resp) = try await session.data(for: req)
        try validate(resp)
    }

    func locationContext() async throws -> LocationContextResponse {
        try await get("/location/context")
    }

    // MARK: - Setup / Integrations
    func setupStatus() async throws -> SetupStatusResponse {
        try await get("/setup/status")
    }

    // MARK: - Scene / Work Mode
    func workModeBootstrap() async throws -> WorkModeBootstrapResponse {
        try await get("/workmode/bootstrap")
    }

    // MARK: - Family
    func familyMembers() async throws -> [FamilyMember] {
        try await get("/family/members")
    }

    func familyAlerts() async throws -> [FamilyAlert] {
        struct R: Decodable { let alerts: [FamilyAlert]? }
        // alerts endpoint returns array directly
        return try await get("/family/alerts")
    }

    func ackAlert(id: Int) async throws {
        var req = URLRequest(url: URL(string: "\(base)/family/alerts/\(id)/ack")!)
        req.httpMethod = "POST"
        authorized(&req)
        let (_, resp) = try await session.data(for: req)
        try validate(resp)
    }

    func uploadFamilyLocation(deviceToken: String, lat: Double, lng: Double, battery: Int) async throws {
        var req = URLRequest(url: URL(string: "\(base)/family/location")!)
        req.httpMethod = "POST"
        authorized(&req)
        req.httpBody = try JSONSerialization.data(withJSONObject: [
            "device_token": deviceToken,
            "lat": lat, "lng": lng, "battery": battery
        ])
        let (_, resp) = try await session.data(for: req)
        try validate(resp)
    }

    // MARK: - Reminders
    func pendingReminders() async throws -> [ReminderItem] {
        try await get("/reminders/pending")
    }

    // MARK: - Visit prep
    func visitPrep() async throws -> [VisitReminder] {
        struct R: Decodable { let reminders: [VisitReminder] }
        let r: R = try await get("/visit/prep")
        return r.reminders
    }

    // MARK: - Workouts
    func syncWorkouts(_ workouts: [[String: Any]]) async throws {
        var req = URLRequest(url: URL(string: "\(base)/workouts/sync")!)
        req.httpMethod = "POST"
        authorized(&req)
        req.httpBody = try JSONSerialization.data(withJSONObject: ["workouts": workouts])
        let (_, resp) = try await session.data(for: req)
        try validate(resp)
    }

    // MARK: - Generic
    func get<T: Decodable>(_ path: String) async throws -> T {
        var req = URLRequest(url: URL(string: "\(base)\(path)")!)
        authorized(&req)
        let (data, resp) = try await session.data(for: req)
        try validate(resp)
        return try JSONDecoder().decode(T.self, from: data)
    }

    private func validate(_ resp: URLResponse) throws {
        if let http = resp as? HTTPURLResponse, !(200...299).contains(http.statusCode) {
            throw URLError(.badServerResponse)
        }
    }

    // MARK: - Ambient（被動錄音；按金鈕啟動，不觸發 AI 回應）
    func ambientStart(label: String, triggerMessage: String? = nil) async throws -> Int {
        var req = URLRequest(url: URL(string: "\(base)/ambient/start")!)
        req.httpMethod = "POST"
        authorized(&req)
        var payload: [String: String] = ["label": label]
        if let triggerMessage, !triggerMessage.isEmpty { payload["trigger_message"] = triggerMessage }
        req.httpBody = try JSONSerialization.data(withJSONObject: payload)
        let (data, _) = try await session.data(for: req)
        guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let sid = json["session_id"] as? Int else {
            throw URLError(.badServerResponse)
        }
        return sid
    }

    @discardableResult
    func ambientUploadChunk(sessionId: Int, fileURL: URL) async throws -> AmbientChunkResponse {
        let url = URL(string: "\(base)/ambient/chunk/\(sessionId)")!
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        if let t = token { req.setValue("Bearer \(t)", forHTTPHeaderField: "Authorization") }
        let boundary = "AlfredBoundary-\(UUID().uuidString)"
        req.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        let audio = try Data(contentsOf: fileURL)
        var body = Data()
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"file\"; filename=\"\(fileURL.lastPathComponent)\"\r\n".data(using: .utf8)!)
        body.append("Content-Type: audio/m4a\r\n\r\n".data(using: .utf8)!)
        body.append(audio)
        body.append("\r\n--\(boundary)--\r\n".data(using: .utf8)!)
        req.httpBody = body
        let (data, resp) = try await session.upload(for: req, from: body)
        if let http = resp as? HTTPURLResponse, !(200...299).contains(http.statusCode) {
            throw URLError(.badServerResponse)
        }
        return try JSONDecoder().decode(AmbientChunkResponse.self, from: data)
    }

    func ambientStop(sessionId: Int) async throws {
        var req = URLRequest(url: URL(string: "\(base)/ambient/stop/\(sessionId)")!)
        req.httpMethod = "POST"
        authorized(&req)
        let (_, resp) = try await session.data(for: req)
        try validate(resp)
    }

    func ambientForceRollup(sessionId: Int) async throws {
        var req = URLRequest(url: URL(string: "\(base)/ambient/rollup/\(sessionId)")!)
        req.httpMethod = "POST"
        authorized(&req)
        let (_, resp) = try await session.data(for: req)
        try validate(resp)
    }

    // MARK: - Files / Documents
    func uploadDocument(fileURL: URL, purpose: String = "document") async throws -> UploadedFileResponse {
        let boundary = "AlfredDocument-\(UUID().uuidString)"
        var req = URLRequest(url: URL(string: "\(base)/files/upload")!)
        req.httpMethod = "POST"
        if let t = token { req.setValue("Bearer \(t)", forHTTPHeaderField: "Authorization") }
        req.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")

        let filename = fileURL.lastPathComponent
        let fileData = try Data(contentsOf: fileURL)
        let mime = Self.mimeType(for: filename)
        var body = Data()

        func appendField(_ name: String, _ value: String) {
            body.append("--\(boundary)\r\n".data(using: .utf8)!)
            body.append("Content-Disposition: form-data; name=\"\(name)\"\r\n\r\n".data(using: .utf8)!)
            body.append("\(value)\r\n".data(using: .utf8)!)
        }

        appendField("description", "主人透過 iPhone 交給阿福分析的文件")
        appendField("tags", purpose)
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"file\"; filename=\"\(filename)\"\r\n".data(using: .utf8)!)
        body.append("Content-Type: \(mime)\r\n\r\n".data(using: .utf8)!)
        body.append(fileData)
        body.append("\r\n--\(boundary)--\r\n".data(using: .utf8)!)

        let (data, resp) = try await session.upload(for: req, from: body)
        try validate(resp)
        return try JSONDecoder().decode(UploadedFileResponse.self, from: data)
    }

    func analyzeUploadedDocument(fileId: Int) async throws -> ContractAnalyzeResponse {
        var req = URLRequest(url: URL(string: "\(base)/contract/analyze/\(fileId)?output=report")!)
        req.httpMethod = "POST"
        authorized(&req)
        let (data, resp) = try await session.data(for: req)
        try validate(resp)
        return try JSONDecoder().decode(ContractAnalyzeResponse.self, from: data)
    }

    private static func mimeType(for filename: String) -> String {
        let lower = filename.lowercased()
        if lower.hasSuffix(".pdf") { return "application/pdf" }
        if lower.hasSuffix(".docx") { return "application/vnd.openxmlformats-officedocument.wordprocessingml.document" }
        if lower.hasSuffix(".txt") { return "text/plain" }
        if lower.hasSuffix(".md") { return "text/markdown" }
        return "application/octet-stream"
    }
}

// MARK: - Response Models

struct ChatResponse: Decodable {
    let text: String?
    let card: CardData?
}

struct UploadedFileResponse: Decodable {
    let id: Int
    let name: String
    let size: Int
    let ok: Bool
}

struct ContractAnalyzeResponse: Decodable {
    let ok: Bool
    let fileId: Int?
    let name: String?
    let report: String?
    let error: String?
    let output: String?

    enum CodingKeys: String, CodingKey {
        case ok, name, report, error, output
        case fileId = "file_id"
    }
}

struct LocationContextResponse: Decodable {
    let context: String
    let name: String
    let greeting: String
    let checkinRecorded: Bool?
    enum CodingKeys: String, CodingKey {
        case context, name, greeting
        case checkinRecorded = "checkin_recorded"
    }
}

struct WorkModeBootstrapResponse: Decodable {
    let mode: String
    let scene: WorkModeScene
    let readyLine: String
    let today: WorkModeToday
    let office: WorkModeOffice
    let recentDocuments: [WorkModeDocument]
    enum CodingKeys: String, CodingKey {
        case mode, scene, today, office
        case readyLine = "ready_line"
        case recentDocuments = "recent_documents"
    }
}

struct WorkModeScene: Decodable {
    let type: String
    let name: String?
    let lastSeen: String?
    let stale: Bool?
    let driveScope: String?
    let priority: String?
    enum CodingKeys: String, CodingKey {
        case type, name, stale, priority
        case lastSeen = "last_seen"
        case driveScope = "drive_scope"
    }
}

struct WorkModeToday: Decodable {
    let events: [WorkModeEvent]
    let todos: [WorkModeTodo]
}

struct WorkModeEvent: Decodable, Identifiable {
    var id: String { "\(time)-\(title)" }
    let title: String
    let time: String
}

struct WorkModeTodo: Decodable, Identifiable {
    var id: String { "\(due)-\(title)" }
    let title: String
    let due: String
}

struct WorkModeOffice: Decodable {
    let eodItems: [WorkModeCountItem]
    enum CodingKeys: String, CodingKey { case eodItems = "eod_items" }
}

struct WorkModeCountItem: Decodable, Identifiable {
    var id: String { title }
    let title: String
    let count: Int
}

struct WorkModeDocument: Decodable, Identifiable {
    var id: String { "\(source)-\(name)-\(modified)" }
    let name: String
    let source: String
    let modified: String
}

struct SetupStatusResponse: Decodable {
    let google: GoogleIntegrationStatus
    let line: LineIntegrationStatus
    let telegram: TelegramIntegrationStatus
    let whatsapp: WhatsAppIntegrationStatus?
}

struct GoogleIntegrationStatus: Decodable {
    let connected: Bool
    let gmail: Bool?
}

struct LineIntegrationStatus: Decodable {
    let configured: Bool
    let botId: String?
    let userConnected: Bool
    enum CodingKeys: String, CodingKey {
        case configured
        case botId = "bot_id"
        case userConnected = "user_connected"
    }
}

struct TelegramIntegrationStatus: Decodable {
    let configured: Bool
    let botUsername: String?
    let userConnected: Bool
    enum CodingKeys: String, CodingKey {
        case configured
        case botUsername = "bot_username"
        case userConnected = "user_connected"
    }
}

struct WhatsAppIntegrationStatus: Decodable {
    let configured: Bool
    let userConnected: Bool?
    let note: String?
    enum CodingKeys: String, CodingKey {
        case configured, note
        case userConnected = "user_connected"
    }
}

struct FamilyMember: Decodable, Identifiable {
    let id: Int
    let name: String
    let relation: String
    let lat: Double?
    let lng: Double?
    let address: String?
    let lastSeen: String?
    let battery: Int?
    let isHome: Bool
    enum CodingKeys: String, CodingKey {
        case id, name, relation, lat, lng, address, battery
        case lastSeen = "last_seen"
        case isHome = "is_home"
    }
}

struct FamilyAlert: Decodable, Identifiable {
    let id: Int
    let name: String
    let message: String
    let severity: String
}

struct ReminderItem: Decodable, Identifiable {
    let id: Int
    let title: String
    let triggerAt: String
    enum CodingKeys: String, CodingKey {
        case id, title
        case triggerAt = "trigger_at"
    }
}

struct VisitReminder: Decodable {
    let eventTitle: String
    let person: String
    let suggestion: String
    let minutesAway: Int
    let message: String
    enum CodingKeys: String, CodingKey {
        case person, suggestion, message
        case eventTitle = "event_title"
        case minutesAway = "minutes_away"
    }
}
