import SwiftUI
import UserNotifications

final class AppDelegate: NSObject, UIApplicationDelegate, UNUserNotificationCenterDelegate {
    func application(_ application: UIApplication, didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil) -> Bool {
        let center = UNUserNotificationCenter.current()
        center.delegate = self
        if ProcessInfo.processInfo.arguments.contains("-noperm") { return true }  // 画面確認用
        center.requestAuthorization(options: [.alert, .badge, .sound]) { _, _ in
            DispatchQueue.main.async { application.registerForRemoteNotifications() }
            Task { await Store.shared.refreshNotifStatus() }
        }
        return true
    }

    func application(_ application: UIApplication, didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data) {
        let hex = deviceToken.map { String(format: "%02x", $0) }.joined()
        Task { @MainActor in Store.shared.setToken(hex) }
    }

    func application(_ application: UIApplication, didFailToRegisterForRemoteNotificationsWithError error: Error) {
        Task { @MainActor in Store.shared.lastError = "通知の登録に失敗: \(error.localizedDescription)" }
    }

    // 画面を見ている最中も通知を出す
    func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification) async -> UNNotificationPresentationOptions {
        Task { await Store.shared.refresh() }
        return [.banner, .list, .sound, .badge]
    }

    // 通知タップ → その号を開く
    func userNotificationCenter(_ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse) async {
        if let id = response.notification.request.content.userInfo["issue_id"] as? String {
            await MainActor.run { Store.shared.open(issueID: id) }
        }
    }

    // サイレント通知（content-available）で更新
    func application(_ application: UIApplication, didReceiveRemoteNotification userInfo: [AnyHashable: Any]) async -> UIBackgroundFetchResult {
        await Store.shared.refresh()
        return .newData
    }
}

@main
struct MerumaApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) var delegate
    @StateObject private var store = Store.shared
    @Environment(\.scenePhase) private var phase

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(store)
                .task { await store.refresh(); await store.refreshNotifStatus() }
                .onChange(of: phase) { _, p in
                    if p == .active { Task { await store.refresh(); await store.refreshNotifStatus() } }
                }
        }
    }
}
