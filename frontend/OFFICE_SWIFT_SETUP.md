<!-- ALFRED_MANDATORY_SESSION_BOOTSTRAP -->
# MANDATORY FIRST STEP FOR ANY ALFRED / AFU / ALICE REQUEST

Before any analysis, file edit, DB write, backend patch, demo edit, iOS change, systemd change, or conclusion about Alfred / Afu / Alice / File Map, run:

```bash
/usr/local/bin/alfred-context-guard
```

This is required even in a new session. Do not patch first and read docs later. See `/opt/alfred/ALFRED_MANDATORY_SESSION_BOOTSTRAP.md`.

<!-- /ALFRED_MANDATORY_SESSION_BOOTSTRAP -->

# Alfred 辦公室模組 — 完整安裝手冊

> 給接手的新視窗：先把這份文件完整讀完，再動任何一行程式碼。

---

## 一、阿福的核心設計理念（必讀）

阿福不是助理，是管家。兩者最大的差別：
- **助理**等你問
- **管家**在你問之前就替你想好了

### 設計三鐵律
1. **零介面** — 沒有選單、沒有儀表板。只有對話。介面本身就是阻力。
2. **橋梁不是代理** — 阿福不代替主人做決定，只確保人對人的關心不因忙碌而斷掉。
3. **永遠先行一步** — 不等你說「提醒我」，在你需要之前就出現。

### 辦公室模組的定位
市面上的辦公工具問「怎麼讓流程更快」。  
阿福辦公室模組問「哪些人對人的事情，因為忙碌被省略了」。

**12 個場景對應三條主線：**
- 讓承諾不消失 → Promise Tracker、EOD Wrap、Thanks Nudge
- 讓主管看到看不見的 → Silence Radar、Timezone Fatigue、Manager Lens、Expertise Finder
- 讓後勤消失在背景 → Room Pulse、Supply Autopilot、Guest Prep、Movement Nudge、Onboarding

---

## 二、目前專案狀態

### 後端（已完成）
- 伺服器：`https://YOUR_BACKEND_HOST`
- 程式碼：`/opt/alfred/backend/main.py`（7500+ 行）+ `/opt/alfred/backend/office_service.py`（826 行）
- 辦公室 API 端點（全部需要 JWT Bearer token）：
  - `GET /api/office/eod-wrap` — 下班收尾摘要
  - `GET /api/office/room-pulse` — 訂了但沒人進的會議室
  - `GET /api/office/thanks-nudge` — 待感謝清單
  - `GET /api/office/supplies` — 耗材庫存
  - `GET /api/office/silence-radar` — 沉默同事偵測
  - `GET /api/office/manager-lens` — 主管視角
  - `GET /api/office/timezone-fatigue` — 跨時區疲勞
  - `GET /api/office/expertise-finder?q=關鍵字` — 專長查找
  - `GET /api/office/colleagues` — 同事名單
  - `GET /api/office/rooms` — 會議室列表
  - `POST /api/office/bookings/{id}/checkin` — 打卡進場
  - `POST /api/office/bookings/{id}/release` — 釋出會議室

### iOS 專案結構
```
Alfred/
├── AlfredApp.swift
├── Core/
│   ├── AlfredAPI.swift       ← API client（已有，但 get() 沒有注入 auth token）
│   ├── AlfredViewModel.swift ← 主 ViewModel
│   ├── AuthManager.swift     ← JWT token 管理（用 authorizedRequest() 加 token）
│   ├── AudioManager.swift
│   ├── AudioEngine.swift
│   ├── BackgroundManager.swift
│   ├── LocationManager.swift
│   ├── VaultManager.swift
│   └── HealthKitManager.swift
└── Features/
    ├── Chat/
    │   └── AlfredView.swift  ← 主畫面（需要修改，加辦公室按鈕）
    ├── Auth/
    │   └── LoginView.swift
    └── Office/               ← 用戶已建立此資料夾
        ├── OfficeModels.swift    ← 已放入
        ├── OfficeViewModel.swift ← 已放入
        └── OfficeDashboardView.swift ← 已放入
```

### 重要：AuthManager.authorizedRequest
辦公室所有 API 需要 auth token。用這個 helper：
```swift
AuthManager.shared.authorizedRequest(path: "/office/eod-wrap")
// 會自動在 header 加上 Authorization: Bearer <token>
```

---

## 三、三個已放入的 Swift 檔案完整內容

### OfficeModels.swift
```swift
import Foundation

struct EODWrap: Decodable {
    let pendingTodos: Int
    let openPromises: Int
    let pendingThanks: Int
    let lowSupplies: Int
    let openSubCommits: Int
    var totalIssues: Int {
        pendingTodos + openPromises + pendingThanks + lowSupplies + openSubCommits
    }
    enum CodingKeys: String, CodingKey {
        case pendingTodos   = "pending_todos"
        case openPromises   = "open_promises"
        case pendingThanks  = "pending_thanks"
        case lowSupplies    = "low_supplies"
        case openSubCommits = "open_sub_commits"
    }
}

struct RoomPulse: Decodable {
    let abandonedBookings: [AbandonedBooking]
    let count: Int
    enum CodingKeys: String, CodingKey {
        case abandonedBookings = "abandoned_bookings"
        case count
    }
}

struct AbandonedBooking: Decodable, Identifiable {
    let bookingId: Int
    let title: String
    let startTime: String
    let room: String?
    var id: Int { bookingId }
    enum CodingKeys: String, CodingKey {
        case bookingId = "booking_id"
        case title
        case startTime = "start_time"
        case room
    }
}

struct ThanksNudge: Decodable {
    let pending: [ThanksItem]
}

struct ThanksItem: Decodable, Identifiable {
    let id: Int
    let person: String
    let reason: String
    let date: String
}

struct OfficeSupply: Decodable, Identifiable {
    let id: Int
    let item: String
    let category: String
    let quantity: Double
    let threshold: Double
    let unit: String
    let lastOrdered: String?
    let low: Bool
    enum CodingKeys: String, CodingKey {
        case id, item, category, quantity, threshold, unit, low
        case lastOrdered = "last_ordered"
    }
}

struct SilenceRadar: Decodable {
    let silentColleagues: [SilentColleague]
    let thresholdDays: Int
    enum CodingKeys: String, CodingKey {
        case silentColleagues = "silent_colleagues"
        case thresholdDays    = "threshold_days"
    }
}

struct SilentColleague: Decodable, Identifiable {
    let name: String
    let role: String?
    let dept: String?
    let daysSince: Int?
    var id: String { name }
    enum CodingKeys: String, CodingKey {
        case name, role, dept
        case daysSince = "days_since"
    }
}

struct ManagerLens: Decodable {
    let subordinates: [SubordinateSummary]
    let openSubCommits: [SubCommit]
    let openPromises: [PromiseSummary]
    enum CodingKeys: String, CodingKey {
        case subordinates
        case openSubCommits = "open_sub_commits"
        case openPromises   = "open_promises"
    }
}

struct SubordinateSummary: Decodable, Identifiable {
    let id: Int
    let name: String
    let role: String?
    let last1on1: String?
    enum CodingKeys: String, CodingKey {
        case id, name, role
        case last1on1 = "last_1on1"
    }
}

struct SubCommit: Decodable, Identifiable {
    let sub: String
    let content: String
    let deadline: String?
    var id: String { "\(sub)-\(content)" }
}

struct PromiseSummary: Decodable, Identifiable {
    let to: String
    let content: String
    let deadline: String?
    var id: String { "\(to)-\(content)" }
}
```

---

### OfficeViewModel.swift
```swift
import Foundation

@MainActor
class OfficeViewModel: ObservableObject {
    static let shared = OfficeViewModel()

    @Published var eodWrap: EODWrap?
    @Published var roomPulse: RoomPulse?
    @Published var thanksNudge: ThanksNudge?
    @Published var supplies: [OfficeSupply] = []
    @Published var silenceRadar: SilenceRadar?
    @Published var managerLens: ManagerLens?
    @Published var isLoading = false
    @Published var lastUpdated: Date?

    private let session = URLSession.shared

    func refresh() async {
        isLoading = true
        await fetchEOD()
        await fetchRoomPulse()
        await fetchThanksNudge()
        await fetchSupplies()
        await fetchSilenceRadar()
        await fetchManagerLens()
        lastUpdated = Date()
        isLoading = false
    }

    private func fetch<T: Decodable>(_ path: String) async -> T? {
        let req = AuthManager.shared.authorizedRequest(path: path)
        guard let (data, _) = try? await session.data(for: req) else { return nil }
        return try? JSONDecoder().decode(T.self, from: data)
    }

    private func fetchEOD()         async { eodWrap      = await fetch("/office/eod-wrap") }
    private func fetchRoomPulse()    async { roomPulse    = await fetch("/office/room-pulse") }
    private func fetchThanksNudge()  async { thanksNudge  = await fetch("/office/thanks-nudge") }
    private func fetchSupplies()     async { supplies     = (await fetch("/office/supplies")) ?? [] }
    private func fetchSilenceRadar() async { silenceRadar = await fetch("/office/silence-radar") }
    private func fetchManagerLens()  async { managerLens  = await fetch("/office/manager-lens") }

    func releaseRoom(_ bookingId: Int) async {
        let req = AuthManager.shared.authorizedRequest(
            path: "/office/bookings/\(bookingId)/release", method: "POST")
        _ = try? await session.data(for: req)
        await fetchRoomPulse()
    }

    func checkinRoom(_ bookingId: Int) async {
        let req = AuthManager.shared.authorizedRequest(
            path: "/office/bookings/\(bookingId)/checkin", method: "POST")
        _ = try? await session.data(for: req)
        await fetchRoomPulse()
    }

    var lowSupplies: [OfficeSupply] { supplies.filter { $0.low } }

    var hasAlert: Bool {
        (eodWrap?.totalIssues ?? 0) > 0
        || (roomPulse?.count ?? 0) > 0
        || !(thanksNudge?.pending.isEmpty ?? true)
        || !lowSupplies.isEmpty
        || !(silenceRadar?.silentColleagues.isEmpty ?? true)
    }

    var lastUpdatedText: String {
        guard let d = lastUpdated else { return "尚未載入" }
        let f = DateFormatter(); f.dateFormat = "HH:mm"
        return "更新 \(f.string(from: d))"
    }
}
```

---

### OfficeDashboardView.swift
```swift
import SwiftUI

struct OfficeDashboardView: View {
    @StateObject private var vm = OfficeViewModel.shared
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            ZStack {
                Color(hex: "#090909").ignoresSafeArea()
                if vm.isLoading && vm.eodWrap == nil {
                    VStack(spacing: 16) {
                        ProgressView().tint(Color(hex: "#c9a84c")).scaleEffect(1.2)
                        Text("阿福正在整理辦公室狀況…")
                            .font(.system(size: 14))
                            .foregroundColor(Color(hex: "#c9a84c60"))
                    }
                } else {
                    ScrollView(showsIndicators: false) {
                        VStack(spacing: 16) {
                            eodCard
                            roomPulseCard
                            thanksCard
                            suppliesCard
                            teamCard
                            Spacer().frame(height: 24)
                        }
                        .padding(.horizontal, 16)
                        .padding(.top, 8)
                    }
                }
            }
            .navigationTitle("辦公室")
            .navigationBarTitleDisplayMode(.inline)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button(action: { dismiss() }) {
                        Image(systemName: "xmark")
                            .foregroundColor(Color(hex: "#c9a84c"))
                    }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    HStack(spacing: 8) {
                        Text(vm.lastUpdatedText)
                            .font(.system(size: 11))
                            .foregroundColor(Color(hex: "#c9a84c60"))
                        if vm.isLoading {
                            ProgressView().tint(Color(hex: "#c9a84c")).scaleEffect(0.8)
                        } else {
                            Button(action: { Task { await vm.refresh() } }) {
                                Image(systemName: "arrow.clockwise")
                                    .foregroundColor(Color(hex: "#c9a84c"))
                                    .font(.system(size: 13))
                            }
                        }
                    }
                }
            }
        }
        .task { await vm.refresh() }
    }

    // MARK: - EOD
    var eodCard: some View {
        OfficeCard(icon: "moon.stars", title: "下班收尾") {
            if let eod = vm.eodWrap {
                if eod.totalIssues == 0 {
                    statusRow(icon: "checkmark.circle", text: "今天乾淨收尾，沒有未了結的事", color: "#4CAF50")
                } else {
                    VStack(spacing: 8) {
                        if eod.openPromises > 0 {
                            statusRow(icon: "exclamationmark.circle",
                                      text: "承諾 \(eod.openPromises) 件未履行", color: "#FF6B6B")
                        }
                        if eod.pendingThanks > 0 {
                            statusRow(icon: "heart.circle",
                                      text: "\(eod.pendingThanks) 個人等你說謝謝", color: "#c9a84c")
                        }
                        if eod.pendingTodos > 0 {
                            statusRow(icon: "square.and.pencil",
                                      text: "待辦 \(eod.pendingTodos) 件還開著", color: "#e8d5b7")
                        }
                        if eod.lowSupplies > 0 {
                            statusRow(icon: "shippingbox",
                                      text: "\(eod.lowSupplies) 項耗材快沒了", color: "#FF9800")
                        }
                        if eod.openSubCommits > 0 {
                            statusRow(icon: "person.2",
                                      text: "對下屬 \(eod.openSubCommits) 個承諾未兌現", color: "#9C27B0")
                        }
                    }
                }
            } else {
                placeholderText("載入中…")
            }
        }
    }

    // MARK: - Room Pulse
    var roomPulseCard: some View {
        OfficeCard(icon: "door.left.hand.open", title: "會議室感知") {
            if let pulse = vm.roomPulse {
                if pulse.count == 0 {
                    statusRow(icon: "checkmark.circle", text: "所有預約都有人進場", color: "#4CAF50")
                } else {
                    VStack(spacing: 8) {
                        ForEach(pulse.abandonedBookings.prefix(3)) { booking in
                            HStack {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(booking.title)
                                        .font(.system(size: 14, weight: .medium))
                                        .foregroundColor(Color(hex: "#e8d5b7"))
                                    Text("\(booking.room ?? "未知") · \(booking.startTime.prefix(16))")
                                        .font(.system(size: 11))
                                        .foregroundColor(Color(hex: "#c9a84c80"))
                                }
                                Spacer()
                                Button("釋出") {
                                    Task { await vm.releaseRoom(booking.bookingId) }
                                }
                                .font(.system(size: 12, weight: .medium))
                                .foregroundColor(Color(hex: "#090909"))
                                .padding(.horizontal, 12).padding(.vertical, 5)
                                .background(Color(hex: "#c9a84c"))
                                .cornerRadius(6)
                            }
                        }
                    }
                }
            } else {
                placeholderText("載入中…")
            }
        }
    }

    // MARK: - Thanks
    var thanksCard: some View {
        OfficeCard(icon: "heart", title: "感謝提醒") {
            if let thanks = vm.thanksNudge {
                if thanks.pending.isEmpty {
                    statusRow(icon: "checkmark.circle", text: "你都謝得很到位", color: "#4CAF50")
                } else {
                    VStack(spacing: 8) {
                        ForEach(thanks.pending.prefix(3)) { item in
                            HStack(alignment: .top) {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(item.person)
                                        .font(.system(size: 14, weight: .medium))
                                        .foregroundColor(Color(hex: "#e8d5b7"))
                                    if !item.reason.isEmpty {
                                        Text(item.reason)
                                            .font(.system(size: 12))
                                            .foregroundColor(Color(hex: "#c9a84c80"))
                                    }
                                }
                                Spacer()
                                Text(item.date)
                                    .font(.system(size: 11))
                                    .foregroundColor(Color(hex: "#e8d5b740"))
                            }
                        }
                        if thanks.pending.count > 3 {
                            Text("還有 \(thanks.pending.count - 3) 位…")
                                .font(.system(size: 12))
                                .foregroundColor(Color(hex: "#c9a84c60"))
                        }
                    }
                }
            } else {
                placeholderText("載入中…")
            }
        }
    }

    // MARK: - Supplies
    var suppliesCard: some View {
        OfficeCard(icon: "shippingbox", title: "耗材庫存") {
            if vm.supplies.isEmpty {
                placeholderText("跟阿福說「新增耗材 XX 數量 Y」開始追蹤")
            } else if vm.lowSupplies.isEmpty {
                statusRow(icon: "checkmark.circle", text: "所有耗材庫存充足", color: "#4CAF50")
            } else {
                VStack(spacing: 8) {
                    ForEach(vm.lowSupplies.prefix(5)) { supply in
                        HStack {
                            Circle().fill(Color(hex: "#FF6B6B")).frame(width: 6, height: 6)
                            Text(supply.item)
                                .font(.system(size: 14))
                                .foregroundColor(Color(hex: "#e8d5b7"))
                            Spacer()
                            Text("剩 \(String(format: "%.0f", supply.quantity))\(supply.unit)")
                                .font(.system(size: 12))
                                .foregroundColor(Color(hex: "#FF6B6B"))
                        }
                    }
                }
            }
        }
    }

    // MARK: - Team
    var teamCard: some View {
        OfficeCard(icon: "person.3", title: "團隊狀態") {
            VStack(spacing: 12) {
                if let radar = vm.silenceRadar {
                    if radar.silentColleagues.isEmpty {
                        statusRow(icon: "checkmark.circle", text: "所有人最近都有互動", color: "#4CAF50")
                    } else {
                        VStack(alignment: .leading, spacing: 6) {
                            HStack {
                                Image(systemName: "bell.slash")
                                    .foregroundColor(Color(hex: "#FF9800")).font(.system(size: 13))
                                Text("沉默超過 \(radar.thresholdDays) 天")
                                    .font(.system(size: 13, weight: .medium))
                                    .foregroundColor(Color(hex: "#FF9800"))
                            }
                            ForEach(radar.silentColleagues.prefix(3)) { col in
                                HStack {
                                    Text("· \(col.name)")
                                        .font(.system(size: 13))
                                        .foregroundColor(Color(hex: "#e8d5b7"))
                                    if let role = col.role {
                                        Text("(\(role))").font(.system(size: 11))
                                            .foregroundColor(Color(hex: "#c9a84c60"))
                                    }
                                    Spacer()
                                    if let days = col.daysSince {
                                        Text("\(days) 天前").font(.system(size: 11))
                                            .foregroundColor(Color(hex: "#e8d5b740"))
                                    }
                                }
                            }
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                    }
                }
                if let lens = vm.managerLens,
                   !lens.openSubCommits.isEmpty || !lens.openPromises.isEmpty {
                    Divider().background(Color(hex: "#c9a84c20"))
                    VStack(alignment: .leading, spacing: 6) {
                        HStack {
                            Image(systemName: "exclamationmark.triangle")
                                .foregroundColor(Color(hex: "#FF6B6B")).font(.system(size: 13))
                            Text("未兌現承諾")
                                .font(.system(size: 13, weight: .medium))
                                .foregroundColor(Color(hex: "#FF6B6B"))
                        }
                        ForEach(lens.openSubCommits.prefix(2)) { c in
                            Text("· 對 \(c.sub)：\(c.content)")
                                .font(.system(size: 12))
                                .foregroundColor(Color(hex: "#e8d5b7")).lineLimit(1)
                        }
                        ForEach(lens.openPromises.prefix(2)) { p in
                            Text("· 對 \(p.to)：\(p.content)")
                                .font(.system(size: 12))
                                .foregroundColor(Color(hex: "#e8d5b7")).lineLimit(1)
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
        }
    }

    // MARK: - Helpers
    func statusRow(icon: String, text: String, color: String) -> some View {
        HStack(spacing: 8) {
            Image(systemName: icon).foregroundColor(Color(hex: color)).font(.system(size: 14))
            Text(text).font(.system(size: 14)).foregroundColor(Color(hex: "#e8d5b7"))
            Spacer()
        }
    }

    func placeholderText(_ text: String) -> some View {
        Text(text).font(.system(size: 13)).foregroundColor(Color(hex: "#c9a84c40")).italic()
            .frame(maxWidth: .infinity, alignment: .leading)
    }
}

struct OfficeCard<Content: View>: View {
    let icon: String
    let title: String
    @ViewBuilder let content: () -> Content

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 8) {
                Image(systemName: icon)
                    .foregroundColor(Color(hex: "#c9a84c")).font(.system(size: 14, weight: .medium))
                Text(title)
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundColor(Color(hex: "#c9a84c")).kerning(0.8)
            }
            content()
        }
        .padding(16)
        .background(Color(hex: "#13110e"))
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(Color(hex: "#c9a84c20"), lineWidth: 1))
        .cornerRadius(12)
    }
}
```

---

## 四、唯一需要手動修改的檔案：AlfredView.swift

路徑：`Features/Chat/AlfredView.swift`

### 改動 1：在第 8 行 `@State private var isPressing` 下面加一行

找到：
```swift
@State private var isPressing = false
```
改成：
```swift
@State private var isPressing = false
@State private var showOffice = false
```

### 改動 2：在 `.onAppear { vm.onAppear() }` 後面加三個 modifier

找到：
```swift
.onAppear { vm.onAppear() }
```
改成：
```swift
.onAppear { vm.onAppear() }
.sheet(isPresented: $showOffice) {
    OfficeDashboardView()
}
.overlay(alignment: .bottomTrailing) {
    Button(action: { showOffice = true }) {
        Image(systemName: "building.2")
            .font(.system(size: 18, weight: .medium))
            .foregroundColor(Color(hex: "#c9a84c"))
            .frame(width: 44, height: 44)
            .background(Color(hex: "#c9a84c15"))
            .overlay(Circle().stroke(Color(hex: "#c9a84c40"), lineWidth: 1))
            .clipShape(Circle())
    }
    .padding(.trailing, 24)
    .padding(.bottom, 60)
}
```

---

## 五、Build 後預期結果

- 主畫面右下角出現小建築圖示（`building.2`）
- 點開後是辦公室儀表板，五張卡片：下班收尾、會議室感知、感謝提醒、耗材庫存、團隊狀態
- 登入後資料會從後端即時載入
- 未登入時所有卡片顯示「載入中…」（API 回 401，資料為空）

## 六、常見問題

**Q：Color(hex:) 找不到**
A：已在 `AlfredView.swift` 定義，整個 module 都可用，不需要重複定義。

**Q：AuthManager 找不到**
A：在 `Core/AuthManager.swift`，確認 Office 資料夾的檔案有加入 target。

**Q：build 成功但資料都空**
A：需要先登入（LoginView），token 存在 Keychain 後 API 才能過驗證。

