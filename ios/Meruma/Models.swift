import Foundation

struct IndexArticle: Codable, Hashable {
    let idx: Int
    let title: String
    let summary: String
    let countries: [String]
    let genres: [String]
}

struct IndexIssue: Codable, Identifiable, Hashable {
    let id: String
    let newsletter: String
    let newsletter_name: String
    let number: Int?
    let title: String
    let date: String
    let headline: String
    let articles: [IndexArticle]

    var dateValue: Date { DateParse.parse(date) }
    var numberLabel: String { number.map { "第\($0)号" } ?? "" }
}

struct IndexFile: Codable {
    let updated_at: String
    let issues: [IndexIssue]
}

struct IssueSummary: Codable, Hashable {
    let toc: [String]
    let points: [String]
    let changes: [String]
    let watch_next: [String]

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        toc = (try? c.decode([String].self, forKey: .toc)) ?? []
        points = (try? c.decode([String].self, forKey: .points)) ?? []
        changes = (try? c.decode([String].self, forKey: .changes)) ?? []
        watch_next = (try? c.decode([String].self, forKey: .watch_next)) ?? []
    }
}

struct IssueArticle: Codable, Hashable, Identifiable {
    let idx: Int
    let title: String
    let body: String
    let summary: String
    let points: [String]
    let countries: [String]
    let genres: [String]
    var id: Int { idx }
}

struct Issue: Codable, Identifiable {
    let id: String
    let newsletter: String
    let newsletter_name: String
    let number: Int?
    let title: String
    let date: String
    let headline: String
    let gmail_link: String
    let full_text: String
    let summary: IssueSummary
    let articles: [IssueArticle]

    var dateValue: Date { DateParse.parse(date) }
    var numberLabel: String { number.map { "第\($0)号" } ?? "" }
}

enum DateParse {
    private static let f1: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter(); f.formatOptions = [.withInternetDateTime]; return f
    }()
    private static let f2: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter(); f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]; return f
    }()
    static func parse(_ s: String) -> Date { f1.date(from: s) ?? f2.date(from: s) ?? .distantPast }

    private static let out: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "ja_JP")
        f.timeZone = TimeZone(identifier: "Asia/Tokyo")
        f.dateFormat = "M/d(E) HH:mm"
        return f
    }()
    static func label(_ d: Date) -> String { d == .distantPast ? "" : out.string(from: d) }
}

enum FilterKind: String, Hashable { case country, genre }
struct FilterRoute: Hashable { let kind: FilterKind; let name: String }
struct IssueRoute: Hashable { let id: String; let articleIdx: Int? }

// 号ごとの「一言学び」
struct Learning: Codable, Identifiable {
    let issueID: String
    let issueTitle: String
    let text: String
    let date: Date
    var id: String { issueID }
}

// 「きょうの記録」へ渡す形（きょうの記録側の MerumaImport.swift と同じ形にそろえる）
struct SharedLearning: Codable {
    let issueID: String
    let issueTitle: String
    let text: String
    let date: Date
}
