import SwiftUI

// MARK: - Translate Sub-App
// 後端翻譯完成後呈現精美雙語卡片，支援面對面展示模式

struct TranslateSubAppView: View {
    let config   : SubAppConfig
    let onDismiss: () -> Void

    @State private var showFaceToFace = false

    private let gold  = Color(hex: "#c9a84c")
    private let cream = Color(hex: "#e8d5b7")

    private var original   : String { config.original   ?? "" }
    private var translated : String { config.translated ?? "" }
    private var sourceLang : String { config.sourceLang ?? "zh-TW" }
    private var targetLang : String { config.targetLang ?? "en" }

    var body: some View {
        VStack(spacing: 0) {
            header
            ScrollView(showsIndicators: false) {
                VStack(spacing: 28) {
                    // 原文卡
                    langCard(
                        label: langLabel(sourceLang),
                        text: original,
                        dimmed: false
                    )
                    // 方向箭頭
                    Image(systemName: "arrow.down")
                        .font(.system(size: 14, weight: .ultraLight))
                        .foregroundColor(gold.opacity(0.35))
                    // 譯文卡
                    langCard(
                        label: langLabel(targetLang),
                        text: translated,
                        dimmed: false
                    )
                    // 操作按鈕
                    actionButtons
                    Spacer().frame(height: 40)
                }
                .padding(.horizontal, 24)
                .padding(.top, 8)
            }
        }
        .background(Color(hex: "#0c0905").ignoresSafeArea())
        .fullScreenCover(isPresented: $showFaceToFace) {
            FaceToFaceView(text: translated, lang: targetLang, onDismiss: { showFaceToFace = false })
        }
        .onAppear {
            // 阿福念出譯文
            if !translated.isEmpty {
                AlfredViewModel.shared.speakTranslated(translated, lang: targetLang)
            }
        }
    }

    // MARK: Header
    private var header: some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text("T R A N S L A T I O N").font(.system(size: 9, weight: .medium)).foregroundColor(gold.opacity(0.5)).kerning(4)
                Text("\(langLabel(sourceLang))  →  \(langLabel(targetLang))")
                    .font(.system(size: 16, weight: .thin)).foregroundColor(cream)
            }
            Spacer()
            Button(action: onDismiss) {
                Image(systemName: "xmark").font(.system(size: 12, weight: .ultraLight))
                    .foregroundColor(gold.opacity(0.5)).frame(width: 32, height: 32)
                    .background(gold.opacity(0.06)).clipShape(Circle())
            }
        }
        .padding(.horizontal, 24).padding(.vertical, 20)
    }

    // MARK: Lang Card
    private func langCard(label: String, text: String, dimmed: Bool) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(label)
                .font(.system(size: 9, weight: .medium))
                .foregroundColor(gold.opacity(dimmed ? 0.3 : 0.6))
                .kerning(3)
            Text(text)
                .font(.system(size: dimmed ? 14 : 17, weight: dimmed ? .ultraLight : .light))
                .foregroundColor(dimmed ? cream.opacity(0.5) : cream)
                .lineSpacing(6)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(18)
        .background(
            RoundedRectangle(cornerRadius: 2)
                .fill(gold.opacity(dimmed ? 0.02 : 0.05))
                .overlay(RoundedRectangle(cornerRadius: 2).stroke(gold.opacity(dimmed ? 0.06 : 0.15), lineWidth: 0.5))
        )
    }

    // MARK: Action Buttons
    private var actionButtons: some View {
        HStack(spacing: 16) {
            // 再聽一次
            actionBtn(icon: "speaker.wave.2", label: "再聽一次") {
                AlfredViewModel.shared.speakTranslated(translated, lang: targetLang)
            }
            // 面對面展示
            actionBtn(icon: "person.2", label: "給對方看") {
                showFaceToFace = true
            }
            // 複製
            actionBtn(icon: "doc.on.doc", label: "複製") {
                UIPasteboard.general.string = translated
            }
        }
    }

    private func actionBtn(icon: String, label: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            VStack(spacing: 6) {
                Image(systemName: icon).font(.system(size: 16, weight: .ultraLight)).foregroundColor(gold.opacity(0.7))
                Text(label).font(.system(size: 9, weight: .medium)).foregroundColor(gold.opacity(0.5)).kerning(1)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 14)
            .background(RoundedRectangle(cornerRadius: 2).fill(gold.opacity(0.05))
                .overlay(RoundedRectangle(cornerRadius: 2).stroke(gold.opacity(0.12), lineWidth: 0.5)))
        }
    }

    private func langLabel(_ code: String) -> String {
        switch code {
        case "zh-TW", "zh":  return "繁體中文"
        case "zh-CN":        return "簡體中文"
        case "en":           return "English"
        case "ja":           return "日本語"
        case "ko":           return "한국어"
        case "fr":           return "Français"
        case "es":           return "Español"
        case "de":           return "Deutsch"
        case "th":           return "ภาษาไทย"
        default:             return code.uppercased()
        }
    }
}

// MARK: - Face-to-Face Full Screen

struct FaceToFaceView: View {
    let text     : String
    let lang     : String
    let onDismiss: () -> Void

    private let gold  = Color(hex: "#c9a84c")
    private let cream = Color(hex: "#e8d5b7")

    var body: some View {
        ZStack {
            Color(hex: "#060503").ignoresSafeArea()
            VStack(spacing: 32) {
                Spacer()
                Text(text)
                    .font(.system(size: 38, weight: .thin))
                    .foregroundColor(cream)
                    .multilineTextAlignment(.center)
                    .lineSpacing(12)
                    .padding(.horizontal, 32)
                Spacer()
                Button(action: onDismiss) {
                    Text("收起").font(.system(size: 11, weight: .medium)).foregroundColor(gold.opacity(0.5))
                        .kerning(3).padding(.bottom, 40)
                }
            }
        }
    }
}
