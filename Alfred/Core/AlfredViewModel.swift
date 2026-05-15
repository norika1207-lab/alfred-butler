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
    @Published var photoPicker: PhotoPickerRequest? = nil   // 主人問相片時帶條件開 grid
    @Published var documentUploadRequest: DocumentUploadRequest? = nil
    @Published private(set) var currentSceneMode: String = "unknown"

    // 阿福模式：按一下大頭像開啟整天聆聽。
    // 平常只做逐字稿與生活觀察；只有聽到「阿福，我要你...」才把命令送進 chat handler。
    @Published var conversationalMode: Bool = false
    @Published var showAlfredModeDisclosure: Bool = false

    enum AlfredState { case idle, listening, thinking, speaking }

    override init() {
        super.init()
    }

    /// 大頭像 tap 入口 — 每次開啟前都先顯示明確聆聽宣告。
    func toggleConversationalMode() {
        if conversationalMode {
            stopAlfredMode()
        } else {
            requestAlfredModeDisclosure()
        }
    }

    func requestAlfredModeDisclosure() {
        guard UserDefaults.standard.bool(forKey: "alfred_onboarded") else {
            isFirstLaunch = true
            alfredText = """
            主人，阿福模式要先完成主人認證才會開啟。

            請先按住中間對話按鈕，照著這句話完整唸出來：

            「阿福，我是你的主人，我會有很多地方需要你的幫忙，你要幫我把每一件事情處理好。」
            """
            Task { await speakText("主人，阿福模式要先完成主人認證才會開啟。請先照著畫面上的句子念一遍。") }
            return
        }
        showAlfredModeDisclosure = true
    }

    func confirmAlfredModeDisclosure() {
        showAlfredModeDisclosure = false
        startAlfredModeIfNeeded(reason: "manual_disclosure_confirmed")
    }

    func cancelAlfredModeDisclosure() {
        showAlfredModeDisclosure = false
    }

    private func startAlfredModeIfNeeded(reason: String) {
        guard !conversationalMode else { return }
        guard UserDefaults.standard.bool(forKey: "alfred_onboarded") else {
            requestAlfredModeDisclosure()
            return
        }
        NSLog("[AlfredMode] enter reason=%@", reason)
        conversationalMode = true
        speechGeneration += 1
        audio.stopPlayback()
        alfredText = "阿福模式正在開啟..."
        AmbientRecorder.shared.onCommandDetected = { [weak self] command in
            guard let self else { return }
            Task { @MainActor in
                guard self.conversationalMode else { return }
                NSLog("[AlfredMode] command detected: %@", command)
                self.userText = "「\(command)」"
                await self.sendMessage(command)
            }
        }
        AmbientRecorder.shared.onReplyText = { [weak self] reply in
            guard let self else { return }
            Task { @MainActor in
                guard self.conversationalMode else { return }
                NSLog("[AlfredMode] quick reply: %@", reply)
                await self.speakText(reply)
            }
        }
        AmbientRecorder.shared.onStopRequested = { [weak self] in
            guard let self else { return }
            Task { @MainActor in
                self.stopAlfredMode()
            }
        }
        AmbientRecorder.shared.onStartFailed = { [weak self] message in
            guard let self else { return }
            Task { @MainActor in
                self.conversationalMode = false
                self.alfredText = message
                self.state = .idle
                await self.speakText(message)
            }
        }
        Task {
            if self.api.token == nil {
                let deviceId = UIDevice.current.identifierForVendor?.uuidString ?? UUID().uuidString
                _ = try? await self.api.deviceLogin(deviceId: deviceId)
            }
            AmbientRecorder.shared.start(
                label: "阿福模式 \(Self.sessionLabel())",
                triggerMessage: "阿福模式開啟：整天聆聽需求與生活脈絡，只有明確喚醒句才執行。",
                chunkInterval: 5
            )
            BackgroundManager.shared.scheduleAlfredModeTransparencyNotices()
            await speakText("主人，阿福模式已開啟。我會在本地判斷人聲，沒有聲音不會上傳；您叫我阿福時，我會回應您。")
            alfredText = ""
            state = .idle
        }
    }

    private func stopAlfredMode() {
        NSLog("[AlfredMode] exit")
        conversationalMode = false
        showAlfredModeDisclosure = false
        AmbientRecorder.shared.onCommandDetected = nil
        AmbientRecorder.shared.onReplyText = nil
        AmbientRecorder.shared.onStopRequested = nil
        AmbientRecorder.shared.onStartFailed = nil
        AmbientRecorder.shared.stop()
        BackgroundManager.shared.cancelAlfredModeTransparencyNotices()
        speechGeneration += 1
        audio.stopPlayback()
        state = .idle
    }

    private static func sessionLabel() -> String {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd HH:mm"
        return f.string(from: Date())
    }

    var statusLine: String? {
        switch state {
        case .listening:
            return "LISTENING"
        case .thinking, .speaking:
            return "THINKING"
        case .idle:
            return nil
        }
    }

    // MARK: - Private
    private let api = AlfredAPI.shared
    private let audio = AudioEngine.shared
    private var history: [[String: String]] = []
    private var typewriterTimer: Timer?
    private var pendingUserAudioPath: String?
    private var workModeCache: WorkModeBootstrapResponse?
    private var speechGeneration = 0
    private let pendingGooglePromptKey = "alfred_pending_google_link_prompt"
    private let sceneModeAnnounceKey = "alfred_scene_mode_announced"

    // MARK: - Startup
    func onAppear() {
        // UI test mode：launch arg 含 --prompt 時跳過 greet，避免跟 test sendMessage 打架
        if CommandLine.arguments.contains("--prompt") { return }
        Task {
            // 首次啟動：把所有 iOS 系統權限一次要完，避免用戶用到功能時才被打斷
            await PermissionCascade.runIfNeeded()
            await greet()
        }
    }

    func greet() async {
        // 一開機就拿 token，不等 onboarding（tts/transcribe 一開始就會用到）
        if api.token == nil {
            let deviceId = UIDevice.current.identifierForVendor?.uuidString ?? UUID().uuidString
            _ = try? await api.deviceLogin(deviceId: deviceId)
        }
        let isOnboarded = UserDefaults.standard.bool(forKey: "alfred_onboarded")

        if !isOnboarded {
            isFirstLaunch = true
            UserDefaults.standard.set(false, forKey: pendingGooglePromptKey)
            alfredText = """
            主人您好，我是您的全能管家。

            請您先讓我認識您，壓著中間對話按鈕，按照以下文字完整唸出來：

            「阿福，我是你的主人，我會有很多地方需要你的幫忙，你要幫我把每一件事情處理好。」
            """
            let intro = "主人您好，我是阿福。請按住中間按鈕，照著畫面上的文字完整唸一遍，讓我確認是您。"
            ConversationLog.shared.log(role: "assistant", text: intro, action: "onboarding_prompt")
            await speakText(intro)
            state = .idle
        } else {
            do {
                let resp = try await api.greet()
                isFirstLaunch = resp.firstTime ?? false
                // 上架安全：阿福模式不自動開麥。主人每次進 App 按下並看過宣告後才啟用。
                Task { await LocationManager.shared.checkContext(announce: false) }
                Task { await preloadSceneMode(announce: false) }
            } catch {
                print("[Alfred] greet error:", error)
            }
        }
    }

    // MARK: - Voice Input (按住錄音)
    func startListening() {
        NSLog("[AlfredDIAG] startListening fired, state=%@ token=%@", String(describing: state), api.token != nil ? "Y" : "N")
        // 按住即打斷阿福，不論當前狀態
        speechGeneration += 1
        audio.stopPlayback()
        typewriterTimer?.invalidate()
        audio.startRecording()
        state = .listening
        userText = ""
        NSLog("[AlfredDIAG] startListening done, recording started, state=listening")
        // onboarding 期間保留啟動語提示，主人才看得到要念什麼
        if UserDefaults.standard.bool(forKey: "alfred_onboarded") {
            alfredText = ""
        }
    }

    func stopListening() {
        NSLog("[AlfredDIAG] stopListening fired, state=%@ isRecording=%d", String(describing: state), audio.isRecording ? 1 : 0)
        guard state == .listening || audio.isRecording else {
            NSLog("[AlfredDIAG] stopListening GUARD SKIPPED (state not listening AND not recording)")
            return
        }
        state = .thinking
        Task {
            guard let audioData = audio.stopRecording() else {
                NSLog("[AlfredDIAG] stopRecording RETURNED NIL — abort to idle")
                state = .idle; return
            }
            NSLog("[AlfredDIAG] stopRecording got %d bytes audio", audioData.count)

            let shouldAck = UserDefaults.standard.bool(forKey: "alfred_onboarded")
            let ackTask: Task<Void, Never>? = shouldAck ? Task { await self.speakAck() } : nil

            do {
                NSLog("[Alfred] transcribe start, audio %d bytes", audioData.count)
                let transcript = try await api.transcribe(audioData: audioData)
                NSLog("[Alfred] transcribe result: '%@'", transcript)
                guard !transcript.isEmpty else {
                    NSLog("[Alfred] transcript empty, abort")
                    await ackTask?.value
                    state = .idle
                    return
                }
                userText = "「\(transcript)」"
                pendingUserAudioPath = audio.lastRecordingPath
                await ackTask?.value
                NSLog("[Alfred] sendMessage start")
                await sendMessage(transcript)
                NSLog("[Alfred] sendMessage done, state=%@", String(describing: state))
            } catch {
                NSLog("[Alfred] transcribe error: %@", String(describing: error))
                await ackTask?.value
                state = .idle
            }
        }
    }

    private let ackVoiceFiles = [
        "ack_short", "ack_got_it", "ack_understood", "ack_noted",
        "ack_on_it", "ack_asap", "ack_willdo", "ack_done",
        "ack_ofcourse", "ack_noworry", "ack_consider", "ack_reminding",
        "ack_perfect", "ack_interesting", "ack_wise", "ack_righaway",
        "ack_need_understood", "ack_now_handle", "ack_leave_to_me", "ack_checking",
        "ack_prepare_plan", "ack_generate_first", "ack_discreet", "ack_right_away_soft",
        "ack_following_up", "ack_arrange_after_confirm", "ack_no_problem",
        "ack_understood_need", "ack_looking_into_it", "ack_one_moment",
        "ack_quietly_handle", "ack_make_draft", "ack_sorting_now",
        "ack_understood_context", "ack_check_sources", "ack_will_report_back",
        "ack_butler_understood", "ack_butler_handle", "ack_butler_sort",
        "ack_butler_leave", "ack_butler_on_it"
    ]

    private let ackFallbackTexts = [
        "阿福已了解您的需求。",
        "阿福知道了，現在去處理。",
        "好的主人，阿福來處理。",
        "收到主人，我先替您整理。",
        "明白了主人，交給阿福。"
    ]


    private func bundledAudioURL(named name: String, in folder: String) -> URL? {
        let candidates: [String?] = [folder, "Resources/\(folder)", nil]
        for subdirectory in candidates {
            if let url = Bundle.main.url(forResource: name, withExtension: "mp3", subdirectory: subdirectory) {
                return url
            }
        }
        return nil
    }

    private func speakAck() async {
        if state == .listening { return }
        if await VoiceBankPlayer.shared.playRandom(in: "ack_butler") { return }

        do {
            let audioData = try await api.tts(text: "阿福已經收到您的指令。")
            await audio.play(data: audioData)
        } catch {
            NSLog("[Alfred] ack audio error: %@", String(describing: error))
        }
    }

    // MARK: - Send message (SSE stream)
    func sendMessage(_ message: String) async {
        let wasOnboarded = UserDefaults.standard.bool(forKey: "alfred_onboarded")
        let audioPath = pendingUserAudioPath
        pendingUserAudioPath = nil
        ConversationLog.shared.log(role: "user", text: message, audioPath: audioPath)

        // ────────────────────────────────────────────────────────────────────
        // ▸ Afu Brain MASL Gate（destructive action 本地擋，0 token）
        // ────────────────────────────────────────────────────────────────────
        if wasOnboarded {
            let gate = AfuBrainGate.decide(text: message)
            NSLog("[AfuBrain] intent=%@ risk=%@ decision=%@",
                  gate.intent, gate.risk.rawValue, gate.decision.rawValue)

            // critical block：完全不送 LLM
            if gate.decision == .block && gate.risk == .critical {
                let reply = "主人，這個動作是「\(gate.blockedFinalAction ?? "不可逆動作")」，阿福不直接執行。需要您 explicit 確認後我才會做。要做嗎？"
                ConversationLog.shared.log(role: "assistant", text: reply, action: "afu_brain_block")
                await speakText(reply)
                state = .idle
                return
            }
        }

        // ────────────────────────────────────────────────────────────────────
        // ▸ Alice Fastpath（時間 / 日期 / 數學 / 換算 / 簡短禮貌語）— 0 LLM 0 延遲
        //   用 iOS 本地 AVSpeechSynthesizer，跳過 ElevenLabs round trip
        // ────────────────────────────────────────────────────────────────────
        if wasOnboarded, let fastReply = AliceFastpath.tryAnswer(message) {
            NSLog("[AliceFastpath] hit, reply=%@", fastReply)
            ConversationLog.shared.log(role: "assistant", text: fastReply, action: "alice_fastpath")

            // ⭐ Voice bank 優先:liveness / greeting 等命中時直接從 bundle 預錄 mp3 播
            //    (Michael Caine 聲,< 1s,0 網路 0 LLM 0 ElevenLabs)
            //    沒對應 voice_bank category 才 fallback AVSpeechSynthesizer。
            state = .speaking
            if let cat = AliceFastpath.voiceBankCategory(for: message) {
                let played = await VoiceBankPlayer.shared.playRandom(in: cat)
                if !played {
                    NSLog("[AliceFastpath] voice_bank miss cat=%@, fallback speakLocally", cat)
                    await speakLocally(fastReply)
                }
            } else {
                await speakLocally(fastReply)
            }
            state = .idle
            return
        }

        // ── Onboarding 階段：不走正常 chat，避免 alfredText 被清空 ─────────────
        if !wasOnboarded {
            // 嚴比對：必須同時念到「主人」+「處理」，避免單字「主人」誤觸通過
            let normalized = message.replacingOccurrences(of: "妳", with: "你")
            let isStrictActivation = normalized.contains("主人") && normalized.contains("處理")
            NSLog("[Alfred onboarding] heard: %@ → strict_match: %@", message, isStrictActivation ? "YES" : "NO")

            if isStrictActivation {
                UserDefaults.standard.set(true, forKey: "alfred_onboarded")
                isFirstLaunch = false
                alfredText = ""
                if api.token == nil {
                    let deviceId = UIDevice.current.identifierForVendor?.uuidString ?? UUID().uuidString
                    _ = try? await api.deviceLogin(deviceId: deviceId)
                }
                BackgroundManager.shared.start()
                Task { await HealthKitManager.shared.requestPermissions() }
                LocationManager.shared.startTracking()
                Task { await LocationManager.shared.checkContext(announce: false) }
                Task { await preloadSceneMode(announce: false) }
                UserDefaults.standard.set(true, forKey: pendingGooglePromptKey)
                let reply = "好的，主人。認證完成，阿福正式待命。需要跟 Google 帳號連結嗎？連結後，我就能替您查詢與分析 Google Drive 資料，也能在您確認後安排行事曆。"
                ConversationLog.shared.log(role: "assistant", text: reply, action: "onboarding_success_google_prompt")
                await speakText(reply)
            } else {
                alfredText = "對不起主人，請依畫面上的句子說一遍：\n\n「阿福，我是你的主人，我會有很多地方需要你的幫忙，你要幫我把每一件事情處理好。」"
                let reply = "對不起主人，請依畫面上的句子說一遍。"
                ConversationLog.shared.log(role: "assistant", text: reply, action: "onboarding_retry")
                await speakText(reply)
            }
            return
        }

        if UserDefaults.standard.bool(forKey: pendingGooglePromptKey) {
            let normalized = message.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
            let wantsGoogle = normalized.contains("好") || normalized.contains("需要") || normalized.contains("可以") || normalized.contains("連") || normalized.contains("yes") || normalized.contains("ok")
            let declinesGoogle = normalized.contains("不要") || normalized.contains("不用") || normalized.contains("稍後") || normalized.contains("晚點") || normalized.contains("no")
            let isShortReply = normalized.count <= 12
            if wantsGoogle || declinesGoogle || isShortReply {
                UserDefaults.standard.set(false, forKey: pendingGooglePromptKey)
                if wantsGoogle && !declinesGoogle {
                    let urlString = "https://alfred.31.97.221.240.nip.io/alfred/api/gcal/authorize?label=personal"
                    let reply = "好的主人，我幫您打開 Google 授權連結。完成後，阿福就能協助查 Drive、分析資料，並在您確認後安排日曆。"
                    ConversationLog.shared.log(role: "assistant", text: reply, action: "google_link_prompt_open")
                    await speakText(reply)
                    if let url = URL(string: urlString) { await UIApplication.shared.open(url) }
                    state = .idle
                    return
                } else {
                    let reply = "好的主人，先不連結。之後需要時，您說一聲連結 Google 就可以。"
                    ConversationLog.shared.log(role: "assistant", text: reply, action: "google_link_prompt_decline")
                    await speakText(reply)
                    return
                }
            } else {
                UserDefaults.standard.set(false, forKey: pendingGooglePromptKey)
            }
        }

        if await handleIntegrationLinkRequest(message) {
            return
        }

        state = .thinking
        history.append(["role": "user", "content": message])
        if history.count > 20 { history = Array(history.suffix(20)) }

        var fullText = ""
        var responseCard: CardData?

        NSLog("[Alfred] chatStream start, msg='%@'", message)
        do {
            let stream = try await api.chatStream(message: message,
                                                   history: Array(history.suffix(10)))
            for try await chunk in stream {
                if chunk.thinking != nil {
                    state = .thinking
                }
                if let delta = chunk.delta {
                    fullText += delta
                }
                if chunk.done == true {
                    responseCard = chunk.card
                    if let c = chunk.card, shouldPresentVisualCard(c) { card = c }
                    if let action = chunk.action {
                        await handleAction(action, fullText: fullText)
                        return  // action 接管後續播放
                    }
                }
            }
            NSLog("[Alfred] chatStream done, fullText len=%d", fullText.count)
            history.append(["role": "assistant", "content": fullText])
            ConversationLog.shared.log(role: "assistant", text: fullText)
            await speakText(spokenReply(for: fullText, card: responseCard, userMessage: message))
            NSLog("[Alfred] speakText done")
        } catch {
            NSLog("[Alfred] chat error: %@", String(describing: error))
            state = .idle
        }
    }

    private func spokenReply(for text: String, card: CardData?, userMessage: String) -> String {
        let type = (card?.type ?? "").lowercased()
        let isDocumentCard = ["document", "file"].contains(type)
        let looksLikeDocumentResult = text.contains("我先從索引裡找到") ||
            text.contains("您要我讀哪一份") ||
            text.contains("我找到「") && (text.contains("我先念重點") || text.contains("目前沒有可朗讀"))
        let documentIntent = isDocumentCard || looksLikeDocumentResult
        guard documentIntent else { return text }

        let source = userMessage + " " + (card?.title ?? "") + " " + text
        if source.contains("合約") || source.contains("契約") || source.lowercased().contains("contract") {
            return "主人，我已經把合約先找出來，如果不是您要的，我會再去找一遍。"
        }
        if source.contains("報告") || source.contains("摘要") || source.contains("整理") {
            return "主人，我已經把文件先整理出來，如果不是您要的，我會再去找一遍。"
        }
        return "主人，我已經把文件先找出來，如果不是您要的，我會再去找一遍。"
    }


    func preloadSceneMode(context: LocationContextResponse? = nil, announce: Bool = false) async {
        do {
            async let setupWarmup: SetupStatusResponse = api.setupStatus()
            let boot = try await api.workModeBootstrap()
            _ = try? await setupWarmup
            workModeCache = boot
            currentSceneMode = boot.mode
            ConversationLog.shared.log(role: "assistant", text: "scene=\(boot.mode), priority=\(boot.scene.priority ?? "")", action: "scene_mode_preload")
            if announce, shouldAnnounceSceneMode(boot.mode), !boot.readyLine.isEmpty {
                ConversationLog.shared.log(role: "assistant", text: boot.readyLine, action: "scene_mode_announce")
                await speakSceneModeLine(mode: boot.mode, fallbackText: boot.readyLine)
            }
        } catch {
            NSLog("[Alfred] scene mode preload error: %@", String(describing: error))
        }
    }

    private func shouldAnnounceSceneMode(_ mode: String) -> Bool {
        guard ["work", "home", "travel"].contains(mode) else { return false }
        let day = ISO8601DateFormatter().string(from: Date()).prefix(10)
        let key = "\(mode)-\(day)"
        if UserDefaults.standard.string(forKey: sceneModeAnnounceKey) == key { return false }
        UserDefaults.standard.set(key, forKey: sceneModeAnnounceKey)
        return true
    }

    private func shouldPresentVisualCard(_ card: CardData) -> Bool {
        let type = (card.type ?? "").lowercased()
        let visualTypes = ["image", "photo", "photos", "product_list"]
        return visualTypes.contains(type)
    }

    private func handleIntegrationLinkRequest(_ message: String) async -> Bool {
        let normalized = message.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        let asksLine = normalized.contains("line") || normalized.contains("賴")
        let asksTelegram = normalized.contains("telegram") || normalized.contains("tg")
        let asksWhatsApp = normalized.contains("whatsapp") || normalized.contains("what's app") || normalized.contains("what app") || normalized.contains("瓦次")
        let asksGoogle = normalized.contains("google") || normalized.contains("gmail") || normalized.contains("行事曆") || normalized.contains("drive")
        let asksTextChannel = normalized.contains("不方便講話") || normalized.contains("文字對話") || normalized.contains("打字")
        let asksConnection = normalized.contains("連結") || normalized.contains("加入") || normalized.contains("好友") || normalized.contains("授權") || normalized.contains("開通")
        let asksStatus = normalized.contains("連上") || normalized.contains("連好了") || normalized.contains("狀態") || normalized.contains("有沒有連") || normalized.contains("已經連") || normalized.contains("好了嗎")

        guard asksConnection || asksTextChannel || asksLine || asksTelegram || asksWhatsApp || asksGoogle else { return false }

        if asksLine || (asksTextChannel && normalized.contains("阿福")) {
            let setup = try? await api.setupStatus()
            let botId = setup?.line.botId?.isEmpty == false ? setup!.line.botId! : "@222ouqpj"
            let urlString = "https://line.me/R/ti/p/\(botId)"
            let reply = "可以的主人。如果現在不方便講話，可以用 Line 跟阿福文字對話。我幫您打開加入好友連結。"
            ConversationLog.shared.log(role: "assistant", text: reply, action: "line_link_open")
            await speakText(reply)
            if let url = URL(string: urlString) { await UIApplication.shared.open(url) }
            state = .idle
            return true
        }

        if asksTelegram {
            let setup = try? await api.setupStatus()
            let username = setup?.telegram.botUsername?.isEmpty == false ? setup!.telegram.botUsername! : "alfred_demo_bot"
            let urlString = "https://t.me/\(username)"
            let reply = "可以的主人。我幫您打開 Telegram 連結，打開後按 Start，阿福就能記住這個對話。"
            ConversationLog.shared.log(role: "assistant", text: reply, action: "telegram_link_open")
            await speakText(reply)
            if let url = URL(string: urlString) { await UIApplication.shared.open(url) }
            state = .idle
            return true
        }

        if asksWhatsApp {
            let reply = "主人，WhatsApp 這條線阿福還沒開通。我先記下，目前可用的是 Line 和 Telegram。"
            ConversationLog.shared.log(role: "assistant", text: reply, action: "whatsapp_not_ready")
            await speakText(reply)
            state = .idle
            return true
        }

        if asksGoogle {
            if asksStatus && !normalized.contains("授權連結") {
                return false
            }
            guard asksConnection || normalized.contains("授權") else { return false }
            let urlString = "https://alfred.31.97.221.240.nip.io/alfred/api/gcal/authorize?label=personal"
            let reply = "好的主人，我幫您打開 Google 授權連結。完成後，阿福就能協助查 Drive、分析資料，並在您確認後安排日曆。"
            ConversationLog.shared.log(role: "assistant", text: reply, action: "google_link_open")
            await speakText(reply)
            if let url = URL(string: urlString) { await UIApplication.shared.open(url) }
            state = .idle
            return true
        }

        return false
    }

    // MARK: - Action Handler
    private func handleAction(_ action: [String: String], fullText: String) async {
        let type = action["type"] ?? ""
        ConversationLog.shared.log(role: "assistant", text: fullText, action: type)
        switch type {
        case "play_voice_bank":
            let category = action["category"] ?? "ack_butler"
            let played = await VoiceBankPlayer.shared.playRandom(in: category)
            if !played {
                await speakText(fullText)
            }
            state = .idle

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

        case "open_url":
            await speakText(fullText)
            if let urlString = action["url"], let url = URL(string: urlString) {
                await UIApplication.shared.open(url)
            }
            state = .idle

        case "request_upload":
            await speakText(fullText)
            documentUploadRequest = DocumentUploadRequest(
                title: action["title"] ?? "請把檔案交給阿福",
                purpose: action["purpose"] ?? "document",
                accept: action["accept"]
            )
            state = .idle

        case "show_family", "show_office", "show_translate", "show_attendance":
            // 零介面原則：不開 sheet，純語音回答（card / photo 才需要 UI）
            await speakText(fullText)
            state = .idle

        case "show_photos_picker":
            // 阿福先講話（介紹要找哪段時間 / 關鍵字的照片），再開 grid
            await speakText(fullText)
            let keyword = action["keyword"]
            let rangeStr = action["range"]   // "today" / "yesterday" / "last_week" / "last_month"
            photoPicker = PhotoPickerRequest(keyword: keyword, range: rangeStr)
            state = .idle

        case "start_ambient":
            await speakText(fullText)
            AmbientRecorder.shared.start(label: action["label"], triggerMessage: action["trigger_message"])
            state = .idle

        case "stop_ambient":
            AmbientRecorder.shared.stop()
            await speakText(fullText)
            state = .idle

        default:
            await speakText(fullText)
            state = .idle
        }
    }

    func uploadSelectedDocument(_ url: URL) async {
        let request = documentUploadRequest
        documentUploadRequest = nil
        let accessed = url.startAccessingSecurityScopedResource()
        defer {
            if accessed { url.stopAccessingSecurityScopedResource() }
        }

        let name = url.lastPathComponent
        ConversationLog.shared.log(role: "user", text: "上傳文件：\(name)", action: "document_upload")
        await speakText("主人，我收到「\(name)」。我現在讀內容並整理重點。")

        do {
            let uploaded = try await api.uploadDocument(fileURL: url, purpose: request?.purpose ?? "document")
            let analysis = try await api.analyzeUploadedDocument(fileId: uploaded.id)
            guard analysis.ok, let report = analysis.report else {
                let error = analysis.error ?? "文件讀取失敗"
                ConversationLog.shared.log(role: "assistant", text: error, action: "document_analyze_failed")
                await speakText("主人，這份文件我收到了，但讀取內容時失敗：\(error)")
                return
            }

            let title = "文件分析：\(analysis.name ?? uploaded.name)"
            card = CardData(title: title, content: report, type: "document")
            let spoken = makeSpokenDigest(from: report)
            ConversationLog.shared.log(role: "assistant", text: spoken, action: "document_analyzed")
            await speakText("主人，我讀完了，完整報告已經放在畫面上。我先念最重要的重點。\(spoken)")
            state = .idle
        } catch {
            ConversationLog.shared.log(role: "assistant", text: error.localizedDescription, action: "document_upload_failed")
            await speakText("主人，文件上傳或分析失敗：\(error.localizedDescription)")
            state = .idle
        }
    }

    func requestManualDocumentAnalysis() {
        audio.stopPlayback()
        typewriterTimer?.invalidate()
        documentUploadRequest = DocumentUploadRequest(
            title: "請選擇要交給阿福解讀的文件",
            purpose: "document",
            accept: "pdf,docx,txt,md"
        )
    }

    func cancelDocumentUpload() {
        documentUploadRequest = nil
    }

    private func makeSpokenDigest(from markdown: String) -> String {
        let cleaned = markdown
            .replacingOccurrences(of: "#", with: "")
            .replacingOccurrences(of: "*", with: "")
            .replacingOccurrences(of: "`", with: "")
            .replacingOccurrences(of: "🚩", with: "")
        let lines = cleaned
            .split(separator: "\n")
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty && !$0.hasPrefix("---") }
        let picked = lines.prefix(8).joined(separator: "。")
        if picked.count > 650 {
            return String(picked.prefix(650)) + "。"
        }
        return picked
    }

    private func speakSceneModeLine(mode: String, fallbackText: String) async {
        let fileName: String?
        switch mode {
        case "work": fileName = "mode_work_enter"
        case "home": fileName = "family_watch_quietly"
        case "travel": fileName = "mode_travel_enter"
        default: fileName = nil
        }
        if let fileName {
            guard state != .listening else { return }
            let generation = speechGeneration
            state = .speaking
            let played = await VoiceBankPlayer.shared.play(id: fileName)
            if played {
                if generation == speechGeneration, state == .speaking { state = .idle }
                return
            }
        }
        await speakText(fallbackText)
    }

    // MARK: - TTS
    func speakText(_ text: String) async {
        guard state != .listening else { return }
        let generation = speechGeneration
        state = .speaking
        do {
            let audioData = try await api.tts(text: text)
            if generation == speechGeneration, state != .listening {
                await audio.play(data: audioData)
            }
        } catch {
            print("[Alfred] tts error:", error)
        }
        if generation == speechGeneration, state == .speaking { state = .idle }
    }

    func showAndSpeakContext(_ text: String) async {
        await speakText(text)
    }

    private func showAndSpeak(_ text: String) async {
        await speakText(text)
    }

    // 警報主動觸發：app 在前景時讓阿福直接開口
    func speakAloud(_ text: String) async {
        guard state == .idle else { return }
        await speakText(text)
    }

    // 本地 TTS（用 iOS AVSpeechSynthesizer，0 網路）—— 給 Alice fastpath 用
    private let localSynth = AVSpeechSynthesizer()
    func speakLocally(_ text: String) async {
        await MainActor.run {
            // 停掉任何進行中的播放（ack 或前一輪 reply）
            audio.stopPlayback()
            if localSynth.isSpeaking { localSynth.stopSpeaking(at: .immediate) }
            let utt = AVSpeechUtterance(string: text)
            utt.voice = AVSpeechSynthesisVoice(language: "zh-TW")
            utt.rate = 0.50               // 比 default 0.5 稍慢一點，clearer
            utt.pitchMultiplier = 0.95    // 稍低，往老管家靠
            utt.volume = 1.0
            state = .speaking
            localSynth.speak(utt)
        }
        // 粗估播放秒數 = 字數 / 6 + 0.4 buffer
        let estSec = Double(text.count) / 6.0 + 0.4
        try? await Task.sleep(nanoseconds: UInt64(estSec * 1_000_000_000))
        state = .idle
    }
}

// MARK: - Data Models
struct TranslationOverlay: Identifiable {
    let id = UUID()
    let text: String
    let lang: String
}

struct ProductItem: Decodable {
    let site: String?
    let code: String?
    let name: String?
    let price: Int?
    let listPrice: Int?
    let discountPct: Int?
    let imageUrl: String?
    let buyUrl: String?
    let rating: String?
    let reviewCount: String?
    enum CodingKeys: String, CodingKey {
        case site, code, name, price
        case listPrice = "list_price"
        case discountPct = "discount_pct"
        case imageUrl = "image_url"
        case buyUrl = "buy_url"
        case rating
        case reviewCount = "review_count"
    }
}

struct CardData: Decodable, Identifiable {
    var id = UUID()
    let title: String?
    let content: String?
    let type: String?
    let url: String?
    let buttonTitle: String?
    let products: [ProductItem]?

    init(title: String? = nil, content: String? = nil, type: String? = nil, url: String? = nil, buttonTitle: String? = nil, products: [ProductItem]? = nil) {
        self.title = title
        self.content = content
        self.type = type
        self.url = url
        self.buttonTitle = buttonTitle
        self.products = products
    }

    enum CodingKeys: String, CodingKey { case title, content, type, url, buttonTitle, products }
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

struct DocumentUploadRequest: Identifiable {
    let id = UUID()
    let title: String
    let purpose: String
    let accept: String?
}
