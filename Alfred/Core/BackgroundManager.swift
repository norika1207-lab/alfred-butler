import Foundation
import Combine
import UserNotifications

// MARK: - Background Manager
// 提醒輪詢（60 秒）+ 家人警報（30 秒）+ 拜訪前提醒（30 分）

@MainActor
class BackgroundManager: ObservableObject {
    static let shared = BackgroundManager()

    @Published var familyMembers: [FamilyMember] = []
    var isAppActive: Bool = false

    private var reminderTask: Task<Void, Never>?
    private var alertTask: Task<Void, Never>?
    private var visitTask: Task<Void, Never>?
    private var familyTask: Task<Void, Never>?
    private var acknowledgedAlerts: Set<Int> = []

    func start() {
        requestNotificationPermission()
        startReminderPolling()
        startAlertPolling()
        startVisitPolling()
        startFamilyPolling()
    }

    func stop() {
        reminderTask?.cancel()
        alertTask?.cancel()
        visitTask?.cancel()
        familyTask?.cancel()
    }

    // MARK: - 提醒輪詢（60 秒）
    private func startReminderPolling() {
        reminderTask = Task {
            while !Task.isCancelled {
                await pollReminders()
                try? await Task.sleep(nanoseconds: 60_000_000_000)
            }
        }
    }

    private func pollReminders() async {
        do {
            let reminders = try await AlfredAPI.shared.pendingReminders()
            for reminder in reminders {
                scheduleLocalNotification(
                    id: "reminder-\(reminder.id)",
                    title: "阿福提醒",
                    body: reminder.title,
                    triggerAt: reminder.triggerAt
                )
            }
        } catch {
            print("[BackgroundManager] reminder poll error:", error)
        }
    }

    // MARK: - 家人警報（30 秒）
    private func startAlertPolling() {
        alertTask = Task {
            while !Task.isCancelled {
                await pollFamilyAlerts()
                try? await Task.sleep(nanoseconds: 30_000_000_000)
            }
        }
    }

    private func pollFamilyAlerts() async {
        do {
            let alerts = try await AlfredAPI.shared.familyAlerts()
            for alert in alerts {
                guard !acknowledgedAlerts.contains(alert.id) else { continue }
                acknowledgedAlerts.insert(alert.id)

                if isAppActive {
                    // App 在前景：阿福主畫面直接開口說
                    await AlfredViewModel.shared.speakAloud(alert.message)
                } else {
                    // 背景：推播通知
                    fireImmediateNotification(
                        id: "alert-\(alert.id)",
                        title: alert.severity == "critical" ? "🚨 \(alert.name)" : "⚠️ \(alert.name)",
                        body: alert.message
                    )
                }
                try? await AlfredAPI.shared.ackAlert(id: alert.id)
            }
        } catch {
            print("[BackgroundManager] alert poll error:", error)
        }
    }

    // MARK: - 家人位置（60 秒）
    private func startFamilyPolling() {
        familyTask = Task {
            while !Task.isCancelled {
                await pollFamilyMembers()
                try? await Task.sleep(nanoseconds: 60_000_000_000)
            }
        }
    }

    private func pollFamilyMembers() async {
        do {
            let members = try await AlfredAPI.shared.familyMembers()
            familyMembers = members
        } catch {
            print("[BackgroundManager] family members poll error:", error)
        }
    }

    // MARK: - 拜訪前提醒（30 分）
    private func startVisitPolling() {
        visitTask = Task {
            while !Task.isCancelled {
                await pollVisitPrep()
                try? await Task.sleep(nanoseconds: 1_800_000_000_000)
            }
        }
    }

    private func pollVisitPrep() async {
        do {
            let visits = try await AlfredAPI.shared.visitPrep()
            for visit in visits {
                fireImmediateNotification(
                    id: "visit-\(visit.eventTitle)-\(visit.minutesAway)",
                    title: "拜訪提醒 · \(visit.person)",
                    body: visit.message
                )
            }
        } catch {
            print("[BackgroundManager] visit poll error:", error)
        }
    }

    // MARK: - 阿福模式透明提醒
    func scheduleAlfredModeTransparencyNotices() {
        requestNotificationPermission()
        cancelAlfredModeTransparencyNotices()
        let content = UNMutableNotificationContent()
        content.title = "阿福模式仍在開啟中"
        content.body = "主人，阿福仍在陪伴您。有聲片段才會轉成逐字稿；若要暫停，請說：阿福你先不要聽。"
        content.sound = nil
        let trigger = UNTimeIntervalNotificationTrigger(timeInterval: 2 * 3600, repeats: true)
        let request = UNNotificationRequest(identifier: alfredModeNoticeId, content: content, trigger: trigger)
        UNUserNotificationCenter.current().add(request) { err in
            if let err { print("[BackgroundManager] alfred mode notice error:", err) }
        }
    }

    func cancelAlfredModeTransparencyNotices() {
        UNUserNotificationCenter.current().removePendingNotificationRequests(withIdentifiers: [alfredModeNoticeId])
    }

    private var alfredModeNoticeId: String { "alfred-mode-notice-2h-repeat" }

    // MARK: - 通知工具
    private func requestNotificationPermission() {
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound, .badge]) { _, _ in }
    }

    private func scheduleLocalNotification(id: String, title: String, body: String, triggerAt: String) {
        let formatter = ISO8601DateFormatter()
        guard let date = formatter.date(from: triggerAt), date > Date() else { return }
        let content = UNMutableNotificationContent()
        content.title = title
        content.body = body
        content.sound = .default
        let comps = Calendar.current.dateComponents([.year, .month, .day, .hour, .minute], from: date)
        let trigger = UNCalendarNotificationTrigger(dateMatching: comps, repeats: false)
        let request = UNNotificationRequest(identifier: id, content: content, trigger: trigger)
        UNUserNotificationCenter.current().add(request) { err in
            if let err { print("[BackgroundManager] schedule error:", err) }
        }
    }

    private func fireImmediateNotification(id: String, title: String, body: String) {
        let content = UNMutableNotificationContent()
        content.title = title
        content.body = body
        content.sound = .default
        let trigger = UNTimeIntervalNotificationTrigger(timeInterval: 1, repeats: false)
        let request = UNNotificationRequest(identifier: id, content: content, trigger: trigger)
        UNUserNotificationCenter.current().add(request) { err in
            if let err { print("[BackgroundManager] fire error:", err) }
        }
    }
}
