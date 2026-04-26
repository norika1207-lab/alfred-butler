import SwiftUI

struct FamilyView: View {
    @StateObject private var bg = BackgroundManager.shared
    @Environment(\.dismiss) private var dismiss
    @State private var alerts: [FamilyAlert] = []

    var body: some View {
        NavigationStack {
            ZStack {
                Color(hex: "#090909").ignoresSafeArea()
                ScrollView(showsIndicators: false) {
                    VStack(spacing: 16) {
                        if !alerts.isEmpty { alertsSection }
                        membersSection
                        Spacer().frame(height: 24)
                    }
                    .padding(.horizontal, 16)
                    .padding(.top, 8)
                }
            }
            .navigationTitle("家人")
            .navigationBarTitleDisplayMode(.inline)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button(action: { dismiss() }) {
                        Image(systemName: "xmark").foregroundColor(Color(hex: "#c9a84c"))
                    }
                }
            }
        }
        .task { await loadAlerts() }
    }

    // MARK: - Alerts
    var alertsSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 8) {
                Image(systemName: "exclamationmark.triangle.fill")
                    .foregroundColor(Color(hex: "#FF6B6B")).font(.system(size: 13))
                Text("警報").font(.system(size: 13, weight: .semibold))
                    .foregroundColor(Color(hex: "#FF6B6B")).kerning(0.8)
            }
            ForEach(alerts) { alert in
                HStack(alignment: .top, spacing: 12) {
                    Circle()
                        .fill(alert.severity == "critical" ? Color(hex: "#FF6B6B") : Color(hex: "#FF9800"))
                        .frame(width: 8, height: 8)
                        .padding(.top, 5)
                    VStack(alignment: .leading, spacing: 3) {
                        Text(alert.name)
                            .font(.system(size: 14, weight: .semibold))
                            .foregroundColor(Color(hex: "#e8d5b7"))
                        Text(alert.message)
                            .font(.system(size: 13))
                            .foregroundColor(Color(hex: "#e8d5b7b0"))
                    }
                }
                .padding(12)
                .background(Color(hex: "#FF6B6B10"))
                .overlay(RoundedRectangle(cornerRadius: 10)
                    .stroke(Color(hex: "#FF6B6B30"), lineWidth: 1))
                .cornerRadius(10)
            }
        }
        .padding(16)
        .background(Color(hex: "#13110e"))
        .overlay(RoundedRectangle(cornerRadius: 12)
            .stroke(Color(hex: "#FF6B6B30"), lineWidth: 1))
        .cornerRadius(12)
    }

    // MARK: - Members
    var membersSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 8) {
                Image(systemName: "person.3").foregroundColor(Color(hex: "#c9a84c"))
                    .font(.system(size: 14, weight: .medium))
                Text("家人位置").font(.system(size: 13, weight: .semibold))
                    .foregroundColor(Color(hex: "#c9a84c")).kerning(0.8)
            }
            if bg.familyMembers.isEmpty {
                Text("跟阿福說「新增家人 OO」開始追蹤")
                    .font(.system(size: 13)).foregroundColor(Color(hex: "#c9a84c40")).italic()
            } else {
                ForEach(bg.familyMembers) { member in
                    memberRow(member)
                    if member.id != bg.familyMembers.last?.id {
                        Divider().background(Color(hex: "#c9a84c15"))
                    }
                }
            }
        }
        .padding(16)
        .background(Color(hex: "#13110e"))
        .overlay(RoundedRectangle(cornerRadius: 12)
            .stroke(Color(hex: "#c9a84c20"), lineWidth: 1))
        .cornerRadius(12)
    }

    func memberRow(_ member: FamilyMember) -> some View {
        HStack(spacing: 12) {
            // 頭像
            Circle()
                .fill(Color(hex: "#c9a84c20"))
                .overlay(Text(String(member.name.prefix(1)))
                    .font(.system(size: 16, weight: .medium))
                    .foregroundColor(Color(hex: "#c9a84c")))
                .frame(width: 40, height: 40)

            VStack(alignment: .leading, spacing: 3) {
                HStack {
                    Text(member.name)
                        .font(.system(size: 15, weight: .medium))
                        .foregroundColor(Color(hex: "#e8d5b7"))
                    if member.isHome {
                        Text("在家").font(.system(size: 10, weight: .medium))
                            .foregroundColor(Color(hex: "#4CAF50"))
                            .padding(.horizontal, 6).padding(.vertical, 2)
                            .background(Color(hex: "#4CAF5020"))
                            .cornerRadius(4)
                    }
                }
                Text(member.address ?? "位置未知")
                    .font(.system(size: 12))
                    .foregroundColor(Color(hex: "#c9a84c80"))
                    .lineLimit(1)
                if let seen = member.lastSeen {
                    Text(relativeTime(seen))
                        .font(.system(size: 11))
                        .foregroundColor(Color(hex: "#e8d5b740"))
                }
            }

            Spacer()

            if let battery = member.battery {
                VStack(spacing: 2) {
                    Image(systemName: batteryIcon(battery))
                        .font(.system(size: 14))
                        .foregroundColor(battery < 20 ? Color(hex: "#FF6B6B") : Color(hex: "#c9a84c60"))
                    Text("\(battery)%")
                        .font(.system(size: 10))
                        .foregroundColor(Color(hex: "#e8d5b740"))
                }
            }
        }
    }

    func batteryIcon(_ pct: Int) -> String {
        switch pct {
        case 75...: return "battery.100"
        case 50...: return "battery.75"
        case 25...: return "battery.25"
        default:   return "battery.0"
        }
    }

    func relativeTime(_ iso: String) -> String {
        let f = ISO8601DateFormatter()
        guard let date = f.date(from: iso) else { return iso }
        let diff = Int(Date().timeIntervalSince(date))
        if diff < 60 { return "剛剛" }
        if diff < 3600 { return "\(diff/60) 分鐘前" }
        if diff < 86400 { return "\(diff/3600) 小時前" }
        return "\(diff/86400) 天前"
    }

    func loadAlerts() async {
        alerts = (try? await AlfredAPI.shared.familyAlerts()) ?? []
    }
}
