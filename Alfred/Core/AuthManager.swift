import Foundation
import Combine
import Security

// MARK: - Auth Manager
// 管理登入、JWT token 儲存（Keychain）、訂閱狀態

@MainActor
class AuthManager: ObservableObject {
    static let shared = AuthManager()

    @Published var isLoggedIn: Bool = false
    @Published var email: String = ""
    @Published var subscription: String = "trial"
    @Published var trialRemaining: Int = 50

    private let base = "https://alfred.31.97.221.240.nip.io/alfred/api"
    private let keychainKey = "alfred_jwt_token"

    init() {
        // 啟動時檢查 Keychain 有沒有 token
        if let _ = loadToken() {
            isLoggedIn = true
            Task { await refreshStatus() }
        }
    }

    // MARK: - Token（Keychain）
    func saveToken(_ token: String) {
        let data = token.data(using: .utf8)!
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: keychainKey,
            kSecValueData as String: data
        ]
        SecItemDelete(query as CFDictionary)
        SecItemAdd(query as CFDictionary, nil)
        UserDefaults.standard.set(token, forKey: keychainKey)
        AlfredAPI.shared.token = token
    }

    func loadToken() -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: keychainKey,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]
        var result: AnyObject?
        SecItemCopyMatching(query as CFDictionary, &result)
        if let data = result as? Data, let token = String(data: data, encoding: .utf8) {
            return token
        }
        return UserDefaults.standard.string(forKey: keychainKey)
    }

    func deleteToken() {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: keychainKey
        ]
        SecItemDelete(query as CFDictionary)
        UserDefaults.standard.removeObject(forKey: keychainKey)
        AlfredAPI.shared.token = nil
    }

    // MARK: - Auth 的 URLRequest helper
    func authorizedRequest(path: String, method: String = "GET") -> URLRequest {
        var normalized = path.hasPrefix("/") ? path : "/\(path)"
        if normalized.hasPrefix("/api/") {
            normalized.removeFirst(4)
        }
        var req = URLRequest(url: URL(string: "\(base)\(normalized)")!)
        req.httpMethod = method
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let token = loadToken() {
            req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        return req
    }

    // MARK: - Register
    func register(email: String, password: String) async throws {
        var req = URLRequest(url: URL(string: "\(base)/auth/register")!)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONEncoder().encode(["email": email, "password": password])

        let (data, _) = try await URLSession.shared.data(for: req)
        let resp = try JSONDecoder().decode(AuthResponse.self, from: data)

        guard resp.ok else {
            throw AuthError.serverError(resp.detail ?? "註冊失敗")
        }
        saveToken(resp.token!)
        self.email = resp.email ?? email
        self.subscription = resp.subscription ?? "trial"
        self.trialRemaining = resp.trialRemaining ?? 50
        self.isLoggedIn = true
    }

    // MARK: - Login
    func login(email: String, password: String) async throws {
        var req = URLRequest(url: URL(string: "\(base)/auth/login")!)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONEncoder().encode(["email": email, "password": password])

        let (data, _) = try await URLSession.shared.data(for: req)
        let resp = try JSONDecoder().decode(AuthResponse.self, from: data)

        guard resp.ok else {
            throw AuthError.serverError(resp.detail ?? "Email 或密碼不正確")
        }
        saveToken(resp.token!)
        self.email = resp.email ?? email
        self.subscription = resp.subscription ?? "trial"
        self.trialRemaining = resp.trialRemaining ?? 50
        self.isLoggedIn = true
    }

    // MARK: - Logout
    func logout() {
        deleteToken()
        email = ""
        subscription = "trial"
        trialRemaining = 50
        isLoggedIn = false
    }

    // MARK: - Refresh status
    func refreshStatus() async {
        var req = authorizedRequest(path: "/auth/me")
        guard let token = loadToken() else { return }
        req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")

        guard let (data, _) = try? await URLSession.shared.data(for: req),
              let resp = try? JSONDecoder().decode(MeResponse.self, from: data)
        else { return }

        self.email = resp.email
        self.subscription = resp.subscription
        self.trialRemaining = resp.trialRemaining
    }
}

// MARK: - Models
struct AuthResponse: Decodable {
    let ok: Bool
    let token: String?
    let email: String?
    let subscription: String?
    let trialRemaining: Int?
    let detail: String?
    enum CodingKeys: String, CodingKey {
        case ok, token, email, subscription, detail
        case trialRemaining = "trial_remaining"
    }
}

struct MeResponse: Decodable {
    let email: String
    let subscription: String
    let trialRemaining: Int
    enum CodingKeys: String, CodingKey {
        case email, subscription
        case trialRemaining = "trial_remaining"
    }
}

enum AuthError: LocalizedError {
    case serverError(String)
    var errorDescription: String? {
        if case .serverError(let msg) = self { return msg }
        return nil
    }
}
