import AVFoundation
import Foundation

// MARK: - AudioManager
// 管理錄音、TTS 播放、翻譯音頻

@MainActor
class AudioManager: NSObject, ObservableObject {
    static let shared = AudioManager()

    @Published var isRecording = false
    @Published var isPlaying = false

    private var audioRecorder: AVAudioRecorder?
    private var audioPlayer: AVAudioPlayer?
    private var recordingURL: URL?

    override init() {
        super.init()
        setupAudioSession()
    }

    // MARK: - Session Setup

    func setupAudioSession() {
        do {
            let session = AVAudioSession.sharedInstance()
            try session.setCategory(.playAndRecord, mode: .default, options: [.defaultToSpeaker, .allowBluetooth])
            try session.setActive(true)
        } catch {
            print("[Audio] session setup error: \(error)")
        }
    }

    // MARK: - Recording

    func startRecording() throws -> URL {
        let docs = FileManager.default.temporaryDirectory
        let url = docs.appendingPathComponent("alfred_rec_\(Date().timeIntervalSince1970).m4a")
        recordingURL = url

        let settings: [String: Any] = [
            AVFormatIDKey: Int(kAudioFormatMPEG4AAC),
            AVSampleRateKey: 16000,
            AVNumberOfChannelsKey: 1,
            AVEncoderAudioQualityKey: AVAudioQuality.high.rawValue
        ]

        audioRecorder = try AVAudioRecorder(url: url, settings: settings)
        audioRecorder?.record()
        isRecording = true
        return url
    }

    func stopRecording() -> URL? {
        audioRecorder?.stop()
        isRecording = false
        return recordingURL
    }

    // MARK: - TTS Playback

    func playTTS(text: String) async {
        do {
            let data = try await APIClient.shared.tts(text: text)
            await playAudioData(data)
        } catch {
            print("[Audio] TTS error: \(error)")
        }
    }

    func playTranslationTTS(text: String, lang: String) async {
        do {
            let data = try await APIClient.shared.translateTTS(text: text, targetLang: lang)
            await playAudioData(data)
        } catch {
            print("[Audio] Translation TTS error: \(error)")
        }
    }

    func playAudioData(_ data: Data) async {
        guard !data.isEmpty else { return }
        do {
            let tmpURL = FileManager.default.temporaryDirectory
                .appendingPathComponent("alfred_tts_\(Date().timeIntervalSince1970).mp3")
            try data.write(to: tmpURL)
            audioPlayer = try AVAudioPlayer(contentsOf: tmpURL)
            audioPlayer?.delegate = self
            audioPlayer?.play()
            isPlaying = true
        } catch {
            print("[Audio] play error: \(error)")
        }
    }

    func stopPlayback() {
        audioPlayer?.stop()
        isPlaying = false
    }
}

extension AudioManager: AVAudioPlayerDelegate {
    nonisolated func audioPlayerDidFinishPlaying(_ player: AVAudioPlayer, successfully flag: Bool) {
        Task { @MainActor in
            self.isPlaying = false
        }
    }
}
