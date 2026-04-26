import SwiftUI
import UIKit

// MARK: - 主畫面（零介面）
// 全螢幕阿福。按住說話，放開阿福回答。就這樣。

struct AlfredView: View {
    @StateObject private var vm = AlfredViewModel.shared
    @State private var isPressing = false

    var body: some View {
        ZStack {
            // 背景
            Color(hex: "#090909").ignoresSafeArea()

            VStack(spacing: 0) {
                Spacer()

                // 阿福頭像（按住這裡說話）
                AlfredAvatarView(state: vm.state, isPressing: isPressing)
                    .gesture(
                        DragGesture(minimumDistance: 0)
                            .onChanged { _ in
                                if !isPressing {
                                    isPressing = true
                                    vm.startListening()
                                }
                            }
                            .onEnded { _ in
                                if isPressing {
                                    isPressing = false
                                    vm.stopListening()
                                }
                            }
                    )

                Spacer().frame(height: 32)

                // 只在 onboarding（isFirstLaunch=true）顯示啟動語提示，認證完成後純聲音
                if vm.isFirstLaunch && !vm.alfredText.isEmpty {
                    Text(vm.alfredText)
                        .font(.system(size: 17, weight: .regular))
                        .foregroundColor(Color(hex: "#e8d5b7"))
                        .padding(.horizontal, 28)
                        .multilineTextAlignment(.center)
                        .lineSpacing(6)
                        .animation(.easeIn(duration: 0.1), value: vm.alfredText)
                }

                Spacer().frame(height: 16)

                // 狀態提示
                Text(hintText)
                    .font(.system(size: 11, weight: .medium))
                    .foregroundColor(Color(hex: "#c9a84c60"))
                    .letterSpacing(1.5)
                    .padding(.bottom, 40)
            }
        }
        // 卡片（合約分析、報告等）
        .sheet(item: $vm.card) { card in
            CardView(card: card)
        }
        // 阿福主動推開的功能頁面
        .sheet(isPresented: $vm.showFamily)    { FamilyView() }
        .sheet(isPresented: $vm.showOffice)    { OfficeDashboardView() }
        .sheet(isPresented: $vm.showTranslate) { TranslateView() }
        .sheet(isPresented: $vm.showAttendance){ AttendanceView() }
        // 翻譯覆層（大字給對方看）
        .overlay {
            if let overlay = vm.translationOverlay {
                TranslationOverlayView(overlay: overlay)
                    .transition(.opacity.combined(with: .scale(scale: 0.95)))
            }
        }
        .animation(.easeInOut(duration: 0.3), value: vm.translationOverlay?.id)
        .onAppear { vm.onAppear() }
    }

    var hintText: String {
        switch vm.state {
        case .idle:      return isPressing ? "正在聆聽" : "按住說話"
        case .listening: return "正在聆聽..."
        case .thinking:  return "思考中"
        case .speaking:  return "A L F R E D"
        }
    }
}

// MARK: - 阿福頭像 + 動畫
struct AlfredAvatarView: View {
    let state: AlfredViewModel.AlfredState
    let isPressing: Bool

    @State private var pulse = false

    var body: some View {
        ZStack {
            // 光暈環
            ForEach(0..<3) { i in
                Circle()
                    .stroke(Color(hex: "#c9a84c").opacity(ringOpacity(i)), lineWidth: 1)
                    .frame(width: CGFloat(180 + i * 40), height: CGFloat(180 + i * 40))
                    .scaleEffect(pulse ? 1.04 : 1.0)
                    .animation(
                        .easeInOut(duration: 2.4).repeatForever().delay(Double(i) * 0.5),
                        value: pulse
                    )
            }

            // 頭像圓
            Circle()
                .fill(Color(hex: "#c9a84c").opacity(0.08))
                .overlay(
                    Circle().stroke(Color(hex: "#c9a84c").opacity(0.4), lineWidth: 1.5)
                )
                .frame(width: 110, height: 110)
                .scaleEffect(isPressing ? 0.93 : 1.0)
                .animation(.spring(response: 0.2), value: isPressing)
                .overlay(
                    Text("🎩")
                        .font(.system(size: 44))
                )
        }
        .onAppear { pulse = true }
    }

    func ringOpacity(_ i: Int) -> Double {
        switch state {
        case .listening: return [0.4, 0.25, 0.12][i]
        case .speaking:  return [0.35, 0.2, 0.08][i]
        default:         return [0.2, 0.12, 0.05][i]
        }
    }
}

// MARK: - 卡片視圖（合約、報告等長內容）
struct CardView: View {
    let card: CardData
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 20) {
                    Text(card.content ?? "")
                        .font(.system(size: 15))
                        .foregroundColor(Color(hex: "#e8d5b7"))
                        .frame(maxWidth: .infinity, alignment: .leading)

                    // OAuth 授權卡片：顯示「前往授權」按鈕，點下開外部 Safari
                    if let urlStr = card.url, let url = URL(string: urlStr) {
                        Button {
                            UIApplication.shared.open(url)
                        } label: {
                            Text("前往授權")
                                .font(.system(size: 16, weight: .semibold))
                                .foregroundColor(Color(hex: "#090909"))
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 14)
                                .background(Color(hex: "#c9a84c"))
                                .cornerRadius(10)
                        }
                    }
                }
                .padding(20)
            }
            .background(Color(hex: "#13110e"))
            .navigationTitle(card.title ?? "")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("關閉") { dismiss() }
                        .foregroundColor(Color(hex: "#c9a84c"))
                }
            }
        }
    }
}

// MARK: - 翻譯覆層（給對方看的大字）
struct TranslationOverlayView: View {
    let overlay: TranslationOverlay

    var body: some View {
        ZStack {
            Color.black.opacity(0.92).ignoresSafeArea()
            VStack(spacing: 24) {
                Text(langLabel)
                    .font(.system(size: 13, weight: .medium))
                    .foregroundColor(Color(hex: "#c9a84c80"))
                    .letterSpacing(2)
                Text(overlay.text)
                    .font(.system(size: 36, weight: .light))
                    .foregroundColor(Color(hex: "#e8d5b7"))
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 32)
                    .lineSpacing(10)
            }
        }
    }

    var langLabel: String {
        switch overlay.lang {
        case "en": return "ENGLISH"
        case "ja": return "日本語"
        case "ko": return "한국어"
        case "fr": return "FRANÇAIS"
        case "es": return "ESPAÑOL"
        case "de": return "DEUTSCH"
        case "th": return "ภาษาไทย"
        default:   return overlay.lang.uppercased()
        }
    }
}

// MARK: - Helpers
extension Color {
    init(hex: String) {
        let h = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: h).scanHexInt64(&int)
        let a, r, g, b: UInt64
        switch h.count {
        case 6: (a, r, g, b) = (255, int >> 16, int >> 8 & 0xFF, int & 0xFF)
        case 8: (a, r, g, b) = (int >> 24, int >> 16 & 0xFF, int >> 8 & 0xFF, int & 0xFF)
        default: (a, r, g, b) = (255, 0, 0, 0)
        }
        self.init(.sRGB,
                  red: Double(r) / 255,
                  green: Double(g) / 255,
                  blue: Double(b) / 255,
                  opacity: Double(a) / 255)
    }
}

extension Text {
    func letterSpacing(_ spacing: CGFloat) -> some View {
        self.kerning(spacing)
    }
}
