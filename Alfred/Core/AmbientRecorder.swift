import Foundation
import AVFoundation
import Combine

// MARK: - Ambient Recorder
// 被動錄音：本地先用低成本音量偵測判斷有沒有人聲。
// 沒有人聲的片段直接丟棄，不上傳、不轉錄、不生成逐字稿。
// 一般 ambient 不觸發 AI 回應；阿福模式只在明確「阿福，我要你...」喚醒句時執行。
@MainActor
final class AmbientRecorder: NSObject, ObservableObject {
    static let shared = AmbientRecorder()

    @Published private(set) var isRecording = false
    @Published private(set) var sessionId: Int? = nil
    @Published private(set) var chunksSentThisSession = 0

    private var recorder: AVAudioRecorder?
    private var currentURL: URL?
    private var rotateTimer: Timer?
    private var meteringTask: Task<Void, Never>?
    private var chunkHasSpeech = false
    private let speechThresholdDb: Float = -45.0
    private let speechFramesNeeded = 3
    private let defaultChunkInterval: TimeInterval = 120   // 一般 ambient: 120 秒
    private var activeChunkInterval: TimeInterval = 120
    var onCommandDetected: ((String) -> Void)?
    var onReplyText: ((String) -> Void)?
    var onStopRequested: (() -> Void)?
    var onStartFailed: ((String) -> Void)?

    private let chunkDir: URL = {
        let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        let d = docs.appendingPathComponent("ambient_chunks", isDirectory: true)
        try? FileManager.default.createDirectory(at: d, withIntermediateDirectories: true)
        return d
    }()

    func toggle() {
        if isRecording { stop() } else { start() }
    }

    func start(label requestedLabel: String? = nil, triggerMessage: String? = nil, chunkInterval: TimeInterval? = nil) {
        guard !isRecording else { return }
        activeChunkInterval = chunkInterval ?? defaultChunkInterval
        configureSession()
        Task {
            do {
                let label = requestedLabel ?? isoLabel()
                let sid = try await AlfredAPI.shared.ambientStart(label: label, triggerMessage: triggerMessage)
                self.sessionId = sid
                self.chunksSentThisSession = 0
                self.isRecording = true
                self.startNewChunk()
                guard self.isRecording, self.recorder != nil else {
                    return
                }
                self.scheduleRotate()
                NSLog("[Ambient] start session=\(sid) label=\(label)")
            } catch {
                let message = "主人，阿福模式沒有成功開啟。請確認網路與麥克風權限後再試一次。"
                NSLog("[Ambient] start failed: \(error.localizedDescription)")
                self.isRecording = false
                self.sessionId = nil
                self.onStartFailed?(message)
            }
        }
    }

    func stop() {
        guard isRecording else { return }
        rotateTimer?.invalidate()
        rotateTimer = nil
        let lastChunk = finishCurrentChunk()
        let sid = sessionId
        isRecording = false
        sessionId = nil
        if let chunk = lastChunk, let sid = sid {
            Task.detached(priority: .background) { [weak self] in
                await self?.uploadChunkIfVoiced(chunk, sessionId: sid, isFinal: true)
                try? await AlfredAPI.shared.ambientStop(sessionId: sid)
                NSLog("[Ambient] stop done")
            }
        } else if let sid = sid {
            Task.detached { try? await AlfredAPI.shared.ambientStop(sessionId: sid) }
        }
    }

    // MARK: - Internal

    private func configureSession() {
        #if !os(macOS)
        let s = AVAudioSession.sharedInstance()
        do {
            try s.setCategory(.record, mode: .measurement,
                              options: [.allowBluetooth, .mixWithOthers])
            try s.setActive(true)
        } catch {
            NSLog("[Ambient] session error \(error.localizedDescription)")
        }
        #endif
    }

    private func startNewChunk() {
        let stamp: String = {
            let f = DateFormatter()
            f.dateFormat = "yyyy-MM-dd_HH-mm-ss"
            return f.string(from: Date())
        }()
        let url = chunkDir.appendingPathComponent("ambient_\(stamp).m4a")
        let settings: [String: Any] = [
            AVFormatIDKey: Int(kAudioFormatMPEG4AAC),
            AVSampleRateKey: 16000,
            AVNumberOfChannelsKey: 1,
            AVEncoderAudioQualityKey: AVAudioQuality.medium.rawValue
        ]
        do {
            let r = try AVAudioRecorder(url: url, settings: settings)
            r.isMeteringEnabled = true
            r.prepareToRecord()
            let ok = r.record()
            guard ok else {
                throw NSError(domain: "AmbientRecorder", code: -1, userInfo: [NSLocalizedDescriptionKey: "AVAudioRecorder.record() returned false"])
            }
            self.recorder = r
            self.currentURL = url
            self.chunkHasSpeech = false
            self.startMetering()
        } catch {
            let message = "主人，麥克風沒有成功開始錄音。請確認 Alfred 的麥克風權限。"
            NSLog("[Ambient] record start error \(error.localizedDescription)")
            self.isRecording = false
            self.sessionId = nil
            self.onStartFailed?(message)
        }
    }

    @discardableResult
    private func finishCurrentChunk() -> (url: URL, hasSpeech: Bool)? {
        meteringTask?.cancel()
        meteringTask = nil
        recorder?.stop()
        let url = currentURL
        let hasSpeech = chunkHasSpeech
        recorder = nil
        currentURL = nil
        chunkHasSpeech = false
        guard let url else { return nil }
        return (url, hasSpeech)
    }

    private func startMetering() {
        meteringTask?.cancel()
        meteringTask = Task { @MainActor [weak self] in
            var voicedFrames = 0
            while !Task.isCancelled {
                guard let self, let recorder = self.recorder else { return }
                recorder.updateMeters()
                let level = recorder.averagePower(forChannel: 0)
                if level > self.speechThresholdDb {
                    voicedFrames += 1
                    if voicedFrames >= self.speechFramesNeeded {
                        self.chunkHasSpeech = true
                    }
                } else {
                    voicedFrames = max(0, voicedFrames - 1)
                }
                try? await Task.sleep(nanoseconds: 250_000_000)
            }
        }
    }

    private func scheduleRotate() {
        rotateTimer?.invalidate()
        let t = Timer.scheduledTimer(withTimeInterval: activeChunkInterval, repeats: true) { [weak self] _ in
            Task { @MainActor in self?.rotateChunk() }
        }
        // app 在背景時 Timer 也會嘗試 fire；audio background mode 開啟下系統會保活
        RunLoop.main.add(t, forMode: .common)
        rotateTimer = t
    }

    private func rotateChunk() {
        guard isRecording, let sid = sessionId else { return }
        let finishedChunk = finishCurrentChunk()
        startNewChunk()  // 立即開新檔，最小化縫隙（~50ms）
        if let chunk = finishedChunk {
            Task.detached(priority: .background) { [weak self] in
                await self?.uploadChunkIfVoiced(chunk, sessionId: sid, isFinal: false)
            }
        }
    }

    private func uploadChunkIfVoiced(_ chunk: (url: URL, hasSpeech: Bool), sessionId: Int, isFinal: Bool) async {
        guard chunk.hasSpeech else {
            NSLog("[Ambient] discard silent chunk \(chunk.url.lastPathComponent) (final=\(isFinal))")
            try? FileManager.default.removeItem(at: chunk.url)
            return
        }
        await uploadChunk(url: chunk.url, sessionId: sessionId, isFinal: isFinal)
    }

    private func uploadChunk(url: URL, sessionId: Int, isFinal: Bool) async {
        // retry 3 次，間隔遞增
        for attempt in 0..<3 {
            do {
                let response = try await AlfredAPI.shared.ambientUploadChunk(sessionId: sessionId, fileURL: url)
                NSLog("[Ambient] uploaded \(url.lastPathComponent) (final=\(isFinal))")
                await MainActor.run {
                    self.chunksSentThisSession += 1
                    if response.controlAction == "stop_alfred_mode" {
                        self.onStopRequested?()
                        return
                    }
                    if let reply = response.replyText?.trimmingCharacters(in: .whitespacesAndNewlines), !reply.isEmpty {
                        self.onReplyText?(reply)
                        return
                    }
                    if response.commandDetected == true, let command = response.commandText?.trimmingCharacters(in: .whitespacesAndNewlines), !command.isEmpty {
                        self.onCommandDetected?(command)
                    }
                }
                try? FileManager.default.removeItem(at: url)
                return
            } catch {
                NSLog("[Ambient] upload attempt \(attempt+1) failed: \(error.localizedDescription)")
                try? await Task.sleep(nanoseconds: UInt64(pow(2.0, Double(attempt))) * 1_000_000_000)
            }
        }
        NSLog("[Ambient] upload gave up — keeping local file \(url.lastPathComponent)")
    }

    private func isoLabel() -> String {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd HH:mm"
        return f.string(from: Date())
    }
}
