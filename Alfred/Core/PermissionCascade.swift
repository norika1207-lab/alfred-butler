import Foundation
import AVFoundation
import CoreLocation
import Photos
import Contacts
import HealthKit
import UserNotifications
import UIKit

/// 一次性權限引導 cascade（首次啟動跑一次）
/// 設計：零介面 — 只用 iOS 系統原生權限對話框 + 阿福聲音串場
/// 對應 Info.plist 已寫好的 NSUsageDescription，符合 App Store 5.5.x
/// 一次跑完所有權限，避免用戶用到功能時才被打斷
@MainActor
final class PermissionCascade {

    private static let kDoneKey = "alfred_permission_cascade_done_v1"

    /// 主入口（idempotent — 第二次以後直接 return）
    static func runIfNeeded() async {
        guard !UserDefaults.standard.bool(forKey: kDoneKey) else { return }

        // 開場（短，不要勸退）
        await AlfredViewModel.shared.speakAloud("主人，請允許接下來幾個權限，這樣我才能完整服務您。")
        try? await Task.sleep(nanoseconds: 600_000_000)

        // 依序請求（每個 await 用戶按完才往下）
        _ = await requestMicrophone()
        _ = await requestNotifications()
        _ = await requestLocationWhenInUse()
        try? await Task.sleep(nanoseconds: 800_000_000)
        _ = await requestLocationAlways()
        LocationManager.shared.startTracking()
        _ = await requestHealthKit()
        _ = await requestPhotos()
        _ = await requestCamera()
        _ = await requestContacts()

        UserDefaults.standard.set(true, forKey: kDoneKey)

        try? await Task.sleep(nanoseconds: 400_000_000)
        await AlfredViewModel.shared.speakAloud("好了，我準備好聽您的吩咐。")
    }

    // MARK: - 各權限請求（async wrap）

    private static func requestMicrophone() async -> Bool {
        await withCheckedContinuation { (cont: CheckedContinuation<Bool, Never>) in
            if #available(iOS 17.0, *) {
                AVAudioApplication.requestRecordPermission { granted in
                    cont.resume(returning: granted)
                }
            } else {
                AVAudioSession.sharedInstance().requestRecordPermission { granted in
                    cont.resume(returning: granted)
                }
            }
        }
    }

    private static func requestNotifications() async -> Bool {
        do {
            return try await UNUserNotificationCenter.current()
                .requestAuthorization(options: [.alert, .sound, .badge])
        } catch {
            return false
        }
    }

    private static func requestLocationWhenInUse() async -> Bool {
        await LocationCascadeWaiter.shared.request(.whenInUse)
    }

    private static func requestLocationAlways() async -> Bool {
        await LocationCascadeWaiter.shared.request(.always)
    }

    private static func requestHealthKit() async -> Bool {
        await HealthKitManager.shared.requestPermissions()
        return true
    }

    private static func requestPhotos() async -> Bool {
        let status = await PHPhotoLibrary.requestAuthorization(for: .readWrite)
        return status == .authorized || status == .limited
    }

    private static func requestCamera() async -> Bool {
        await withCheckedContinuation { (cont: CheckedContinuation<Bool, Never>) in
            AVCaptureDevice.requestAccess(for: .video) { granted in
                cont.resume(returning: granted)
            }
        }
    }

    private static func requestContacts() async -> Bool {
        await withCheckedContinuation { (cont: CheckedContinuation<Bool, Never>) in
            CNContactStore().requestAccess(for: .contacts) { granted, _ in
                cont.resume(returning: granted)
            }
        }
    }
}

/// CLLocationManager 沒有 completion handler，必須走 delegate；
/// 用 continuation + 8s 防呆超時
private final class LocationCascadeWaiter: NSObject, CLLocationManagerDelegate {
    static let shared = LocationCascadeWaiter()

    enum Mode { case whenInUse, always }

    private let manager = CLLocationManager()
    private var continuation: CheckedContinuation<Bool, Never>?

    override init() {
        super.init()
        manager.delegate = self
    }

    func request(_ mode: Mode) async -> Bool {
        await withCheckedContinuation { (cont: CheckedContinuation<Bool, Never>) in
            self.continuation = cont
            switch mode {
            case .whenInUse: manager.requestWhenInUseAuthorization()
            case .always:    manager.requestAlwaysAuthorization()
            }
            // 8 秒沒回應放掉
            DispatchQueue.main.asyncAfter(deadline: .now() + 8) { [weak self] in
                guard let self else { return }
                if let c = self.continuation {
                    self.continuation = nil
                    c.resume(returning: false)
                }
            }
        }
    }

    func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        if let c = continuation {
            continuation = nil
            let status = manager.authorizationStatus
            let granted = (status == .authorizedAlways || status == .authorizedWhenInUse)
            c.resume(returning: granted)
        }
    }
}
