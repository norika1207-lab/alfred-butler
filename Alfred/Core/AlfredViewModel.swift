import Foundation
import Combine
import AVFoundation
import UIKit

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
        // 一開機就拿 token，不等 onboarding（tts/transcribe 一開始就會用到）
        if api.token == nil {
            let deviceId = UIDevice.current.identifierForVendor?.uuidString ?? UUID().uuidString
            _ = try? await api.deviceLogin(deviceId: deviceId)
        }
        let isOnboarded = UserDefaults.standard.bool(forKey: "alfred_onboarded")

        if !isOnboarded {
            // mp3 內容把啟動語也念了，改用 TTS 只念介紹段，啟動語保留給主人念
            isFirstLaunch = true
            let intro = "主人您好，我是您的全能管家，能為您協助做很多事情。請您先讓我認識您，壓著中間對話按鈕，按照以下的文字說出來。"
            alfredText = "\(intro)\n\n「阿福，我是你的主人，我會有很多地方需要你的幫忙，你要幫我把每一件事情處理好。」"
            state = .speaking
            do {
                let audioData = try await api.tts(text: intro)
                await audio.play(data: audioData)
            } catch {
                print("[Alfred] onboarding TTS error:", error)
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
        // onboarding 期間保留啟動語提示，主人才看得到要念什麼
        if UserDefaults.standard.bool(forKey: "alfred_onboarded") {
            alfredText = ""
        }
    }

    func stopListening() {
        guard state == .listening else { return }
        state = .thinking
        Task {
            guard let audioData = audio.stopRecording() else {
                state = .idle; return
            }

            // 立刻說「阿福已經收到」（永遠執行，token 一開機就拿過）
            let ackTask = Task { await self.speakAck() }

            do {
                let transcript = try await api.transcribe(audioData: audioData)
                guard !transcript.isEmpty else {
                    await ackTask.value
                    state = .idle
                    return
                }
                userText = "「\(transcript)」"
                await ackTask.value
                await sendMessage(transcript)
            } catch {
                print("[Alfred] transcribe error:", error)
                await ackTask.value
                state = .idle
            }
        }
    }

    private func speakAck() async {
        do {
            let audioData = try await api.tts(text: "阿福已經收到")
            await audio.play(data: audioData)
        } catch {
            print("[Alfred] ack TTS error:", error)
        }
    }

    // MARK: - Send message (SSE stream)
    func sendMessage(_ message: String) async {
        let wasOnboarded = UserDefaults.standard.bool(forKey: "alfred_onboarded")
        let isActivation = message.contains("我是你的主人") && message.contains("幫我把每一件事情處理好")

        // ── Onboarding 階段：不走正常 chat，避免 alfredText 被清空 ─────────────
        if !wasOnboarded {
            if isActivation {
                UserDefaults.standard.set(true, forKey: "alfred_onboarded")
                isFirstLaunch = false
                if api.token == nil {
                    let deviceId = UIDevice.current.identifierForVendor?.uuidString ?? UUID().uuidString
                    _ = try? await api.deviceLogin(deviceId: deviceId)
                }
                alfredText = "好的，主人。從今天起我陪在您身邊。需要什麼跟我說一聲就好。"
                await speakText(alfredText)
            } else {
                // 啟動語錯：保留提示文字，請主人重念
                alfredText = "對不起主人，請依畫面上的句子說一遍：\n\n「阿福，我是你的主人，我會有很多地方需要你的幫忙，你要幫我把每一件事情處理好。」"
                await speakText("對不起主人，請依畫面上的句子說一遍。")
            }
            return
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
    let url: String?
    enum CodingKeys: String, CodingKey { case title, content, type, url }
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
