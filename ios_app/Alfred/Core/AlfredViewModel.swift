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
    @Published var showFamily: Bool = false
    @Published var showOffice: Bool = false
    @Published var showTranslate: Bool = false
    @Published var showAttendance: Bool = false

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
        let isOnboarded = UserDefaults.standard.bool(forKey: "alfred_onboarded")
        if !isOnboarded {
            // 首次開啟：播本地音檔，不 call API
            isFirstLaunch = true
            alfredText = "主人您好，請您依照以下內容說話，作為我認識您的開始：\n「阿福，我是你的主人，我會有很多地方需要你的幫忙，你要幫我把每一件事情處理好。」"
            state = .speaking
            if let url = Bundle.main.url(forResource: "onboarding_greeting", withExtension: "mp3") {
                do {
                    let data = try Data(contentsOf: url)
                    await audio.play(data: data)
                } catch {
                    print("[Alfred] onboarding audio error:", error)
                }
            }
            state = .idle
        } else {
            do {
                let resp = try await api.greet()
                isFirstLaunch = resp.firstTime ?? false
                await showAndSpeak(resp.text)
            } catch {
                print("[Alfred] greet error:", error)
            }
        }
    }

    // MARK: - Voice Input (按住錄音)
    func startListening() {
        // 按住即打斷阿福，不論當前狀態
        audio.stopPlayback()
        typewriterTimer?.invalidate()
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
        // 偵測啟動語 → 標記 onboarded + 自動取得 JWT token
        if message.contains("我是你的主人") && message.contains("幫我把每一件事情處理好") {
            UserDefaults.standard.set(true, forKey: "alfred_onboarded")
            isFirstLaunch = false
            if api.token == nil {
                let deviceId = UIDevice.current.identifierForVendor?.uuidString ?? UUID().uuidString
                _ = try? await api.deviceLogin(deviceId: deviceId)
            }
        }

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
            state = .idle

        case "show_family":
            await speakText(fullText)
            showFamily = true
            state = .idle

        case "show_office":
            await speakText(fullText)
            showOffice = true
            state = .idle

        case "show_translate":
            await speakText(fullText)
            showTranslate = true
            state = .idle

        case "show_attendance":
            await speakText(fullText)
            showAttendance = true
            state = .idle

        default:
            await speakText(fullText)
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
