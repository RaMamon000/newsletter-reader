import Foundation
import SwiftUI
import UserNotifications

@MainActor
final class Store: ObservableObject {
    static let shared = Store()

    static let baseURL = "https://raw.githubusercontent.com/RaMamon000/newsletter-reader/main/data"

    @Published var issues: [IndexIssue] = []
    @Published var readIDs: Set<String>
    @Published var lastUpdated: Date?
    @Published var usingSample = false
    @Published var isRefreshing = false
    @Published var lastError: String?
    @Published var openIssueID: String?
    @Published var deviceToken: String
    @Published var notifStatus: String = "確認中"
    @Published var notes: [String: Learning] = [:]

    private let readKey = "readIssueIDs"
    private let updatedKey = "lastUpdated"
    private let tokenKey = "apnsToken"
    private let dir: URL

    private init() {
        let d = UserDefaults.standard
        readIDs = Set(d.stringArray(forKey: readKey) ?? [])
        lastUpdated = d.object(forKey: updatedKey) as? Date
        deviceToken = d.string(forKey: tokenKey) ?? ""
        let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0].appendingPathComponent("cache", isDirectory: true)
        try? FileManager.default.createDirectory(at: base.appendingPathComponent("issues"), withIntermediateDirectories: true)
        dir = base
        loadLocal()
        loadNotes()
        shareWithLifeLog()
    }

    // MARK: 一言学び（端末内だけに保存。GitHub には送らない）
    private var notesURL: URL { dir.deletingLastPathComponent().appendingPathComponent("learnings.json") }

    private func loadNotes() {
        guard let data = try? Data(contentsOf: notesURL),
              let list = try? JSONDecoder().decode([Learning].self, from: data) else { return }
        notes = Dictionary(list.map { ($0.issueID, $0) }, uniquingKeysWith: { a, _ in a })
    }

    func saveNote(issueID: String, title: String, text: String) {
        let t = text.trimmingCharacters(in: .whitespacesAndNewlines)
        if t.isEmpty {
            notes[issueID] = nil
        } else {
            notes[issueID] = Learning(issueID: issueID, issueTitle: title, text: t, date: Date())
        }
        if let data = try? JSONEncoder().encode(Array(notes.values)) {
            try? data.write(to: notesURL, options: [.atomic, .completeFileProtection])
        }
        shareWithLifeLog()
    }

    /// 「きょうの記録」と共有する置き場（App Group）にも書き出す。きょうの記録が開いたときに取り込む
    static let lifeLogGroup = "group.com.ramamon.lifelog"
    static let sharedLearningsKey = "meruma.learnings"
    func shareWithLifeLog() {
        let list = notes.values.map { SharedLearning(issueID: $0.issueID, issueTitle: $0.issueTitle, text: $0.text, date: $0.date) }
        if let data = try? JSONEncoder().encode(list) {
            UserDefaults(suiteName: Self.lifeLogGroup)?.set(data, forKey: Self.sharedLearningsKey)
        }
    }

    // MARK: 読み込み（キャッシュ → サンプル）
    private func loadLocal() {
        if let data = try? Data(contentsOf: dir.appendingPathComponent("index.json.enc")),
           let idx = decodeIndex(data) {
            issues = idx.issues; usingSample = false
        } else if let url = Bundle.main.url(forResource: "sample_index.json", withExtension: "enc"),
                  let data = try? Data(contentsOf: url), let idx = decodeIndex(data) {
            issues = idx.issues; usingSample = true
        }
        updateBadge()
    }

    private func decodeIndex(_ enc: Data) -> IndexFile? {
        guard let plain = try? DataCrypto.decrypt(enc) else { return nil }
        return try? JSONDecoder().decode(IndexFile.self, from: plain)
    }

    // MARK: 取得
    private func fetch(_ path: String) async throws -> Data {
        var comps = URLComponents(string: "\(Store.baseURL)/\(path)")!
        comps.queryItems = [URLQueryItem(name: "t", value: String(Int(Date().timeIntervalSince1970)))]
        var req = URLRequest(url: comps.url!)
        req.cachePolicy = .reloadIgnoringLocalCacheData
        req.timeoutInterval = 20
        let (data, resp) = try await URLSession.shared.data(for: req)
        guard let http = resp as? HTTPURLResponse, http.statusCode == 200 else {
            throw NSError(domain: "fetch", code: (resp as? HTTPURLResponse)?.statusCode ?? -1)
        }
        return data
    }

    func refresh() async {
        if isRefreshing { return }
        isRefreshing = true
        defer { isRefreshing = false }
        do {
            let enc = try await fetch("index.json.enc")
            guard let idx = decodeIndex(enc) else { throw NSError(domain: "decrypt", code: 0) }
            try? enc.write(to: dir.appendingPathComponent("index.json.enc"))
            issues = idx.issues
            usingSample = false
            lastUpdated = Date()
            UserDefaults.standard.set(lastUpdated, forKey: updatedKey)
            lastError = nil
            updateBadge()
            // 新しい順に最大30号をキャッシュ（オフライン用）
            for i in idx.issues.prefix(30) where !FileManager.default.fileExists(atPath: issueURL(i.id).path) {
                if let d = try? await fetch("issues/\(i.id).json.enc") { try? d.write(to: issueURL(i.id)) }
            }
        } catch {
            let code = (error as NSError)
            lastError = code.domain == "fetch" ? "取得できませんでした（HTTP \(code.code)）" : "取得できませんでした（\(code.domain)）"
        }
    }

    private func issueURL(_ id: String) -> URL { dir.appendingPathComponent("issues/\(id).json.enc") }

    func loadIssue(_ id: String) async -> Issue? {
        if let i = readIssue(id) { return i }
        if let d = try? await fetch("issues/\(id).json.enc") {
            try? d.write(to: issueURL(id))
            if let i = decodeIssue(d) { return i }
        }
        if let url = Bundle.main.url(forResource: "sample_\(id).json", withExtension: "enc"),
           let d = try? Data(contentsOf: url) { return decodeIssue(d) }
        return nil
    }

    private func readIssue(_ id: String) -> Issue? {
        guard let d = try? Data(contentsOf: issueURL(id)) else { return nil }
        return decodeIssue(d)
    }

    private func decodeIssue(_ enc: Data) -> Issue? {
        guard let plain = try? DataCrypto.decrypt(enc) else { return nil }
        return try? JSONDecoder().decode(Issue.self, from: plain)
    }

    // MARK: 既読・バッジ
    var unreadCount: Int { issues.filter { !readIDs.contains($0.id) }.count }

    func markRead(_ id: String) {
        guard !readIDs.contains(id) else { return }
        readIDs.insert(id)
        UserDefaults.standard.set(Array(readIDs), forKey: readKey)
        updateBadge()
    }

    func updateBadge() {
        let n = unreadCount
        UNUserNotificationCenter.current().setBadgeCount(n)
    }

    // MARK: 通知
    func open(issueID: String) {
        openIssueID = issueID
        Task { await refresh() }
    }

    func setToken(_ token: String) {
        deviceToken = token
        UserDefaults.standard.set(token, forKey: tokenKey)
        if let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first {
            try? token.write(to: docs.appendingPathComponent("apns_token.txt"), atomically: true, encoding: .utf8)
        }
    }

    func refreshNotifStatus() async {
        let s = await UNUserNotificationCenter.current().notificationSettings().authorizationStatus
        switch s {
        case .authorized: notifStatus = "許可されています"
        case .denied: notifStatus = "拒否されています（設定アプリで変更）"
        case .notDetermined: notifStatus = "未確認"
        case .provisional: notifStatus = "仮の許可"
        case .ephemeral: notifStatus = "一時的な許可"
        @unknown default: notifStatus = "不明"
        }
    }

    // MARK: 集計
    struct Entry: Identifiable { let issue: IndexIssue; let article: IndexArticle; var id: String { "\(issue.id)#\(article.idx)" } }

    func counts(_ kind: FilterKind) -> [(name: String, count: Int)] {
        var d: [String: Int] = [:]
        for i in issues { for a in i.articles { for t in (kind == .country ? a.countries : a.genres) { d[t, default: 0] += 1 } } }
        return d.map { ($0.key, $0.value) }.sorted { $0.1 != $1.1 ? $0.1 > $1.1 : $0.0 < $1.0 }
    }

    func entries(_ r: FilterRoute) -> [Entry] {
        issues.sorted { $0.dateValue > $1.dateValue }.flatMap { i in
            i.articles.filter { (r.kind == .country ? $0.countries : $0.genres).contains(r.name) }.map { Entry(issue: i, article: $0) }
        }
    }
}
