import SwiftUI

// MARK: - Ambient Button
// 金色精緻圓鈕 — 像高級音響的開機鈕。
// 待機：浮起、淡淡金邊。錄音中：按下沉、外圈金光呼吸閃爍。
// 不顯示「正在錄音」文字 — 主人開會用，介面要低調。
struct AmbientButton: View {
    @ObservedObject private var recorder = AmbientRecorder.shared
    @ObservedObject private var vm = AlfredViewModel.shared
    @State private var glow: CGFloat = 0.0   // 0..1 呼吸動畫值

    private let gold       = Color(red: 0.788, green: 0.659, blue: 0.298)   // #c9a84c
    private let goldLight  = Color(red: 0.965, green: 0.847, blue: 0.498)   // #f6d87f
    private let goldShadow = Color(red: 0.376, green: 0.298, blue: 0.106)   // #60511b
    private let bgIdle     = Color(red: 0.078, green: 0.078, blue: 0.078)   // #141414

    private let size: CGFloat = 28

    var body: some View {
        Button {
            // 觸覺：按一下短震
            #if os(iOS)
            let h = UIImpactFeedbackGenerator(style: .medium)
            h.impactOccurred()
            #endif
            vm.toggleConversationalMode()
        } label: {
            ZStack {
                // 外圈呼吸金光（錄音中才有）
                if recorder.isRecording {
                    Circle()
                        .stroke(goldLight.opacity(0.55 + 0.45 * glow), lineWidth: 4)
                        .frame(width: size + 18 + 12 * glow,
                               height: size + 18 + 12 * glow)
                        .blur(radius: 4 + 4 * glow)
                }

                // 主鈕（按下沉）
                ZStack {
                    Circle()
                        .fill(
                            LinearGradient(
                                colors: recorder.isRecording
                                    ? [goldShadow, gold.opacity(0.92), goldShadow]
                                    : [gold, goldLight, gold],
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                            )
                        )
                    // 內陰影 (錄音中)
                    if recorder.isRecording {
                        Circle()
                            .stroke(Color.black.opacity(0.55), lineWidth: 2)
                            .blur(radius: 2)
                            .mask(Circle().padding(2))
                    }
                    // 中央小圓（凹光感）
                    Circle()
                        .fill(
                            recorder.isRecording
                                ? RadialGradient(colors: [goldLight.opacity(0.9), gold],
                                                 center: .center, startRadius: 0, endRadius: size * 0.35)
                                : RadialGradient(colors: [Color.white.opacity(0.5), gold],
                                                 center: .center, startRadius: 0, endRadius: size * 0.35)
                        )
                        .frame(width: size * 0.55, height: size * 0.55)
                }
                .frame(width: size, height: size)
                .shadow(color: recorder.isRecording
                            ? goldLight.opacity(0.8 * glow + 0.2)
                            : .black.opacity(0.55),
                        radius: recorder.isRecording ? (8 + 6 * glow) : 6,
                        x: 0, y: recorder.isRecording ? 1 : 3)
                .scaleEffect(recorder.isRecording ? 0.94 : 1.0)
                .animation(.spring(response: 0.28, dampingFraction: 0.7),
                           value: recorder.isRecording)
            }
            .frame(width: size + 36, height: size + 36)
            .contentShape(Circle())
        }
        .buttonStyle(.plain)
        .onAppear {
            withAnimation(.easeInOut(duration: 1.6).repeatForever(autoreverses: true)) {
                glow = 1.0
            }
        }
        .accessibilityLabel(recorder.isRecording ? "關閉阿福模式" : "開啟阿福模式")
        .accessibilityHint(recorder.isRecording
            ? "阿福正在聆聽有聲片段。再按一次會關閉，也可以說阿福你先不要聽。"
            : "按一下會先顯示聆聽宣告，確認後才開啟阿福模式。")
    }
}

#if DEBUG
#Preview {
    ZStack {
        Color(hex: "#090909").ignoresSafeArea()
        VStack {
            AmbientButton()
            Spacer()
        }
        .padding(.top, 50)
    }
}
#endif
