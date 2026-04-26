import SwiftUI

@main
struct AlfredApp: App {
    @StateObject private var auth = AuthManager.shared
    @StateObject private var locationManager = LocationManager.shared
    @StateObject private var backgroundManager = BackgroundManager.shared
    @StateObject private var healthKit = HealthKitManager.shared
    @Environment(\.scenePhase) private var scenePhase

    var body: some Scene {
        WindowGroup {
            Group {
                if auth.isLoggedIn {
                    AlfredView()
                        .onAppear {
                            backgroundManager.start()
                            Task { await healthKit.requestPermissions() }
                        }
                        .onDisappear {
                            backgroundManager.stop()
                        }
                } else {
                    LoginView()
                        .onAppear {
                            backgroundManager.stop()
                        }
                }
            }
            .preferredColorScheme(.dark)
            .environmentObject(auth)
        }
        .onChange(of: scenePhase) { _, phase in
            BackgroundManager.shared.isAppActive = (phase == .active)
            if phase == .active && auth.isLoggedIn {
                Task { await LocationManager.shared.checkContext() }
            }
        }
    }
}
