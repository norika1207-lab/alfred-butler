import SwiftUI

// MARK: - 登入/註冊畫面（純文字，零介面風格）

struct LoginView: View {
    @StateObject private var auth = AuthManager.shared
    @State private var email = ""
    @State private var password = ""
    @State private var isRegister = false
    @State private var loading = false
    @State private var errorMsg = ""

    var body: some View {
        ZStack {
            Color(hex: "#090909").ignoresSafeArea()

            VStack(spacing: 0) {
                Spacer()

                // 頭像
                Text("🎩").font(.system(size: 64))
                    .padding(.bottom, 12)

                Text("A L F R E D")
                    .font(.system(size: 12, weight: .medium))
                    .foregroundColor(Color(hex: "#c9a84c80"))
                    .kerning(4)
                    .padding(.bottom, 8)

                Text(isRegister ? "建立您的帳號" : "歡迎回來，主人")
                    .font(.system(size: 22, weight: .light))
                    .foregroundColor(Color(hex: "#e8d5b7"))
                    .padding(.bottom, 40)

                // 輸入欄
                VStack(spacing: 14) {
                    AlfredTextField(placeholder: "Email", text: $email, isSecure: false)
                    AlfredTextField(placeholder: "密碼", text: $password, isSecure: true)
                }
                .padding(.horizontal, 32)

                if !errorMsg.isEmpty {
                    Text(errorMsg)
                        .font(.system(size: 13))
                        .foregroundColor(Color.red.opacity(0.8))
                        .padding(.top, 12)
                        .padding(.horizontal, 32)
                }

                // 主按鈕
                Button(action: submit) {
                    ZStack {
                        RoundedRectangle(cornerRadius: 14)
                            .fill(Color(hex: "#c9a84c").opacity(0.85))
                        if loading {
                            ProgressView().tint(Color(hex: "#120e08"))
                        } else {
                            Text(isRegister ? "開始使用阿福" : "登入")
                                .font(.system(size: 16, weight: .semibold))
                                .foregroundColor(Color(hex: "#120e08"))
                        }
                    }
                    .frame(height: 52)
                }
                .padding(.horizontal, 32)
                .padding(.top, 24)
                .disabled(loading)

                // 切換登入/註冊
                Button(action: { isRegister.toggle(); errorMsg = "" }) {
                    Text(isRegister ? "已有帳號？登入" : "還沒有帳號？免費試用")
                        .font(.system(size: 13))
                        .foregroundColor(Color(hex: "#c9a84c60"))
                }
                .padding(.top, 16)

                if isRegister {
                    Text("免費試用 50 次對話")
                        .font(.system(size: 11))
                        .foregroundColor(Color(hex: "#e8d5b730"))
                        .padding(.top, 8)
                }

                Spacer()
            }
        }
    }

    func submit() {
        guard !email.isEmpty, !password.isEmpty else {
            errorMsg = "請填寫 Email 和密碼"; return
        }
        loading = true; errorMsg = ""
        Task {
            do {
                if isRegister {
                    try await auth.register(email: email, password: password)
                } else {
                    try await auth.login(email: email, password: password)
                }
            } catch {
                errorMsg = error.localizedDescription
            }
            loading = false
        }
    }
}

struct AlfredTextField: View {
    let placeholder: String
    @Binding var text: String
    let isSecure: Bool

    var body: some View {
        Group {
            if isSecure {
                SecureField(placeholder, text: $text)
            } else {
                TextField(placeholder, text: $text)
                    .keyboardType(.emailAddress)
                    .autocapitalization(.none)
            }
        }
        .padding(14)
        .background(Color(hex: "#ffffff08"))
        .overlay(
            RoundedRectangle(cornerRadius: 10)
                .stroke(Color(hex: "#c9a84c30"), lineWidth: 1)
        )
        .foregroundColor(Color(hex: "#e8d5b7"))
        .font(.system(size: 16))
    }
}
