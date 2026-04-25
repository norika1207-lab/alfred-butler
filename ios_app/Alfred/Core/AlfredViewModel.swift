import Foundation
import AVFoundation

// MARK: - Alfred Core ViewModel
// 整個 App 的大腦。語音錄音 → STT → Chat (SSE) → TTS → 播放

@MainActor
class AlfredViewModel: NSObject, ObservableObject {

    static let shared = AlfredViewModel()

    // MARK: - Published state
    @Published var alfredText: String = ""       // 阿福說的話（打字效果中）
    @Published var userText: String = ""         // 主人說的話
    @Published var state: AlfredState = .idle    // idle / listening / thinking / speaking
    @Published var card: CardData? = nil         // 卡片（合約分析、報告等）
    @Published var isFirstLaunch: Bool = false

    enum AlfredState { case idle, listening, thinking, speaking }

    // MARK: - Private
    private let api = AlfredAPI.shared
    private let audio = AudioEngine.shared
    private var history: [[String: String]] = []
    private var typewriterTimer: Timer?

    // MARK: - Startup
    func onAppear() {
        Task { await greet() }
    }

    func greet() async {
        do {
            let resp = try await api.greet()
            isFirstLaunch = resp.firstTime ?? false
            await showAndSpeak(resp.text)
        } catch {
            print("[Alfred] greet error:", error)
        }
    }

    // MARK: - Voice Input (按住錄音)
    func startListening() {
        guard state == .idle else { return }
        audio.startRecording()
        state = .listening
        userText = ""
        alfredText = ""
    }

    func stopListening() {
        guard state == .listening else { return }
        state = .thinking
        Task {
            guard let audioData = audio.stopRecording() else {
                state = .idle; return
            }
            do {
                let transcript = try await api.transcribe(audioData: audioData)
                guard !transcript.isEmpty else { state = .idle; return }
                userText = "「\(transcript)」"
                await sendMessage(transcript)
            } catch {
                print("[Alfred] transcribe error:", error)
                state = .idle
            }
        }
    }

    // MARK: - Send message (SSE stream)
    func sendMessage(_ message: String) async {
        state = .thinking
        history.append(["role": "user", "content": message])
        if history.count > 20 { history = Array(history.suffix(20)) }

        alfredText = ""
        var fullText = ""

        do {
            let stream = try await api.chatStream(message: message,
                                                   history: Array(history.suffix(10)))
            for try await chunk in stream {
                if let delta = chunk.delta {
                    fullText += delta
                    alfredText = fullText          // 即時更新
                }
                if chunk.done == true {
                    if let c = chunk.card { card = c }
                    // action 處理（翻譯、上傳等）
                }
            }
            history.append(["role": "assistant", "content": fullText])
            await speakText(fullText)
        } catch {
            print("[Alfred] chat error:", error)
            state = .idle
        }
    }

    // MARK: - TTS
    func speakText(_ text: String) async {
        state = .speaking
        do {
            let audioData = try await api.tts(text: text)
            await audio.play(data: audioData)
        } catch {
            print("[Alfred] tts error:", error)
        }
        state = .idle
    }

    private func showAndSpeak(_ text: String) async {
        alfredText = text
        await speakText(text)
    }
}

// MARK: - Data Models
struct CardData: Decodable, Identifiable {
    var id = UUID()
    let title: String?
    let content: String?
    let type: String?
    enum CodingKeys: String, CodingKey { case title, content, type }
}

struct GreetResponse: Decodable {
    let text: String
    let firstTime: Bool?
    enum CodingKeys: String, CodingKey {
        case text
        case firstTime = "first_time"
    }
}

struct StreamChunk: Decodable {
    let delta: String?
    let done: Bool?
    let text: String?
    let card: CardData?
    let action: [String: String]?
}
