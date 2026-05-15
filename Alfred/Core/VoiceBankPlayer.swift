import Foundation
import AVFoundation

/// VoiceBankPlayer — 從 bundle 預錄 mp3 隨機 / 規則挑播。
///
/// 產品策略：
/// - 有 `voice_bank_manifest.json` 時照 manifest 分類。
/// - 沒 manifest 時直接掃 bundle 內 `voice_bank` / `Resources/voice_bank` /
///   `voices` / `Resources/voices`，用檔名前綴自動建分類。
/// - backend action: `play_voice_bank`、iOS AliceFastpath、場景模式都走這裡。
@MainActor
final class VoiceBankPlayer {

    static let shared = VoiceBankPlayer()

    private var manifest: [String: [String]] = [:]  // category -> filename without .mp3
    private var player: AVAudioPlayer?

    private let searchSubdirectories = [
        "voice_bank",
        "Resources/voice_bank",
        "voices",
        "Resources/voices",
        nil,
    ]

    private let categoryAliases: [String: [String]] = [
        "ack_butler": ["ack_butler", "ack_short", "ack_got_it", "ack_understood", "character_here", "character_ready"],
        "greet_time": ["greet_time", "greet_morning", "greet_afternoon", "greet_evening", "greet_latenight", "goodnight"],
        "mode_enter": ["mode_enter", "context_at_home", "context_at_office", "context_traveling"],
        "travel_mode": ["travel_mode", "travel", "context_traveling"],
        "family_safety": ["family_safety", "family_safe", "family_alert", "family_opening"],
        "mood_care": ["mood_care", "care_mood", "care_tired", "care_overworking"],
        "health_monitoring": ["health_monitoring", "health", "care_medicine", "health_stretching"],
        "file_search": ["file_search", "search", "search_drive", "search_found_multiple", "search_looking"],
        "document_review": ["document_review", "doc", "contract", "analyze"],
        "calendar": ["calendar", "cal"],
        "approval_gate": ["approval_gate", "confirm"],
        "error_recovery": ["error_recovery", "error"],
        "office_manager": ["office_manager", "eod", "attendance"],
    ]

    private init() {
        loadManifest()
        if manifest.isEmpty {
            scanBundledAudio()
        }
    }

    private func loadManifest() {
        guard let url = Bundle.main.url(forResource: "voice_bank_manifest", withExtension: "json"),
              let data = try? Data(contentsOf: url),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let lines = json["lines"] as? [[String: Any]]
        else {
            NSLog("[VoiceBank] manifest not found; scanning bundle")
            return
        }
        var map: [String: [String]] = [:]
        for line in lines {
            guard let id = line["id"] as? String,
                  let cat = line["category"] as? String else { continue }
            map[cat, default: []].append(id)
        }
        manifest = map
        let totalIds = map.values.reduce(0) { $0 + $1.count }
        NSLog("[VoiceBank] manifest loaded %d categories, %d ids", map.count, totalIds)
    }

    private func scanBundledAudio() {
        var map: [String: [String]] = [:]
        for subdirectory in searchSubdirectories {
            guard let urls = Bundle.main.urls(forResourcesWithExtension: "mp3", subdirectory: subdirectory) else {
                continue
            }
            for url in urls {
                let id = url.deletingPathExtension().lastPathComponent
                add(id: id, to: &map)
            }
        }
        manifest = map
        let totalIds = map.values.reduce(0) { $0 + $1.count }
        NSLog("[VoiceBank] scanned %d categories, %d ids", map.count, totalIds)
    }

    private func add(id: String, to map: inout [String: [String]]) {
        guard !id.isEmpty else { return }
        map[id, default: []].append(id)

        let parts = id.split(separator: "_").map(String.init)
        guard parts.count >= 2 else { return }

        let first = parts[0]
        map[first, default: []].append(id)

        if parts.count >= 3, Int(parts.last ?? "") != nil {
            let category = parts.dropLast().joined(separator: "_")
            map[category, default: []].append(id)
        } else {
            let category = parts.prefix(2).joined(separator: "_")
            map[category, default: []].append(id)
        }
    }

    func playRandom(in category: String) async -> Bool {
        let keys = [category] + (categoryAliases[category] ?? [])
        for key in keys {
            if let ids = manifest[key], !ids.isEmpty {
                return await play(id: ids.randomElement()!)
            }
        }
        NSLog("[VoiceBank] no ids in category=%@", category)
        return false
    }

    func play(id: String) async -> Bool {
        guard let url = audioURL(for: id) else {
            NSLog("[VoiceBank] mp3 not found: %@", id)
            return false
        }
        return await play(url: url)
    }

    private func audioURL(for id: String) -> URL? {
        for subdirectory in searchSubdirectories {
            if let url = Bundle.main.url(forResource: id, withExtension: "mp3", subdirectory: subdirectory) {
                return url
            }
        }
        return nil
    }

    private func play(url: URL) async -> Bool {
        do {
            let session = AVAudioSession.sharedInstance()
            try session.setCategory(.playAndRecord, mode: .default,
                                    options: [.defaultToSpeaker, .allowBluetoothHFP])
            try session.setActive(true)
            try session.overrideOutputAudioPort(.speaker)

            let p = try AVAudioPlayer(contentsOf: url)
            p.volume = 1.0
            p.prepareToPlay()
            p.play()
            player = p
            try await Task.sleep(nanoseconds: UInt64(max(p.duration, 0.2) * 1_000_000_000))
            return true
        } catch {
            NSLog("[VoiceBank] play failed: %@", String(describing: error))
            return false
        }
    }

    func count(in category: String) -> Int {
        let keys = [category] + (categoryAliases[category] ?? [])
        return keys.reduce(0) { $0 + (manifest[$1]?.count ?? 0) }
    }
}
