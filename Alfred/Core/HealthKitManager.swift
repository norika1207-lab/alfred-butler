import Foundation
import Combine
import HealthKit

// MARK: - HealthKit Manager
// 申請心率/步數/距離/卡路里/運動記錄權限，同步到後端 /api/workouts/sync

@MainActor
class HealthKitManager: ObservableObject {
    static let shared = HealthKitManager()

    private let store = HKHealthStore()

    @Published var isAvailable: Bool = HKHealthStore.isHealthDataAvailable()
    @Published var isAuthorized: Bool = false

    private let readTypes: Set<HKObjectType> = {
        var types: Set<HKObjectType> = []
        let ids: [HKQuantityTypeIdentifier] = [
            .heartRate,
            .stepCount,
            .distanceWalkingRunning,
            .distanceCycling,
            .activeEnergyBurned,
            .restingHeartRate,
            .vo2Max
        ]
        for id in ids {
            if let t = HKQuantityType.quantityType(forIdentifier: id) { types.insert(t) }
        }
        types.insert(HKObjectType.workoutType())
        return types
    }()

    // MARK: - Request Permissions
    func requestPermissions() async {
        guard isAvailable else { return }
        do {
            try await store.requestAuthorization(toShare: [], read: readTypes)
            isAuthorized = true
            await syncRecentWorkouts()
        } catch {
            print("[HealthKit] permission error:", error)
        }
    }

    // MARK: - Sync recent 7-day workouts to backend
    func syncRecentWorkouts() async {
        guard isAvailable else { return }
        let anchor = Date().addingTimeInterval(-7 * 24 * 3600)
        let predicate = HKQuery.predicateForSamples(withStart: anchor, end: Date())

        await withCheckedContinuation { (continuation: CheckedContinuation<Void, Never>) in
            let query = HKSampleQuery(
                sampleType: HKObjectType.workoutType(),
                predicate: predicate,
                limit: 50,
                sortDescriptors: [NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: false)]
            ) { _, samples, error in
                guard let workouts = samples as? [HKWorkout], error == nil else {
                    continuation.resume()
                    return
                }
                Task {
                    var payload: [[String: Any]] = []
                    for w in workouts {
                        var item: [String: Any] = [
                            "workout_type": w.workoutActivityType.name,
                            "start_time": ISO8601DateFormatter().string(from: w.startDate),
                            "end_time": ISO8601DateFormatter().string(from: w.endDate),
                            "duration_min": w.duration / 60.0,
                            "calories": w.totalEnergyBurned?.doubleValue(for: .kilocalorie()) ?? 0
                        ]
                        if let dist = w.totalDistance?.doubleValue(for: .meter()) {
                            item["distance_km"] = dist / 1000.0
                        }
                        payload.append(item)
                    }
                    if !payload.isEmpty {
                        try? await AlfredAPI.shared.syncWorkouts(payload)
                    }
                    continuation.resume()
                }
            }
            store.execute(query)
        }
    }

    // MARK: - Fetch today's step count
    func fetchTodaySteps() async -> Int {
        guard isAvailable, let type = HKQuantityType.quantityType(forIdentifier: .stepCount) else { return 0 }
        let start = Calendar.current.startOfDay(for: Date())
        let predicate = HKQuery.predicateForSamples(withStart: start, end: Date())
        return await withCheckedContinuation { continuation in
            let query = HKStatisticsQuery(quantityType: type, quantitySamplePredicate: predicate, options: .cumulativeSum) { _, result, _ in
                let steps = Int(result?.sumQuantity()?.doubleValue(for: .count()) ?? 0)
                continuation.resume(returning: steps)
            }
            store.execute(query)
        }
    }

    // MARK: - Fetch latest heart rate
    func fetchLatestHeartRate() async -> Int? {
        guard isAvailable, let type = HKQuantityType.quantityType(forIdentifier: .heartRate) else { return nil }
        return await withCheckedContinuation { continuation in
            let query = HKSampleQuery(
                sampleType: type, predicate: nil, limit: 1,
                sortDescriptors: [NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: false)]
            ) { _, samples, _ in
                let bpm = (samples?.first as? HKQuantitySample)
                    .map { Int($0.quantity.doubleValue(for: HKUnit(from: "count/min"))) }
                continuation.resume(returning: bpm)
            }
            store.execute(query)
        }
    }
}

// MARK: - HKWorkoutActivityType name helper
extension HKWorkoutActivityType {
    var name: String {
        switch self {
        case .running:          return "running"
        case .cycling:          return "cycling"
        case .swimming:         return "swimming"
        case .yoga:             return "yoga"
        case .walking:          return "walking"
        case .functionalStrengthTraining, .traditionalStrengthTraining: return "gym"
        case .highIntensityIntervalTraining: return "hiit"
        case .dance:            return "dance"
        case .tennis:           return "tennis"
        case .basketball:       return "basketball"
        case .soccer:           return "soccer"
        default:                return "workout"
        }
    }
}
