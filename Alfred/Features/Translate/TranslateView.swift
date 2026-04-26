import SwiftUI

struct TranslateView: View {
    @Environment(\.dismiss) private var dismiss
    @StateObject private var vm = AlfredViewModel.shared
    @State private var selectedLang = "en"
    @State private var inputText = ""
    @State private var isTranslating = false

    let langs: [(code: String, label: String, flag: String)] = [
        ("en", "英文", "🇺🇸"), ("ja", "日文", "🇯🇵"), ("ko", "韓文", "🇰🇷"),
        ("fr", "法文", "🇫🇷"), ("es", "西班牙文", "🇪🇸"), ("de", "德文", "🇩🇪"),
        ("th", "泰文", "🇹🇭"), ("vi", "越南文", "🇻🇳"), ("id", "印尼文", "🇮🇩"),
    ]

    var body: some View {
        NavigationStack {
            ZStack {
                Color(hex: "#090909").ignoresSafeArea()
                VStack(spacing: 20) {
                    langSelector
                    inputArea
                    actionRow
                    voiceHint
                    Spacer()
                }
                .padding(.horizontal, 16).padding(.top, 8)
            }
            .navigationTitle("翻譯")
            .navigationBarTitleDisplayMode(.inline)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button(action: { dismiss() }) {
                        Image(systemName: "xmark").foregroundColor(Color(hex: "#c9a84c"))
                    }
                }
            }
        }
    }

    // MARK: - Lang Selector
    var langSelector: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(langs, id: \.code) { lang in
                    Button(action: { selectedLang = lang.code }) {
                        HStack(spacing: 4) {
                            Text(lang.flag).font(.system(size: 16))
                            Text(lang.label).font(.system(size: 13, weight: .medium))
                                .foregroundColor(selectedLang == lang.code
                                    ? Color(hex: "#090909") : Color(hex: "#e8d5b7"))
                        }
                        .padding(.horizontal, 12).padding(.vertical, 7)
                        .background(selectedLang == lang.code
                            ? Color(hex: "#c9a84c") : Color(hex: "#c9a84c15"))
                        .overlay(RoundedRectangle(cornerRadius: 20)
                            .stroke(Color(hex: "#c9a84c40"), lineWidth: selectedLang == lang.code ? 0 : 1))
                        .cornerRadius(20)
                    }
                }
            }
            .padding(.horizontal, 2)
        }
    }

    // MARK: - Input
    var inputArea: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("要翻譯的內容").font(.system(size: 12)).foregroundColor(Color(hex: "#c9a84c60")).kerning(0.5)
            ZStack(alignment: .topLeading) {
                if inputText.isEmpty {
                    Text("輸入文字，或直接用語音說給阿福聽…")
                        .font(.system(size: 15)).foregroundColor(Color(hex: "#c9a84c30"))
                        .padding(.top, 12).padding(.leading, 4)
                }
                TextEditor(text: $inputText)
                    .font(.system(size: 15)).foregroundColor(Color(hex: "#e8d5b7"))
                    .frame(minHeight: 100)
                    .scrollContentBackground(.hidden)
                    .background(Color.clear)
            }
        }
        .padding(14)
        .background(Color(hex: "#13110e"))
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(Color(hex: "#c9a84c20"), lineWidth: 1))
        .cornerRadius(12)
    }

    // MARK: - Actions
    var actionRow: some View {
        HStack(spacing: 12) {
            Button(action: translate) {
                HStack(spacing: 6) {
                    if isTranslating {
                        ProgressView().tint(Color(hex: "#090909")).scaleEffect(0.8)
                    } else {
                        Image(systemName: "globe").font(.system(size: 15))
                    }
                    Text(isTranslating ? "翻譯中…" : "翻譯並播音")
                        .font(.system(size: 14, weight: .semibold))
                }
                .foregroundColor(Color(hex: "#090909"))
                .frame(maxWidth: .infinity).padding(.vertical, 13)
                .background(inputText.isEmpty ? Color(hex: "#c9a84c60") : Color(hex: "#c9a84c"))
                .cornerRadius(10)
            }
            .disabled(inputText.isEmpty || isTranslating)

            Button(action: { inputText = "" }) {
                Image(systemName: "xmark.circle").font(.system(size: 22))
                    .foregroundColor(Color(hex: "#c9a84c60"))
            }
            .disabled(inputText.isEmpty)
        }
    }

    // MARK: - Voice hint
    var voiceHint: some View {
        VStack(spacing: 10) {
            HStack { Divider().background(Color(hex: "#c9a84c20")) }
            Text("也可以直接用語音").font(.system(size: 12)).foregroundColor(Color(hex: "#c9a84c40")).kerning(0.5)
            ForEach(["把這句話翻成英文：你好", "用日文說謝謝", "幫我翻成韓文再唸給對方聽"], id: \.self) { hint in
                Button(action: { sendVoiceHint(hint) }) {
                    HStack {
                        Text("「\(hint)」").font(.system(size: 13)).foregroundColor(Color(hex: "#e8d5b7"))
                        Spacer()
                        Image(systemName: "waveform").font(.system(size: 11))
                            .foregroundColor(Color(hex: "#c9a84c40"))
                    }
                    .padding(.vertical, 8).padding(.horizontal, 12)
                    .background(Color(hex: "#c9a84c08")).cornerRadius(8)
                }
            }
        }
    }

    func translate() {
        guard !inputText.isEmpty else { return }
        isTranslating = true
        let text = inputText
        let lang = selectedLang
        Task {
            await vm.sendMessage("把以下內容翻成\(langName(lang))並播音給對方聽：\(text)")
            isTranslating = false
            dismiss()
        }
    }

    func sendVoiceHint(_ hint: String) {
        dismiss()
        Task {
            try? await Task.sleep(nanoseconds: 300_000_000)
            await vm.sendMessage(hint)
        }
    }

    func langName(_ code: String) -> String {
        langs.first { $0.code == code }?.label ?? code
    }
}
