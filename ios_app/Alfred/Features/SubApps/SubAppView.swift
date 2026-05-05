import SwiftUI

// MARK: - Sub-App Config

struct SubAppConfig: Identifiable {
    let id      = UUID()
    let app     : String
    let lat     : Double?
    let lng     : Double?
    let query   : String?
    let original: String?
    let translated: String?
    let sourceLang: String?
    let targetLang: String?
    let driving : Bool
}

// MARK: - Router

struct SubAppView: View {
    let config: SubAppConfig
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        Group {
            switch config.app {
            case "weather":
                WeatherSubAppView(config: config, onDismiss: { dismiss() })
            case "maps":
                MapsSubAppView(config: config, onDismiss: { dismiss() })
            case "translate":
                TranslateSubAppView(config: config, onDismiss: { dismiss() })
            default:
                unknownApp
            }
        }
        .presentationDetents([.medium, .large])
        .presentationDragIndicator(.visible)
        .presentationBackground(Color(hex: "#0c0905"))
    }

    private var unknownApp: some View {
        VStack { Text("未知的 sub-app: \(config.app)").foregroundColor(.white) }
    }
}
