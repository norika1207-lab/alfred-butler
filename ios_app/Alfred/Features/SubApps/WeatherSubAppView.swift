import SwiftUI

// MARK: - Weather Sub-App
// Open-Meteo（免費，無需 API key）直接從 iOS 抓天氣，不依賴後端

struct WeatherSubAppView: View {
    let config   : SubAppConfig
    let onDismiss: () -> Void

    @State private var weather: WeatherData? = nil
    @State private var loading = true
    @State private var errorMsg = ""

    private let gold  = Color(hex: "#c9a84c")
    private let cream = Color(hex: "#e8d5b7")

    var body: some View {
        VStack(spacing: 0) {
            header
            if loading {
                Spacer()
                ProgressView().tint(gold).scaleEffect(1.2)
                Spacer()
            } else if !errorMsg.isEmpty {
                Spacer()
                Text(errorMsg).foregroundColor(cream.opacity(0.6)).font(.system(size: 14, weight: .light))
                Spacer()
            } else if let w = weather {
                weatherContent(w)
            }
        }
        .background(Color(hex: "#0c0905").ignoresSafeArea())
        .task { await fetchWeather() }
    }

    // MARK: Header
    private var header: some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text("W E A T H E R").font(.system(size: 9, weight: .medium)).foregroundColor(gold.opacity(0.5)).kerning(4)
                Text(weather?.cityName ?? "天氣").font(.system(size: 18, weight: .thin)).foregroundColor(cream)
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

    // MARK: Content
    private func weatherContent(_ w: WeatherData) -> some View {
        ScrollView(showsIndicators: false) {
            VStack(spacing: 0) {
                // 主要溫度
                mainTemp(w)
                    .padding(.top, 8).padding(.bottom, 32)

                // 細節列
                detailRow(w)
                    .padding(.horizontal, 24).padding(.bottom, 32)

                // 24 小時預報
                if !w.hourly.isEmpty {
                    hourlyForecast(w.hourly)
                        .padding(.bottom, 28)
                }

                // 7 天預報
                if !w.daily.isEmpty {
                    dailyForecast(w.daily)
                        .padding(.horizontal, 24)
                }

                Spacer().frame(height: 40)
            }
        }
    }

    private func mainTemp(_ w: WeatherData) -> some View {
        VStack(spacing: 8) {
            Text(w.conditionIcon)
                .font(.system(size: 60))
            Text("\(Int(w.currentTemp))°")
                .font(.system(size: 72, weight: .ultraLight))
                .foregroundColor(cream)
            Text(w.conditionText)
                .font(.system(size: 14, weight: .light))
                .foregroundColor(gold.opacity(0.7))
            Text("體感 \(Int(w.feelsLike))°   \(Int(w.tempMin))° ~ \(Int(w.tempMax))°")
                .font(.system(size: 11, weight: .light))
                .foregroundColor(cream.opacity(0.5))
        }
    }

    private func detailRow(_ w: WeatherData) -> some View {
        HStack(spacing: 0) {
            detailCell(icon: "humidity", label: "濕度", value: "\(w.humidity)%")
            dividerV
            detailCell(icon: "wind", label: "風速", value: "\(Int(w.windSpeed)) km/h")
            dividerV
            detailCell(icon: "umbrella", label: "降雨", value: "\(Int(w.precipProb))%")
        }
        .padding(.vertical, 16)
        .background(RoundedRectangle(cornerRadius: 2).fill(gold.opacity(0.04))
            .overlay(RoundedRectangle(cornerRadius: 2).stroke(gold.opacity(0.1), lineWidth: 0.5)))
    }

    private func detailCell(icon: String, label: String, value: String) -> some View {
        VStack(spacing: 4) {
            Image(systemName: sfIcon(icon)).font(.system(size: 16, weight: .ultraLight)).foregroundColor(gold.opacity(0.6))
            Text(value).font(.system(size: 15, weight: .light)).foregroundColor(cream)
            Text(label).font(.system(size: 9, weight: .medium)).foregroundColor(gold.opacity(0.4)).kerning(1)
        }.frame(maxWidth: .infinity)
    }

    private var dividerV: some View {
        Rectangle().fill(gold.opacity(0.15)).frame(width: 0.5).padding(.vertical, 8)
    }

    private func hourlyForecast(_ hours: [HourlyPoint]) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            sectionLabel("24 小時預報")
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 16) {
                    ForEach(Array(hours.prefix(24).enumerated()), id: \.offset) { _, h in
                        VStack(spacing: 6) {
                            Text(h.timeLabel).font(.system(size: 9)).foregroundColor(gold.opacity(0.5)).kerning(1)
                            Text(h.icon).font(.system(size: 20))
                            Text("\(Int(h.temp))°").font(.system(size: 13, weight: .light)).foregroundColor(cream)
                            if h.precipProb > 20 {
                                Text("\(Int(h.precipProb))%").font(.system(size: 9)).foregroundColor(Color(hex: "#6ab4d4"))
                            }
                        }.frame(width: 40)
                    }
                }.padding(.horizontal, 24)
            }
        }
    }

    private func dailyForecast(_ days: [DailyPoint]) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            sectionLabel("未來 7 天")
            VStack(spacing: 0) {
                ForEach(Array(days.prefix(7).enumerated()), id: \.offset) { i, d in
                    HStack {
                        Text(d.dayLabel).font(.system(size: 13, weight: .light)).foregroundColor(cream).frame(width: 60, alignment: .leading)
                        Text(d.icon).font(.system(size: 18))
                        Spacer()
                        if d.precipProb > 20 {
                            Text("\(Int(d.precipProb))%").font(.system(size: 10)).foregroundColor(Color(hex: "#6ab4d4")).frame(width: 30)
                        }
                        Text("\(Int(d.tempMin))°").font(.system(size: 12, weight: .ultraLight)).foregroundColor(cream.opacity(0.45)).frame(width: 32, alignment: .trailing)
                        Text("\(Int(d.tempMax))°").font(.system(size: 13, weight: .light)).foregroundColor(cream).frame(width: 32, alignment: .trailing)
                    }
                    .padding(.vertical, 10)
                    if i < 6 {
                        Rectangle().fill(gold.opacity(0.08)).frame(height: 0.5)
                    }
                }
            }
        }
    }

    private func sectionLabel(_ text: String) -> some View {
        Text(text).font(.system(size: 9, weight: .medium)).foregroundColor(gold.opacity(0.45)).kerning(3).padding(.horizontal, 24)
    }

    private func sfIcon(_ key: String) -> String {
        switch key {
        case "humidity": return "humidity"
        case "wind":     return "wind"
        case "umbrella": return "umbrella"
        default:         return "questionmark"
        }
    }

    // MARK: - Fetch Open-Meteo
    private func fetchWeather() async {
        guard let lat = config.lat, let lng = config.lng else {
            errorMsg = "無法取得位置資料"; loading = false; return
        }
        do {
            let w = try await OpenMeteoFetcher.fetch(lat: lat, lng: lng)
            await MainActor.run { weather = w; loading = false }
            // 讓阿福說出天氣摘要
            let summary = w.verbalSummary
            await MainActor.run {
                AlfredViewModel.shared.speakWeatherResult(summary)
            }
        } catch {
            await MainActor.run { errorMsg = "天氣資料暫時無法取得"; loading = false }
        }
    }
}

// MARK: - Data Models

struct WeatherData {
    let cityName    : String
    let currentTemp : Double
    let feelsLike   : Double
    let tempMin     : Double
    let tempMax     : Double
    let humidity    : Double
    let windSpeed   : Double
    let precipProb  : Double
    let conditionCode: Int
    let hourly      : [HourlyPoint]
    let daily       : [DailyPoint]

    var conditionText: String { WeatherCondition.text(conditionCode) }
    var conditionIcon: String { WeatherCondition.icon(conditionCode) }

    var verbalSummary: String {
        let rain = precipProb > 50 ? "，有降雨機率，記得帶傘" : ""
        return "現在\(conditionText)，氣溫\(Int(currentTemp))度，體感\(Int(feelsLike))度\(rain)。"
    }
}

struct HourlyPoint { let timeLabel: String; let temp: Double; let precipProb: Double; let icon: String }
struct DailyPoint   { let dayLabel: String; let tempMin: Double; let tempMax: Double; let precipProb: Double; let icon: String }

// MARK: - Open-Meteo Fetcher

enum OpenMeteoFetcher {
    static func fetch(lat: Double, lng: Double) async throws -> WeatherData {
        let url = URL(string:
            "https://api.open-meteo.com/v1/forecast"
            + "?latitude=\(lat)&longitude=\(lng)"
            + "&current=temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,weather_code"
            + "&hourly=temperature_2m,precipitation_probability,weather_code"
            + "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code"
            + "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code"
            + "&timezone=Asia%2FTaipei&forecast_days=7"
        )!
        let (data, _) = try await URLSession.shared.data(from: url)
        let j = try JSONSerialization.jsonObject(with: data) as! [String: Any]

        let cur     = j["current"]     as? [String: Any] ?? [:]
        let hourlyJ = j["hourly"]      as? [String: Any] ?? [:]
        let dailyJ  = j["daily"]       as? [String: Any] ?? [:]

        let temp    = (cur["temperature_2m"]     as? Double) ?? 0
        let feels   = (cur["apparent_temperature"] as? Double) ?? temp
        let hum     = (cur["relative_humidity_2m"] as? Double) ?? 0
        let wind    = (cur["wind_speed_10m"]     as? Double) ?? 0
        let code    = (cur["weather_code"]       as? Int)    ?? 0

        // Hourly (next 24)
        let hTemps  = (hourlyJ["temperature_2m"]              as? [Double]) ?? []
        let hPrecs  = (hourlyJ["precipitation_probability"]   as? [Double]) ?? []
        let hCodes  = (hourlyJ["weather_code"]                as? [Int])    ?? []
        let hTimes  = (hourlyJ["time"]                        as? [String]) ?? []
        var hourly: [HourlyPoint] = []
        for i in 0..<min(24, hTemps.count) {
            let label = hTimes.indices.contains(i) ? String(hTimes[i].suffix(5)) : ""
            hourly.append(HourlyPoint(
                timeLabel: label, temp: hTemps[i],
                precipProb: hPrecs.indices.contains(i) ? hPrecs[i] : 0,
                icon: WeatherCondition.icon(hCodes.indices.contains(i) ? hCodes[i] : 0)
            ))
        }

        // Daily (7 days)
        let dMaxes  = (dailyJ["temperature_2m_max"]              as? [Double]) ?? []
        let dMins   = (dailyJ["temperature_2m_min"]              as? [Double]) ?? []
        let dPrecs  = (dailyJ["precipitation_probability_max"]   as? [Double]) ?? []
        let dCodes  = (dailyJ["weather_code"]                    as? [Int])    ?? []
        let dTimes  = (dailyJ["time"]                            as? [String]) ?? []
        var daily: [DailyPoint] = []
        let dayNames = ["今天","明天","後天","週四","週五","週六","週日"]
        for i in 0..<min(7, dMaxes.count) {
            daily.append(DailyPoint(
                dayLabel: i < dayNames.count ? dayNames[i] : (dTimes.indices.contains(i) ? dTimes[i] : ""),
                tempMin: dMins.indices.contains(i) ? dMins[i] : 0,
                tempMax: dMaxes[i],
                precipProb: dPrecs.indices.contains(i) ? dPrecs[i] : 0,
                icon: WeatherCondition.icon(dCodes.indices.contains(i) ? dCodes[i] : 0)
            ))
        }

        let todayMin = (dMins.first) ?? temp - 3
        let todayMax = (dMaxes.first) ?? temp + 3
        let todayPrec = (dPrecs.first) ?? 0

        return WeatherData(
            cityName: "目前位置", currentTemp: temp, feelsLike: feels,
            tempMin: todayMin, tempMax: todayMax, humidity: hum,
            windSpeed: wind, precipProb: todayPrec, conditionCode: code,
            hourly: hourly, daily: daily
        )
    }
}

// MARK: - Weather Condition Mapping (WMO codes)

enum WeatherCondition {
    static func text(_ code: Int) -> String {
        switch code {
        case 0:         return "晴天"
        case 1:         return "大致晴朗"
        case 2:         return "局部多雲"
        case 3:         return "陰天"
        case 45, 48:    return "有霧"
        case 51, 53:    return "毛毛雨"
        case 55:        return "濃密毛毛雨"
        case 61, 63:    return "小雨"
        case 65:        return "大雨"
        case 71, 73:    return "小雪"
        case 75:        return "大雪"
        case 80, 81:    return "陣雨"
        case 82:        return "強陣雨"
        case 95:        return "雷陣雨"
        case 96, 99:    return "雷暴伴冰雹"
        default:        return "多雲"
        }
    }
    static func icon(_ code: Int) -> String {
        switch code {
        case 0:         return "☀️"
        case 1:         return "🌤"
        case 2:         return "⛅️"
        case 3:         return "☁️"
        case 45, 48:    return "🌫"
        case 51...55:   return "🌦"
        case 61...65:   return "🌧"
        case 71...75:   return "❄️"
        case 80...82:   return "🌧"
        case 95:        return "⛈"
        case 96, 99:    return "🌩"
        default:        return "🌥"
        }
    }
}
