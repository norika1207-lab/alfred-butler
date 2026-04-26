import Foundation

// MARK: - Alfred API Client (完整版)

class AlfredAPI {
    static let shared = AlfredAPI()
    private let base = "https://YOUR_BACKEND_HOST/alfred/api"
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
        return t
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
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONSerialization.data(withJSONObject: body)
        let (data, _) = try await session.data(for: req)
        return try JSONDecoder().decode(ChatResponse.self, from: data)
    }

    // MARK: - TTS
    func tts(text: String) async throws -> Data {
        var req = URLRequest(url: URL(string: "\(base)/tts")!)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONEncoder().encode(["text": text])
        let (data, _) = try await session.data(for: req)
        return data
    }

    // MARK: - Transcribe
    func transcribe(audioData: Data) async throws -> String {
        let boundary = UUID().uuidString
        var req = URLRequest(url: URL(string: "\(base)/transcribe")!)
        req.httpMethod = "POST"
        req.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")

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
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONSerialization.data(withJSONObject: ["points": points])
        _ = try await session.data(for: req)
    }

    func locationContext() async throws -> LocationContextResponse {
        try await get("/location/context")
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
        _ = try await session.data(for: req)
    }

    func uploadFamilyLocation(deviceToken: String, lat: Double, lng: Double, battery: Int) async throws {
        var req = URLRequest(url: URL(string: "\(base)/family/location")!)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONSerialization.data(withJSONObject: [
            "device_token": deviceToken,
            "lat": lat, "lng": lng, "battery": battery
        ])
        _ = try await session.data(for: req)
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
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONSerialization.data(withJSONObject: ["workouts": workouts])
        _ = try await session.data(for: req)
    }

    // MARK: - Generic
    func get<T: Decodable>(_ path: String) async throws -> T {
        let (data, _) = try await session.data(from: URL(string: "\(base)\(path)")!)
        return try JSONDecoder().decode(T.self, from: data)
    }
}

// MARK: - Response Models

struct ChatResponse: Decodable {
    let text: String?
    let card: CardData?
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
