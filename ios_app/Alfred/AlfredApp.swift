import SwiftUI

@main
struct AlfredApp: App {
    @StateObject private var locationManager = LocationManager.shared

    var body: some Scene {
        WindowGroup {
            AlfredView()
                .preferredColorScheme(.dark)
                .onReceive(NotificationCenter.default.publisher(for: UIApplication.didBecomeActiveNotification)) { _ in
                    // App 進前景 → 檢查情境（到辦公室/到家）
                    Task { await LocationManager.shared.checkContext() }
                }
        }
    }
}
