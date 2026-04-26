import SwiftUI

@main
struct AlfredApp: App {
    @StateObject private var auth = AuthManager.shared
    @StateObject private var locationManager = LocationManager.shared
    @StateObject private var backgroundManager = BackgroundManager.shared

    var body: some Scene {
        WindowGroup {
            Group {
                if auth.isLoggedIn {
                    AlfredView()
                        .onReceive(NotificationCenter.default.publisher(
                            for: UIApplication.didBecomeActiveNotification)) { _ in
                            Task { await LocationManager.shared.checkContext() }
                        }
                        .onAppear {
                            backgroundManager.start()
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
    }
}
