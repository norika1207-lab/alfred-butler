import SwiftUI
import Photos
import UIKit

// MARK: - Photo Grid View
// 從對話 action `show_photos_picker` 跳出來；按條件列照片，主人選一張，
// 阿福把原圖丟 /api/analyze-photo 描述照片內容。
struct PhotoGridView: View {
    let request: PhotoPickerRequest
    let onClose: () -> Void

    @State private var assets: [PHAsset] = []
    @State private var thumbs: [String: UIImage] = [:]   // localIdentifier -> UIImage
    @State private var loading = true
    @State private var analyzing = false
    @State private var alfredText: String = ""

    private let columns = [GridItem(.flexible(), spacing: 4),
                           GridItem(.flexible(), spacing: 4),
                           GridItem(.flexible(), spacing: 4)]

    var body: some View {
        NavigationStack {
            ZStack {
                Color(red: 0.035, green: 0.035, blue: 0.035).ignoresSafeArea()
                if loading {
                    VStack(spacing: 14) {
                        ProgressView().tint(Color(red: 0.788, green: 0.659, blue: 0.298))
                        Text("阿福正在翻相簿...")
                            .foregroundColor(.gray)
                            .font(.system(size: 13))
                    }
                } else if assets.isEmpty {
                    VStack(spacing: 16) {
                        Text("找不到符合的照片")
                            .foregroundColor(Color(red: 0.91, green: 0.84, blue: 0.72))
                            .font(.system(size: 16))
                        if request.keyword != nil || request.range != nil {
                            Text("阿福目前還沒有相簿語意搜尋的能力，是按條件比對的。")
                                .foregroundColor(.gray.opacity(0.75))
                                .font(.system(size: 12))
                                .multilineTextAlignment(.center)
                                .padding(.horizontal, 32)
                        }
                    }
                } else {
                    ScrollView {
                        LazyVGrid(columns: columns, spacing: 4) {
                            ForEach(assets, id: \.localIdentifier) { a in
                                Button {
                                    Task { await analyze(a) }
                                } label: {
                                    ZStack {
                                        if let img = thumbs[a.localIdentifier] {
                                            Image(uiImage: img)
                                                .resizable()
                                                .scaledToFill()
                                        } else {
                                            Color.gray.opacity(0.18)
                                        }
                                    }
                                    .frame(height: 120)
                                    .clipped()
                                }
                                .buttonStyle(.plain)
                            }
                        }
                        .padding(.horizontal, 4)
                    }
                }

                if analyzing {
                    Color.black.opacity(0.55).ignoresSafeArea()
                    VStack(spacing: 12) {
                        ProgressView().tint(Color(red: 0.965, green: 0.847, blue: 0.498))
                        Text("阿福在看這張照片...")
                            .foregroundColor(.white)
                            .font(.system(size: 14))
                    }
                }

                if !alfredText.isEmpty {
                    VStack {
                        Spacer()
                        Text(alfredText)
                            .font(.system(size: 15))
                            .foregroundColor(Color(red: 0.91, green: 0.84, blue: 0.72))
                            .padding(16)
                            .background(
                                RoundedRectangle(cornerRadius: 14)
                                    .fill(Color.black.opacity(0.85))
                            )
                            .padding(.horizontal, 16)
                            .padding(.bottom, 24)
                            .multilineTextAlignment(.leading)
                    }
                }
            }
            .navigationTitle(request.keyword.map { "「\($0)」相片" } ?? "相簿")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("關閉") { onClose() }
                        .foregroundColor(Color(red: 0.788, green: 0.659, blue: 0.298))
                }
            }
        }
        .task { await load() }
    }

    private func load() async {
        let pm = PhotosManager.shared
        let assetsLoaded: [PHAsset]
        if let r = request.dateRange() {
            assetsLoaded = await pm.fetchInRange(from: r.0, to: r.1, limit: 60)
        } else {
            assetsLoaded = await pm.fetchRecent(limit: 60)
        }
        await MainActor.run {
            self.assets = assetsLoaded
            self.loading = false
        }
        // 縮圖逐張取
        for a in assetsLoaded {
            if let img = await pm.thumbnail(for: a) {
                await MainActor.run { thumbs[a.localIdentifier] = img }
            }
        }
    }

    private func analyze(_ asset: PHAsset) async {
        analyzing = true
        defer { analyzing = false }
        guard let data = await PhotosManager.shared.originalData(for: asset) else {
            alfredText = "讀不到這張照片的原圖。"
            return
        }
        do {
            let answer = try await uploadForAnalysis(imageData: data)
            alfredText = answer
            ConversationLog.shared.log(role: "assistant", text: answer, action: "photo_analyzed")
            await AlfredViewModel.shared.speakText(answer)
        } catch {
            alfredText = "上傳分析失敗：\(error.localizedDescription)"
        }
    }

    private func uploadForAnalysis(imageData: Data) async throws -> String {
        let url = URL(string: "https://alfred.31.97.221.240.nip.io/alfred/api/analyze-photo")!
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        if let t = AlfredAPI.shared.token {
            req.setValue("Bearer \(t)", forHTTPHeaderField: "Authorization")
        }
        let boundary = "AlfredPhoto-\(UUID().uuidString)"
        req.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        var body = Data()
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"file\"; filename=\"photo.jpg\"\r\n".data(using: .utf8)!)
        body.append("Content-Type: image/jpeg\r\n\r\n".data(using: .utf8)!)
        body.append(imageData)
        body.append("\r\n--\(boundary)--\r\n".data(using: .utf8)!)
        req.httpBody = body
        let (data, _) = try await URLSession.shared.upload(for: req, from: body)
        if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
            if let reply = json["reply"] as? String { return reply }
            if let answer = json["answer"] as? String { return answer }
            if let text = json["text"] as? String { return text }
            if let desc = json["description"] as? String { return desc }
        }
        return String(data: data, encoding: .utf8) ?? "（無法解析回應）"
    }
}
