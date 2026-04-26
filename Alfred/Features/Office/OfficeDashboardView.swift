import SwiftUI

struct OfficeDashboardView: View {
    @StateObject private var vm = OfficeViewModel.shared
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            ZStack {
                Color(hex: "#090909").ignoresSafeArea()
                if vm.isLoading {
                    ProgressView().tint(Color(hex: "#c9a84c"))
                } else {
                    ScrollView {
                        VStack(spacing: 16) {
                            EodCard(items: vm.eodItems)
                            RoomPulseCard(rooms: vm.roomPulse)
                            ThanksCard(nudge: vm.thanksNudge)
                            SuppliesCard(items: vm.supplies)
                            TeamCard(colleagues: vm.colleagues)
                        }
                        .padding(16)
                    }
                }
            }
            .navigationTitle("辦公室")
            .navigationBarTitleDisplayMode(.inline)
            .toolbarBackground(Color(hex: "#090909"), for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("關閉") { dismiss() }
                        .foregroundColor(Color(hex: "#c9a84c"))
                }
            }
            .task { await vm.reload() }
        }
    }
}

// MARK: - 下班收尾

private struct EodCard: View {
    let items: [EodItem]

    var body: some View {
        OfficeCard(title: "下班收尾", icon: "checklist") {
            if items.isEmpty {
                Text("今日收尾清單尚未建立").officeSubtext()
            } else {
                ForEach(items) { item in
                    HStack(spacing: 10) {
                        Image(systemName: item.done ? "checkmark.circle.fill" : "circle")
                            .foregroundColor(item.done ? Color(hex: "#c9a84c") : Color(hex: "#e8d5b740"))
                            .font(.system(size: 16))
                        VStack(alignment: .leading, spacing: 2) {
                            Text(item.title)
                                .font(.system(size: 14))
                                .foregroundColor(item.done ? Color(hex: "#e8d5b760") : Color(hex: "#e8d5b7"))
                                .strikethrough(item.done)
                            if let note = item.note {
                                Text(note).font(.system(size: 11)).foregroundColor(Color(hex: "#c9a84c80"))
                            }
                        }
                        Spacer()
                    }
                    .padding(.vertical, 4)
                }
            }
        }
    }
}

// MARK: - 會議室感知

private struct RoomPulseCard: View {
    let rooms: [RoomStatus]

    var body: some View {
        OfficeCard(title: "會議室感知", icon: "door.left.hand.open") {
            if rooms.isEmpty {
                Text("暫無會議室資料").officeSubtext()
            } else {
                ForEach(rooms) { room in
                    HStack {
                        Circle()
                            .fill(room.occupied ? Color.red.opacity(0.7) : Color(hex: "#c9a84c").opacity(0.7))
                            .frame(width: 8, height: 8)
                        Text(room.name)
                            .font(.system(size: 14))
                            .foregroundColor(Color(hex: "#e8d5b7"))
                        Spacer()
                        if room.occupied, let until = room.until {
                            Text("佔用至 \(until)")
                                .font(.system(size: 11))
                                .foregroundColor(Color(hex: "#e8d5b760"))
                        } else {
                            Text("空閒")
                                .font(.system(size: 11))
                                .foregroundColor(Color(hex: "#c9a84c"))
                        }
                    }
                    .padding(.vertical, 5)
                }
            }
        }
    }
}

// MARK: - 感謝提醒

private struct ThanksCard: View {
    let nudge: ThanksNudge?

    var body: some View {
        OfficeCard(title: "感謝提醒", icon: "heart") {
            if let n = nudge, let person = n.person {
                VStack(alignment: .leading, spacing: 6) {
                    Text("\(person) 上次幫過你")
                        .font(.system(size: 14))
                        .foregroundColor(Color(hex: "#e8d5b7"))
                    if let reason = n.reason {
                        Text(reason)
                            .font(.system(size: 12))
                            .foregroundColor(Color(hex: "#e8d5b780"))
                    }
                    if let days = n.daysAgo {
                        Text("已過 \(days) 天，還沒說謝謝")
                            .font(.system(size: 11))
                            .foregroundColor(Color(hex: "#c9a84c"))
                    }
                }
            } else {
                Text("最近都有好好說謝謝").officeSubtext()
            }
        }
    }
}

// MARK: - 耗材庫存

private struct SuppliesCard: View {
    let items: [SupplyItem]

    var levelColor: (String) -> Color = { level in
        switch level {
        case "critical": return .red
        case "low":      return .orange
        default:         return Color(hex: "#c9a84c")
        }
    }

    var body: some View {
        OfficeCard(title: "耗材庫存", icon: "shippingbox") {
            if items.isEmpty {
                Text("暫無耗材資料").officeSubtext()
            } else {
                ForEach(items) { item in
                    HStack {
                        Text(item.name)
                            .font(.system(size: 14))
                            .foregroundColor(Color(hex: "#e8d5b7"))
                        Spacer()
                        Text(item.level == "ok" ? "充足" : item.level == "low" ? "偏少" : "快沒了")
                            .font(.system(size: 12, weight: .medium))
                            .foregroundColor(levelColor(item.level))
                    }
                    .padding(.vertical, 4)
                }
            }
        }
    }
}

// MARK: - 團隊狀態

private struct TeamCard: View {
    let colleagues: [ColleagueStatus]

    var statusIcon: (String) -> String = { s in
        switch s {
        case "in-office": return "building.2"
        case "wfh":       return "house"
        default:          return "moon.zzz"
        }
    }

    var body: some View {
        OfficeCard(title: "團隊狀態", icon: "person.3") {
            if colleagues.isEmpty {
                Text("暫無同事資料").officeSubtext()
            } else {
                ForEach(colleagues) { c in
                    HStack(spacing: 10) {
                        Image(systemName: statusIcon(c.status))
                            .font(.system(size: 13))
                            .foregroundColor(Color(hex: "#c9a84c80"))
                            .frame(width: 20)
                        Text(c.name)
                            .font(.system(size: 14))
                            .foregroundColor(Color(hex: "#e8d5b7"))
                        Spacer()
                        if let mood = c.mood {
                            Text(mood).font(.system(size: 14))
                        }
                    }
                    .padding(.vertical, 4)
                }
            }
        }
    }
}

// MARK: - 共用 Card 容器

private struct OfficeCard<Content: View>: View {
    let title: String
    let icon: String
    @ViewBuilder let content: Content

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 8) {
                Image(systemName: icon)
                    .font(.system(size: 13, weight: .medium))
                    .foregroundColor(Color(hex: "#c9a84c"))
                Text(title)
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundColor(Color(hex: "#c9a84c"))
                    .kerning(0.5)
            }
            content
        }
        .padding(16)
        .background(Color(hex: "#13110e"))
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(Color(hex: "#c9a84c20"), lineWidth: 1))
        .cornerRadius(12)
    }
}

private extension Text {
    func officeSubtext() -> some View {
        self.font(.system(size: 13))
            .foregroundColor(Color(hex: "#e8d5b740"))
            .italic()
    }
}
