import CoreLocation
import Foundation
import Combine

// MARK: - Location Manager
// 背景 GPS 持續上傳到後端

@MainActor
class LocationManager: NSObject, ObservableObject, CLLocationManagerDelegate {
    static let shared = LocationManager()

    private let manager = CLLocationManager()
    private var batch: [[String: Any]] = []
    private var lastUpload = Date()
    @Published private(set) var isTracking = false
    @Published private(set) var lastError: String? = nil
    @Published private(set) var lastCoordinate: CLLocationCoordinate2D? = nil

    override init() {
        super.init()
        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyHundredMeters
        // 只在 Info.plist 宣告了 location background mode 才開背景更新，否則 CoreLocation 會 throw
        let bgModes = Bundle.main.object(forInfoDictionaryKey: "UIBackgroundModes") as? [String] ?? []
        if bgModes.contains("location") {
            manager.allowsBackgroundLocationUpdates = true
        }
        manager.pausesLocationUpdatesAutomatically = false
    }

    func startTracking() {
        let status = manager.authorizationStatus
        switch status {
        case .notDetermined:
            manager.requestWhenInUseAuthorization()
        case .authorizedWhenInUse, .authorizedAlways:
            startLocationUpdates()
        case .denied, .restricted:
            lastError = "GPS 權限未開啟"
            isTracking = false
        @unknown default:
            lastError = "GPS 權限狀態未知"
            isTracking = false
        }
    }

    private func startLocationUpdates() {
        guard CLLocationManager.locationServicesEnabled() else {
            lastError = "系統定位服務未開啟"
            isTracking = false
            return
        }
        manager.startUpdatingLocation()
        manager.startMonitoringSignificantLocationChanges()
        isTracking = true
        lastError = nil
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
                self.lastCoordinate = loc.coordinate
                self.batch.append(point)
            }
            // 每 30 秒或累積 10 點上傳一次
            if Date().timeIntervalSince(self.lastUpload) > 30 || self.batch.count >= 10 {
                await self.flush()
            }
        }
    }

    nonisolated func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        Task { @MainActor in
            switch manager.authorizationStatus {
            case .authorizedWhenInUse, .authorizedAlways:
                self.startLocationUpdates()
            case .denied, .restricted:
                self.lastError = "GPS 權限未開啟"
                self.isTracking = false
            case .notDetermined:
                break
            @unknown default:
                self.lastError = "GPS 權限狀態未知"
                self.isTracking = false
            }
        }
    }

    nonisolated func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        Task { @MainActor in
            self.lastError = error.localizedDescription
            self.isTracking = false
        }
    }

    // MARK: - Upload
    func flush() async {
        guard !batch.isEmpty else { return }
        let toUpload = batch
        batch = []
        lastUpload = Date()
        do {
            try await AlfredAPI.shared.uploadLocation(points: toUpload)
            lastError = nil
        } catch {
            lastError = error.localizedDescription
            batch = toUpload + batch
        }
    }

    // MARK: - Context check（到辦公室/到家）
    func checkContext(announce: Bool = false) async {
        do {
            let ctx = try await AlfredAPI.shared.locationContext()
            if announce, !ctx.greeting.isEmpty {
                await AlfredViewModel.shared.showAndSpeakContext(ctx.greeting)
            }
            await AlfredViewModel.shared.preloadSceneMode(context: ctx, announce: false)
        } catch {}
    }
}
