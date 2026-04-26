import Foundation
import Combine

@MainActor
class OfficeViewModel: ObservableObject {
    static let shared = OfficeViewModel()

    @Published var eodItems: [EodItem] = []
    @Published var roomPulse: [RoomStatus] = []
    @Published var thanksNudge: ThanksNudge? = nil
    @Published var supplies: [SupplyItem] = []
    @Published var colleagues: [ColleagueStatus] = []
    @Published var isLoading = false

    func reload() async {
        isLoading = true
        await withTaskGroup(of: Void.self) { group in
            group.addTask { await self.fetchEod() }
            group.addTask { await self.fetchRooms() }
            group.addTask { await self.fetchThanks() }
            group.addTask { await self.fetchSupplies() }
            group.addTask { await self.fetchColleagues() }
        }
        isLoading = false
    }

    private func fetchEod() async {
        let req = AuthManager.shared.authorizedRequest(path: "/api/office/eod-wrap")
        guard let (data, _) = try? await URLSession.shared.data(for: req) else { return }
        if let resp = try? JSONDecoder().decode(EodWrapResponse.self, from: data) {
            eodItems = resp.items ?? []
        }
    }

    private func fetchRooms() async {
        let req = AuthManager.shared.authorizedRequest(path: "/api/office/rooms")
        guard let (data, _) = try? await URLSession.shared.data(for: req) else { return }
        if let resp = try? JSONDecoder().decode([RoomStatus].self, from: data) {
            roomPulse = resp
        }
    }

    private func fetchThanks() async {
        let req = AuthManager.shared.authorizedRequest(path: "/api/office/thanks-nudge")
        guard let (data, _) = try? await URLSession.shared.data(for: req) else { return }
        if let resp = try? JSONDecoder().decode(ThanksNudge.self, from: data) {
            thanksNudge = resp
        }
    }

    private func fetchSupplies() async {
        let req = AuthManager.shared.authorizedRequest(path: "/api/office/supplies")
        guard let (data, _) = try? await URLSession.shared.data(for: req) else { return }
        if let resp = try? JSONDecoder().decode([SupplyItem].self, from: data) {
            supplies = resp
        }
    }

    private func fetchColleagues() async {
        let req = AuthManager.shared.authorizedRequest(path: "/api/office/colleagues")
        guard let (data, _) = try? await URLSession.shared.data(for: req) else { return }
        if let resp = try? JSONDecoder().decode([ColleagueStatus].self, from: data) {
            colleagues = resp
        }
    }
}

// MARK: - Models

struct EodWrapResponse: Decodable {
    let items: [EodItem]?
}

struct EodItem: Decodable, Identifiable {
    var id: String { title }
    let title: String
    let done: Bool
    let note: String?
}

struct RoomStatus: Decodable, Identifiable {
    var id: String { name }
    let name: String
    let occupied: Bool
    let until: String?
    let capacity: Int?
}

struct ThanksNudge: Decodable {
    let person: String?
    let reason: String?
    let daysAgo: Int?
    enum CodingKeys: String, CodingKey {
        case person, reason
        case daysAgo = "days_ago"
    }
}

struct SupplyItem: Decodable, Identifiable {
    var id: String { name }
    let name: String
    let level: String  // "ok" | "low" | "critical"
    let note: String?
}

struct ColleagueStatus: Decodable, Identifiable {
    var id: String { name }
    let name: String
    let status: String  // "in-office" | "wfh" | "off"
    let mood: String?
}
