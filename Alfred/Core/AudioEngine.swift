import Foundation
import AVFoundation

@MainActor
class AudioEngine: NSObject {
    static let shared = AudioEngine()

    private var recorder: AVAudioRecorder?
    private var player: AVAudioPlayer?
    private var recordingURL: URL?
    private(set) var isRecording = false

    // 2026-05-14 加 — VAD 簡單版 audio level monitoring
    // conversational mode 用,主人講完話 1.5s 靜音自動觸發 callback。
    private var vadTask: Task<Void, Never>?
    var onSilenceDetected: (() -> Void)?  // ViewModel 設這個 callback 收 stop signal
    var silenceThresholdDb: Float = -42.0  // 環境噪音之上的閾值
    var silenceTriggerMs: Int = 1500       // 1.5s 靜音觸發
    var maxRecordDurationMs: Int = 30_000  // 30s 上限

    /// 拿當前 audio level (dB, -160 ~ 0)。錄音中才有意義。
    func currentAudioLevel() -> Float? {
        guard let r = recorder, isRecording else { return nil }
        r.updateMeters()
        return r.averagePower(forChannel: 0)
    }

    /// 啟動 VAD 監聽 (conversational mode 用)。
    /// 連續 silenceTriggerMs 靜音 → call onSilenceDetected。
    /// maxRecordDurationMs 到也會 trigger。
    func startVAD() {
        vadTask?.cancel()
        let threshold = silenceThresholdDb
        let triggerMs = silenceTriggerMs
        let maxMs = maxRecordDurationMs
        let stepMs = 100
        vadTask = Task { @MainActor [weak self] in
            // 等錄音 ramp up 0.5s 避免 mic 開啟瞬間誤觸
            try? await Task.sleep(nanoseconds: 500_000_000)
            var silenceMs = 0
            var elapsedMs = 500
            while !Task.isCancelled {
                guard let self, self.isRecording else { return }
                let level = self.currentAudioLevel() ?? -160
                if level < threshold {
                    silenceMs += stepMs
                } else {
                    silenceMs = 0  // 講話 reset
                }
                if silenceMs >= triggerMs {
                    NSLog("[VAD] silence %dms detected at level=%.1fdB, trigger stop", silenceMs, level)
                    self.onSilenceDetected?()
                    return
                }
                if elapsedMs >= maxMs {
                    NSLog("[VAD] max %dms reached, trigger stop", maxMs)
                    self.onSilenceDetected?()
                    return
                }
                try? await Task.sleep(nanoseconds: UInt64(stepMs) * 1_000_000)
                elapsedMs += stepMs
            }
        }
    }

    /// 關掉 VAD (push-to-talk 模式用,避免 VAD 跟手動 stop 撞)
    func stopVAD() {
        vadTask?.cancel()
        vadTask = nil
    }

    func startRecording() {
        #if !os(macOS)
        let session = AVAudioSession.sharedInstance()
        do {
            // 2026-05-14 統一三個 player (AudioEngine.startRecording/play + VoiceBankPlayer.play) 用同一份 session 設定
            // 避免 setCategory 切換產生的 noise burst (TTS 雜音 root cause)
            // 原設定: .playAndRecord + .measurement + .allowBluetooth (deprecated)
            // .measurement mode 對聲紋採樣有利但會 disable echo cancellation；統一改 .default 以求穩定播放
            try session.setCategory(.playAndRecord, mode: .default,
                                    options: [.defaultToSpeaker, .allowBluetoothHFP])
            try session.setActive(true)
            try session.overrideOutputAudioPort(.speaker)
        } catch {
            print("[AudioEngine] session error:", error)
            return
        }
        #endif

        // 每次錄音都存到 Documents/voice_log/，永久保留（聲紋 / 對話 review 用）
        let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        let logDir = docs.appendingPathComponent("voice_log", isDirectory: true)
        try? FileManager.default.createDirectory(at: logDir, withIntermediateDirectories: true)
        let stamp: String = {
            let f = DateFormatter()
            f.dateFormat = "yyyy-MM-dd_HH-mm-ss"
            return f.string(from: Date())
        }()
        let url = logDir.appendingPathComponent("\(stamp)_\(UUID().uuidString.prefix(8)).m4a")
        print("[AudioEngine] recording →", url.lastPathComponent)
        let settings: [String: Any] = [
            AVFormatIDKey: Int(kAudioFormatMPEG4AAC),
            AVSampleRateKey: 16000,
            AVNumberOfChannelsKey: 1,
            AVEncoderAudioQualityKey: AVAudioQuality.medium.rawValue
        ]
        do {
            recorder = try AVAudioRecorder(url: url, settings: settings)
            recorder?.isMeteringEnabled = true  // 2026-05-14 enable for VAD averagePower
            recorder?.record()
            isRecording = true
            recordingURL = url
        } catch {
            print("[AudioEngine] record error:", error)
        }
    }

    func stopPlayback() {
        player?.stop()
        player = nil
    }

    func stopRecording() -> Data? {
        stopVAD()  // 2026-05-14 ensure VAD task cancelled
        recorder?.stop()
        recorder = nil
        isRecording = false

        guard let url = recordingURL else { return nil }
        lastRecordingPath = url.lastPathComponent
        recordingURL = nil
        return try? Data(contentsOf: url)
    }

    var lastRecordingPath: String?

    func play(data: Data) async {
        #if !os(macOS)
        let session = AVAudioSession.sharedInstance()
        do {
            // 2026-05-14 修 TTS 雜音 root cause:
            // 原: .playback mode → CRITICAL_README 寫得很清楚不能用,
            //     overrideOutputAudioPort(.speaker) 在 .playback 模式無效, 聲音從耳機出。
            // 改: 統一 .playAndRecord + .default + .allowBluetoothHFP, 跟 VoiceBankPlayer 一致,
            //     避免三個 player 共用 AVAudioSession.sharedInstance() 互相 setCategory 切換產生的 noise burst。
            try session.setCategory(.playAndRecord, mode: .default,
                                    options: [.defaultToSpeaker, .allowBluetoothHFP])
            try session.setActive(true)
            try session.overrideOutputAudioPort(.speaker)
        } catch {
            print("[AudioEngine] playback session error:", error)
        }
        #endif

        await withCheckedContinuation { (cont: CheckedContinuation<Void, Never>) in
            do {
                player = try AVAudioPlayer(data: data)
                player?.delegate = PlayerDelegate.shared
                player?.volume = 1.0
                player?.prepareToPlay()
                PlayerDelegate.shared.onFinish = { cont.resume() }
                player?.play()
            } catch {
                print("[AudioEngine] play error:", error)
                cont.resume()
            }
        }
    }
}

private class PlayerDelegate: NSObject, AVAudioPlayerDelegate {
    static let shared = PlayerDelegate()
    var onFinish: (() -> Void)?
    func audioPlayerDidFinishPlaying(_ player: AVAudioPlayer, successfully flag: Bool) {
        onFinish?()
        onFinish = nil
    }
}
