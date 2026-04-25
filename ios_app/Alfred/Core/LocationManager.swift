import CoreLocation
import Foundation

// MARK: - Location Manager
// 背景 GPS 持續上傳到後端

@MainActor
class LocationManager: NSObject, ObservableObject, CLLocationManagerDelegate {
    static let shared = LocationManager()

    private let manager = CLLocationManager()
    private var batch: [[String: Any]] = []
    private var lastUpload = Date()

    override init() {
        super.init()
        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyHundredMeters
        manager.allowsBackgroundLocationUpdates = true
        manager.pausesLocationUpdatesAutomatically = false
        manager.startUpdatingLocation()
        manager.startMonitoringSignificantLocationChanges()
    }

    // MARK: - CLLocationManagerDelegate
    nonisolated func locationManager(_ manager: CLLocationManager,
                                     didUpdateLocations locations: [CLLocation]) {
        Task { @MainActor in
            for loc in locations {
                let point: [String: Any] = [
                    "lat": loc.coordinate.latitude,
                    "lng": loc.coordinate.longitude,
                    "speed": max(0, loc.speed),
                    "heading": max(0, loc.course),
                    "accuracy": loc.horizontalAccuracy,
                    "ts": ISO8601DateFormatter().string(from: loc.timestamp)
                ]
                self.batch.append(point)
            }
            // 每 30 秒或累積 10 點上傳一次
            if Date().timeIntervalSince(self.lastUpload) > 30 || self.batch.count >= 10 {
                await self.flush()
            }
        }
    }

    nonisolated func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        // 系統自動處理授權，不需要 UI
    }

    // MARK: - Upload
    func flush() async {
        guard !batch.isEmpty else { return }
        let toUpload = batch
        batch = []
        lastUpload = Date()
        try? await AlfredAPI.shared.uploadLocation(points: toUpload)
    }

    // MARK: - Context check（到辦公室/到家）
    func checkContext() async {
        do {
            let ctx = try await AlfredAPI.shared.locationContext()
            if !ctx.greeting.isEmpty {
                await AlfredViewModel.shared.showAndSpeakContext(ctx.greeting)
            }
        } catch {}
    }
}
