import SwiftUI

struct AttendanceView: View {
    @Environment(\.dismiss) private var dismiss
    @State private var records: [AttendanceRecord] = []
    @State private var isLoading = true
    @StateObject private var vm = AlfredViewModel.shared

    var body: some View {
        NavigationStack {
            ZStack {
                Color(hex: "#090909").ignoresSafeArea()
                ScrollView(showsIndicators: false) {
                    VStack(spacing: 16) {
                        todayCard
                        weekCard
                        chatHintCard
                        Spacer().frame(height: 24)
                    }
                    .padding(.horizontal, 16).padding(.top, 8)
                }
            }
            .navigationTitle("出勤")
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
        .task { await loadRecords() }
    }

    var today: AttendanceRecord? { records.first { $0.date == todayStr } }
    var todayStr: String {
        let f = DateFormatter(); f.dateFormat = "yyyy-MM-dd"; return f.string(from: Date())
    }

    // MARK: - Today
    var todayCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 8) {
                Image(systemName: "clock.badge.checkmark").foregroundColor(Color(hex: "#c9a84c"))
                    .font(.system(size: 14, weight: .medium))
                Text("今日出勤").font(.system(size: 13, weight: .semibold))
                    .foregroundColor(Color(hex: "#c9a84c")).kerning(0.8)
            }
            if let rec = today {
                HStack(spacing: 24) {
                    statBox(label: "上班", value: rec.checkIn ?? "--:--")
                    statBox(label: "下班", value: rec.checkOut ?? "--")
                    statBox(label: "類型", value: typeLabel(rec.type))
                    if let dur = rec.durationMin {
                        statBox(label: "時數", value: String(format: "%.1fh", Double(dur)/60.0))
                    }
                }
                if let addr = rec.addressIn {
                    HStack(spacing: 6) {
                        Image(systemName: "location").font(.system(size: 11))
                            .foregroundColor(Color(hex: "#c9a84c60"))
                        Text(addr).font(.system(size: 12))
                            .foregroundColor(Color(hex: "#c9a84c60")).lineLimit(1)
                    }
                }
            } else if isLoading {
                Text("載入中…").font(.system(size: 13)).foregroundColor(Color(hex: "#c9a84c40")).italic()
            } else {
                VStack(spacing: 8) {
                    Text("今天尚未打卡").font(.system(size: 14))
                        .foregroundColor(Color(hex: "#e8d5b7b0"))
                    Text("跟阿福說「上班打卡」或「進公司了」")
                        .font(.system(size: 12)).foregroundColor(Color(hex: "#c9a84c60"))
                }
                .frame(maxWidth: .infinity)
            }
        }
        .padding(16)
        .background(Color(hex: "#13110e"))
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(Color(hex: "#c9a84c20"), lineWidth: 1))
        .cornerRadius(12)
    }

    // MARK: - Week
    var weekCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 8) {
                Image(systemName: "calendar").foregroundColor(Color(hex: "#c9a84c"))
                    .font(.system(size: 14, weight: .medium))
                Text("本週").font(.system(size: 13, weight: .semibold))
                    .foregroundColor(Color(hex: "#c9a84c")).kerning(0.8)
            }
            let week = weekRecords()
            if week.isEmpty {
                Text("本週尚無出勤記錄").font(.system(size: 13))
                    .foregroundColor(Color(hex: "#c9a84c40")).italic()
            } else {
                ForEach(week) { rec in
                    HStack {
                        Text(shortDate(rec.date)).font(.system(size: 13))
                            .foregroundColor(Color(hex: "#e8d5b7")).frame(width: 64, alignment: .leading)
                        Text(typeLabel(rec.type)).font(.system(size: 12))
                            .foregroundColor(typeColor(rec.type))
                            .padding(.horizontal, 8).padding(.vertical, 2)
                            .background(typeColor(rec.type).opacity(0.12))
                            .cornerRadius(4)
                        Spacer()
                        if let ci = rec.checkIn, let co = rec.checkOut {
                            Text("\(ci.prefix(5)) – \(co.prefix(5))")
                                .font(.system(size: 12)).foregroundColor(Color(hex: "#c9a84c80"))
                        } else if let ci = rec.checkIn {
                            Text("\(ci.prefix(5)) –").font(.system(size: 12))
                                .foregroundColor(Color(hex: "#c9a84c80"))
                        }
                    }
                }
            }
        }
        .padding(16)
        .background(Color(hex: "#13110e"))
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(Color(hex: "#c9a84c20"), lineWidth: 1))
        .cornerRadius(12)
    }

    // MARK: - Chat hint
    var chatHintCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("可以直接跟阿福說").font(.system(size: 12, weight: .medium))
                .foregroundColor(Color(hex: "#c9a84c60")).kerning(0.5)
            ForEach(["上班打卡", "下班了", "今天在家辦公", "請假一天", "查我這週出勤"], id: \.self) { hint in
                Button(action: { sendHint(hint) }) {
                    HStack {
                        Text("「\(hint)」").font(.system(size: 13))
                            .foregroundColor(Color(hex: "#e8d5b7"))
                        Spacer()
                        Image(systemName: "chevron.right").font(.system(size: 11))
                            .foregroundColor(Color(hex: "#c9a84c40"))
                    }
                    .padding(.vertical, 8).padding(.horizontal, 12)
                    .background(Color(hex: "#c9a84c08"))
                    .cornerRadius(8)
                }
            }
        }
        .padding(16)
        .background(Color(hex: "#13110e"))
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(Color(hex: "#c9a84c20"), lineWidth: 1))
        .cornerRadius(12)
    }

    // MARK: - Helpers
    func statBox(label: String, value: String) -> some View {
        VStack(spacing: 4) {
            Text(value).font(.system(size: 18, weight: .light)).foregroundColor(Color(hex: "#e8d5b7"))
            Text(label).font(.system(size: 10)).foregroundColor(Color(hex: "#c9a84c60")).kerning(0.5)
        }
    }

    func typeLabel(_ type: String?) -> String {
        switch type {
        case "office": return "進公司"
        case "wfh":    return "居家辦公"
        case "leave":  return "請假"
        default:       return type ?? "--"
        }
    }

    func typeColor(_ type: String?) -> Color {
        switch type {
        case "office": return Color(hex: "#4CAF50")
        case "wfh":    return Color(hex: "#2196F3")
        case "leave":  return Color(hex: "#FF9800")
        default:       return Color(hex: "#c9a84c")
        }
    }

    func shortDate(_ str: String) -> String {
        let f = DateFormatter(); f.dateFormat = "yyyy-MM-dd"
        guard let d = f.date(from: str) else { return str }
        let f2 = DateFormatter(); f2.dateFormat = "E M/d"; f2.locale = Locale(identifier: "zh_TW")
        return f2.string(from: d)
    }

    func weekRecords() -> [AttendanceRecord] {
        let cal = Calendar.current
        let start = cal.date(from: cal.dateComponents([.yearForWeekOfYear, .weekOfYear], from: Date()))!
        let f = DateFormatter(); f.dateFormat = "yyyy-MM-dd"
        return records.filter {
            guard let d = f.date(from: $0.date) else { return false }
            return d >= start
        }.sorted { $0.date > $1.date }
    }

    func sendHint(_ text: String) {
        dismiss()
        Task {
            try? await Task.sleep(nanoseconds: 300_000_000)
            await vm.sendMessage(text)
        }
    }

    func loadRecords() async {
        let req = AuthManager.shared.authorizedRequest(path: "/api/attendance/history")
        if let (data, _) = try? await URLSession.shared.data(for: req),
           let arr = try? JSONDecoder().decode([AttendanceRecord].self, from: data) {
            records = arr
        }
        isLoading = false
    }
}

// MARK: - Model
struct AttendanceRecord: Decodable, Identifiable {
    let date: String
    let checkIn: String?
    let checkOut: String?
    let type: String?
    let durationMin: Int?
    let addressIn: String?
    var id: String { date }
    enum CodingKeys: String, CodingKey {
        case date
        case checkIn    = "check_in"
        case checkOut   = "check_out"
        case type
        case durationMin = "duration_min"
        case addressIn  = "address_in"
    }
}
