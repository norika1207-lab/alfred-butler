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
    @Published var translationOverlay: TranslationOverlay? = nil  // 翻譯大字顯示
    var pendingHealthCheckin: Bool = false       // 等待主人回應健康確認
    var pendingEmergencyCall: Bool = false      // 等待主人確認是否撥 119

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

                // 主人說話就是對健康確認的回應（代表主人沒事）
                if pendingHealthCheckin {
                    pendingHealthCheckin = false
                    try? await api.healthCheckinAck()
                }

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
                if chunk.thinking != nil {
                    // 工具呼叫中：保持 thinking 狀態，不更新文字
                    state = .thinking
                }
                if let delta = chunk.delta {
                    if state == .thinking { state = .speaking }
                    fullText += delta
                    alfredText = fullText          // 即時更新
                }
                if chunk.done == true {
                    if let c = chunk.card { card = c }
                    if let action = chunk.action {
                        await handleAction(action, fullText: fullText)
                        return  // action 接管後續播放
                    }
                }
            }
            history.append(["role": "assistant", "content": fullText])
            await speakText(fullText)
        } catch {
            print("[Alfred] chat error:", error)
            state = .idle
        }
    }

    // MARK: - Action Handler
    private func handleAction(_ action: [String: String], fullText: String) async {
        let type = action["type"] ?? ""
        switch type {
        case "speak_translation":
            let translated = action["translated"] ?? ""
            let lang = action["lang"] ?? "en"
            // 先播阿福說的話（中文引導語）
            await speakText(fullText)
            // 顯示大字翻譯給對方看
            translationOverlay = TranslationOverlay(text: translated, lang: lang)
            // 播翻譯語音
            do {
                let audioData = try await api.translateAndSpeak(text: translated, targetLang: lang)
                await audio.play(data: audioData)
            } catch {
                print("[Alfred] translation TTS error:", error)
            }
            // 3 秒後自動收起翻譯覆層
            try? await Task.sleep(nanoseconds: 3_000_000_000)
            translationOverlay = nil
            state = .idle

        case "request_upload":
            await speakText(fullText)
            // 觸發上傳 UI（由 View 監聽 card 變化處理）
            state = .idle

        default:
            await speakText(fullText)
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

    func showAndSpeakContext(_ text: String) async {
        alfredText = text
        await speakText(text)
    }

    private func showAndSpeak(_ text: String) async {
        alfredText = text
        await speakText(text)
    }

    // 警報主動觸發：app 在前景時讓阿福直接開口
    func speakAloud(_ text: String) async {
        guard state == .idle else { return }
        alfredText = text
        await speakText(text)
        // 說完 5 秒後淡出，不佔版面
        try? await Task.sleep(nanoseconds: 5_000_000_000)
        if state == .idle { alfredText = "" }
    }
}

// MARK: - Data Models
struct TranslationOverlay: Identifiable {
    let id = UUID()
    let text: String
    let lang: String
}

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
    let thinking: String?  // 工具執行中的進度提示
}
