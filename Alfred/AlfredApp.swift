import SwiftUI

private let kConsentKey = "alfred_ai_consent_v1"

@main
struct AlfredApp: App {
    @StateObject private var locationManager = LocationManager.shared
    @StateObject private var backgroundManager = BackgroundManager.shared
    @StateObject private var healthKit = HealthKitManager.shared
    @Environment(\.scenePhase) private var scenePhase
    @State private var consentGiven = UserDefaults.standard.bool(forKey: kConsentKey)

    var body: some Scene {
        WindowGroup {
            Group {
                if consentGiven {
                    AlfredView()
                        .onAppear { startIfOnboarded() }
                } else {
                    ConsentView {
                        UserDefaults.standard.set(true, forKey: kConsentKey)
                        consentGiven = true
                    }
                }
            }
            .preferredColorScheme(.dark)
        }
        .onChange(of: scenePhase) { _, phase in
            BackgroundManager.shared.isAppActive = (phase == .active)
            if phase == .active && UserDefaults.standard.bool(forKey: "alfred_onboarded") {
                LocationManager.shared.startTracking()
                Task { await LocationManager.shared.checkContext() }
            }
        }
    }

    private func startIfOnboarded() {
        let args = CommandLine.arguments
        if args.contains("--reset") {
            UserDefaults.standard.removeObject(forKey: "alfred_onboarded")
            AlfredAPI.shared.token = nil
            NSLog("[Alfred] UI test mode --reset (cleared onboarded + token)")
        }
        if let idx = args.firstIndex(of: "--prompt"), idx + 1 < args.count {
            let prompt = args[idx + 1]
            if !args.contains("--reset") {
                UserDefaults.standard.set(true, forKey: "alfred_onboarded")
            }
            NSLog("[Alfred] UI test mode prompt: %@", prompt)
            Task {
                try? await Task.sleep(nanoseconds: 2_000_000_000)
                await AlfredViewModel.shared.sendMessage(prompt)
            }
        }

        if UserDefaults.standard.bool(forKey: "alfred_onboarded") {
            backgroundManager.start()
            LocationManager.shared.startTracking()
            Task { await healthKit.requestPermissions() }
        }
    }
}
