import SwiftUI
import UIKit
import UniformTypeIdentifiers

// MARK: - 主畫面（零介面）
// 大頭像按一下 → 每次先顯示聆聽宣告，主人確認後才開啟阿福模式。
// 只有「阿福，我要你...」明確喚醒句才觸發任務；可用語音請阿福休息。
// 介面保留不動，只在模式開啟時顯示一行狀態。

struct AlfredView: View {
    @StateObject private var vm = AlfredViewModel.shared
    @State private var isPressing = false

    var body: some View {
        ZStack {
            // 背景
            Color(hex: "#090909").ignoresSafeArea()

            VStack(spacing: 0) {
                Spacer()

                if vm.conversationalMode {
                    Text("阿福模式開啟，阿福將會整天聆聽您的需求陪伴在您身邊。")
                        .font(.system(size: 15, weight: .medium))
                        .foregroundColor(Color(hex: "#e8d5b7"))
                        .multilineTextAlignment(.center)
                        .lineSpacing(4)
                        .padding(.horizontal, 28)
                        .transition(.opacity)

                    Spacer().frame(height: 16)
                }

                // 阿福頭像（按一下進入/退出阿福模式）
                AlfredAvatarView(state: vm.state, isPressing: vm.conversationalMode)
                    .gesture(
                        TapGesture()
                            .onEnded { _ in
                                #if os(iOS)
                                UIImpactFeedbackGenerator(style: .medium).impactOccurred()
                                #endif
                                vm.toggleConversationalMode()
                            }
                    )

                Spacer().frame(height: 18)

                if let status = vm.statusLine {
                    Text(status)
                        .font(.system(size: 15, weight: .semibold))
                        .foregroundColor(Color(hex: "#d84a3a"))
                        .tracking(1.5)
                        .transition(.opacity)
                        .animation(.easeInOut(duration: 0.12), value: status)
                }

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

                Spacer().frame(height: 56)
            }
        }
        // 必要視覺輸出：文件 / 圖片 / 授權，不把一般對話做成聊天畫面。
        .sheet(item: $vm.card) { card in
            CardView(card: card)
        }
        // 相片 picker（阿福在對話裡帶 show_photos_picker 才開）
        .sheet(item: $vm.photoPicker) { req in
            PhotoGridView(request: req) { vm.photoPicker = nil }
        }
        // 文件/報告/合約需要主人交檔案時，才開系統檔案選擇器。
        .fileImporter(
            isPresented: Binding(
                get: { vm.documentUploadRequest != nil },
                set: { presented in
                    if !presented { vm.cancelDocumentUpload() }
                }
            ),
            allowedContentTypes: AlfredView.documentTypes,
            allowsMultipleSelection: false
        ) { result in
            switch result {
            case .success(let urls):
                guard let url = urls.first else { return }
                Task { await vm.uploadSelectedDocument(url) }
            case .failure:
                vm.cancelDocumentUpload()
            }
        }
        // 零介面：辦公室 / 家人 / 翻譯 / 出勤 全部純語音口頭回答，不開 sheet
        // 唯一介面 = CardView（文件解讀 / 照片）+ TranslationOverlay（給對方看翻譯）
        // 翻譯覆層（大字給對方看）
        .overlay {
            if let overlay = vm.translationOverlay {
                TranslationOverlayView(overlay: overlay)
                    .transition(.opacity.combined(with: .scale(scale: 0.95)))
            }
        }
        .animation(.easeInOut(duration: 0.3), value: vm.translationOverlay?.id)
        .alert("開啟阿福模式", isPresented: $vm.showAlfredModeDisclosure) {
            Button("開啟阿福模式") { vm.confirmAlfredModeDisclosure() }
            Button("取消", role: .cancel) { vm.cancelAlfredModeDisclosure() }
        } message: {
            Text("開啟後，阿福會使用麥克風聆聽有聲片段，將內容上傳至阿福後端轉成逐字稿，用來整理摘要、會議記錄與待辦。沒有聲音的片段不會上傳或轉錄。您可以隨時再按一次關閉，也可以說：阿福你先關閉、阿福你先不要聽、阿福你去休息。下次要開啟時，請回到 App 再次確認。")
        }
        // 金色被動錄音鈕（介面正上方，按下沉並閃金光；不觸發 AI 回應）
        .overlay(alignment: .top) {
            AmbientButton()
                .padding(.top, 8)
        }
        .onAppear { vm.onAppear() }
    }

}

extension AlfredView {
    static var documentTypes: [UTType] {
        var types: [UTType] = [.pdf, .plainText, .text]
        if let markdown = UTType(filenameExtension: "md") { types.append(markdown) }
        if let docx = UTType(filenameExtension: "docx") { types.append(docx) }
        return types
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
            Group {
                if card.type == "product_list", let products = card.products, !products.isEmpty {
                    ProductListCardView(products: products)
                } else {
                    ScrollView {
                        VStack(spacing: 20) {
                            Text(card.content ?? "")
                                .font(.system(size: 15))
                                .foregroundColor(Color(hex: "#e8d5b7"))
                                .frame(maxWidth: .infinity, alignment: .leading)

                            if let urlStr = card.url, let url = URL(string: urlStr) {
                                Button {
                                    UIApplication.shared.open(url)
                                } label: {
                                    Text(card.buttonTitle ?? "前往授權")
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
                }
            }
            .background(Color(hex: "#13110e"))
            .navigationTitle(card.type == "product_list" ? "比價結果" : (card.title ?? ""))
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

// MARK: - 商品比價卡片

struct ProductListCardView: View {
    let products: [ProductItem]

    var body: some View {
        ScrollView {
            VStack(spacing: 12) {
                ForEach(Array(products.enumerated()), id: \.offset) { _, product in
                    ProductRowView(product: product)
                }
            }
            .padding(16)
        }
    }
}

struct ProductRowView: View {
    let product: ProductItem

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            // 商品圖
            Group {
                if let imgStr = product.imageUrl, let url = URL(string: imgStr) {
                    AsyncImage(url: url) { phase in
                        switch phase {
                        case .success(let img):
                            img.resizable().scaledToFill()
                        case .failure:
                            placeholderImage
                        default:
                            Color(hex: "#1e1c18")
                                .overlay(ProgressView().tint(Color(hex: "#c9a84c")))
                        }
                    }
                } else {
                    placeholderImage
                }
            }
            .frame(width: 90, height: 90)
            .clipShape(RoundedRectangle(cornerRadius: 8))

            // 商品資訊
            VStack(alignment: .leading, spacing: 4) {
                Text(product.name ?? "")
                    .font(.system(size: 13, weight: .medium))
                    .foregroundColor(Color(hex: "#e8d5b7"))
                    .lineLimit(2)

                HStack(spacing: 6) {
                    Text("\(product.price.map { String(format: "%d", $0) } ?? "-") 元")
                        .font(.system(size: 17, weight: .bold))
                        .foregroundColor(Color(hex: "#c9a84c"))

                    if let disc = product.discountPct {
                        Text("省\(disc)%")
                            .font(.system(size: 11, weight: .semibold))
                            .foregroundColor(.white)
                            .padding(.horizontal, 5).padding(.vertical, 2)
                            .background(Color(hex: "#d84a3a"))
                            .clipShape(Capsule())
                    }
                }

                if let rating = product.rating, let count = product.reviewCount {
                    Text("⭐ \(rating)（\(count)則評價）")
                        .font(.system(size: 11))
                        .foregroundColor(Color(hex: "#888070"))
                }

                if let site = product.site {
                    Text(site.uppercased())
                        .font(.system(size: 10, weight: .semibold))
                        .foregroundColor(Color(hex: "#888070"))
                }
            }

            Spacer()

            // 購買按鈕
            if let urlStr = product.buyUrl, let url = URL(string: urlStr) {
                Button {
                    UIApplication.shared.open(url)
                } label: {
                    Text("前往\n購買")
                        .font(.system(size: 12, weight: .semibold))
                        .multilineTextAlignment(.center)
                        .foregroundColor(Color(hex: "#090909"))
                        .frame(width: 52, height: 44)
                        .background(Color(hex: "#c9a84c"))
                        .cornerRadius(8)
                }
            }
        }
        .padding(12)
        .background(Color(hex: "#1a1813"))
        .cornerRadius(12)
    }

    private var placeholderImage: some View {
        RoundedRectangle(cornerRadius: 8)
            .fill(Color(hex: "#1e1c18"))
            .overlay(
                Image(systemName: "cart")
                    .foregroundColor(Color(hex: "#888070"))
                    .font(.system(size: 24))
            )
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
