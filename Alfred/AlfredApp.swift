import SwiftUI

@main
struct AlfredApp: App {
    @StateObject private var locationManager = LocationManager.shared
    @StateObject private var backgroundManager = BackgroundManager.shared
    @StateObject private var healthKit = HealthKitManager.shared
    @Environment(\.scenePhase) private var scenePhase

    var body: some Scene {
        WindowGroup {
            AlfredView()
                .onAppear {
                    // onboarding 完成前不啟動任何背景任務，避免搶話
                    if UserDefaults.standard.bool(forKey: "alfred_onboarded") {
                        backgroundManager.start()
                        Task { await healthKit.requestPermissions() }
                    }
                }
                .preferredColorScheme(.dark)
        }
        .onChange(of: scenePhase) { _, phase in
            BackgroundManager.shared.isAppActive = (phase == .active)
            if phase == .active && UserDefaults.standard.bool(forKey: "alfred_onboarded") {
                Task { await LocationManager.shared.checkContext() }
            }
        }
    }
}
