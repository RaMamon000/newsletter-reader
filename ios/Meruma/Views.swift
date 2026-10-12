import SwiftUI

// MARK: ルート
struct RootView: View {
    @EnvironmentObject var store: Store
    @State private var tab = 0
    @State private var launchArgsDone = false

    var body: some View {
        TabView(selection: $tab) {
            NavigationStack { NewIssuesView().merumaDestinations() }
                .tabItem { Label("新着", systemImage: "envelope") }
                .badge(store.unreadCount).tag(0)
            NavigationStack { GroupListView(kind: .country).merumaDestinations() }
                .tabItem { Label("国別", systemImage: "globe.asia.australia") }.tag(1)
            NavigationStack { GroupListView(kind: .genre).merumaDestinations() }
                .tabItem { Label("ジャンル別", systemImage: "tag") }.tag(2)
            NavigationStack { SettingsView() }
                .tabItem { Label("設定", systemImage: "gearshape") }.tag(3)
        }
        .sheet(item: Binding(get: { store.openIssueID.map { OpenID(id: $0) } },
                             set: { store.openIssueID = $0?.id })) { o in
            NavigationStack {
                IssueView(id: o.id, focusIdx: nil)
                    .merumaDestinations()
                    .toolbar { ToolbarItem(placement: .topBarLeading) { Button("閉じる") { store.openIssueID = nil } } }
            }
        }
        .onAppear {
            // 画面確認用: -tab N / -issue ID
            let a = ProcessInfo.processInfo.arguments
            if let i = a.firstIndex(of: "-tab"), i + 1 < a.count, let n = Int(a[i + 1]) { tab = n }
            if let i = a.firstIndex(of: "-issue"), i + 1 < a.count { store.openIssueID = a[i + 1] }
        }
    }
}
struct OpenID: Identifiable { let id: String }

extension View {
    func merumaDestinations() -> some View {
        self
            .navigationDestination(for: IssueRoute.self) { IssueView(id: $0.id, focusIdx: $0.articleIdx) }
            .navigationDestination(for: FilterRoute.self) { FilterListView(route: $0) }
    }
}

// MARK: 新着
struct NewIssuesView: View {
    @EnvironmentObject var store: Store
    var body: some View {
        List {
            if store.usingSample {
                Label("サンプルデータを表示中（まだ本物のデータを取得できていません）", systemImage: "info.circle")
                    .font(.footnote).foregroundStyle(.secondary)
            }
            if let e = store.lastError {
                Label(e, systemImage: "exclamationmark.triangle").font(.footnote).foregroundStyle(.orange)
            }
            ForEach(store.issues.sorted { $0.dateValue > $1.dateValue }) { i in
                NavigationLink(value: IssueRoute(id: i.id, articleIdx: nil)) { IssueRow(issue: i) }
            }
        }
        .navigationTitle("新着")
        .refreshable { await store.refresh() }
        .overlay { if store.issues.isEmpty { ContentUnavailableView("まだ号がありません", systemImage: "envelope", description: Text("引っ張って更新してください")) } }
    }
}

struct IssueRow: View {
    @EnvironmentObject var store: Store
    let issue: IndexIssue
    var body: some View {
        let unread = !store.readIDs.contains(issue.id)
        HStack(alignment: .top, spacing: 10) {
            Circle().fill(unread ? Color.accentColor : .clear).frame(width: 10, height: 10).padding(.top, 7)
            VStack(alignment: .leading, spacing: 5) {
                Text("\(issue.newsletter_name)　\(issue.numberLabel)").font(.caption).foregroundStyle(.secondary)
                Text(issue.title).font(.headline).fontWeight(unread ? .bold : .regular)
                Text(issue.headline).font(.subheadline).foregroundStyle(.secondary).lineSpacing(4)
                Text(DateParse.label(issue.dateValue)).font(.caption2).foregroundStyle(.tertiary)
            }
        }
        .padding(.vertical, 4)
    }
}

// MARK: 国別・ジャンル別
struct GroupListView: View {
    @EnvironmentObject var store: Store
    let kind: FilterKind
    var body: some View {
        List(store.counts(kind), id: \.name) { item in
            NavigationLink(value: FilterRoute(kind: kind, name: item.name)) {
                HStack { Text(item.name); Spacer(); Text("\(item.count)件").foregroundStyle(.secondary).monospacedDigit() }
            }
        }
        .navigationTitle(kind == .country ? "国別" : "ジャンル別")
        .refreshable { await store.refresh() }
        .overlay { if store.issues.isEmpty { ContentUnavailableView("記事がありません", systemImage: "tray") } }
    }
}

struct FilterListView: View {
    @EnvironmentObject var store: Store
    let route: FilterRoute
    var body: some View {
        List(store.entries(route)) { e in
            NavigationLink(value: IssueRoute(id: e.issue.id, articleIdx: e.article.idx)) {
                VStack(alignment: .leading, spacing: 6) {
                    Text("\(e.issue.newsletter_name)　\(e.issue.numberLabel)　\(DateParse.label(e.issue.dateValue))")
                        .font(.caption).foregroundStyle(.secondary)
                    Text(e.article.title).font(.headline)
                    Text(e.article.summary).font(.subheadline).foregroundStyle(.secondary).lineSpacing(4)
                }.padding(.vertical, 4)
            }
        }
        .navigationTitle(route.name)
        .navigationBarTitleDisplayMode(.inline)
    }
}

// MARK: 号の画面
struct IssueView: View {
    @EnvironmentObject var store: Store
    let id: String
    let focusIdx: Int?
    @State private var issue: Issue?
    @State private var failed = false
    @State private var showFull = ProcessInfo.processInfo.arguments.contains("-full")

    var body: some View {
        Group {
            if let issue {
                content(issue)
            } else if failed {
                ContentUnavailableView("号を読み込めませんでした", systemImage: "wifi.slash", description: Text("通信できる場所で開き直してください"))
            } else {
                ProgressView("読み込み中…")
            }
        }
        .navigationBarTitleDisplayMode(.inline)
        .task(id: id) {
            issue = await store.loadIssue(id)
            failed = issue == nil
            if issue != nil { store.markRead(id) }
        }
    }

    private func content(_ i: Issue) -> some View {
        ScrollViewReader { proxy in
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    VStack(alignment: .leading, spacing: 6) {
                        Text("\(i.newsletter_name)　\(i.numberLabel)").font(.subheadline).foregroundStyle(.secondary)
                        Text(i.title).font(.title2.bold()).lineSpacing(5)
                        Text(DateParse.label(i.dateValue)).font(.caption).foregroundStyle(.tertiary)
                    }
                    Picker("表示", selection: $showFull) {
                        Text("要約").tag(false); Text("全文").tag(true)
                    }.pickerStyle(.segmented)

                    if !showFull { summaryBlock(i.summary) }

                    ForEach(i.articles) { a in
                        articleBlock(a).id(a.idx)
                    }

                    if let url = URL(string: i.gmail_link) {
                        Link(destination: url) { Label("Gmailで開く", systemImage: "arrow.up.right.square").frame(maxWidth: .infinity) }
                            .buttonStyle(.borderedProminent).controlSize(.large)
                    }
                }
                .padding(.horizontal, 18).padding(.vertical, 12)
            }
            .onAppear {
                if let f = focusIdx { DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) { withAnimation { proxy.scrollTo(f, anchor: .top) } } }
            }
        }
    }

    private func summaryBlock(_ s: IssueSummary) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            bullets("今回の内容", s.toc)
            bullets("重要ポイント", s.points)
            bullets("前の号からの変化", s.changes)
            bullets("次号の注目", s.watch_next)
        }
        .padding(16)
        .background(Color(.secondarySystemBackground), in: RoundedRectangle(cornerRadius: 14))
    }

    @ViewBuilder private func bullets(_ title: String, _ items: [String]) -> some View {
        if !items.isEmpty {
            VStack(alignment: .leading, spacing: 8) {
                Text(title).font(.headline)
                ForEach(items, id: \.self) { t in
                    HStack(alignment: .firstTextBaseline, spacing: 8) {
                        Text("・"); Text(t).lineSpacing(7)
                    }.font(.body)
                }
            }
        }
    }

    private func articleBlock(_ a: IssueArticle) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Divider()
            Text(a.title).font(.title3.bold()).lineSpacing(5)
            FlowLayout(spacing: 6) {
                ForEach(a.countries, id: \.self) { c in
                    NavigationLink(value: FilterRoute(kind: .country, name: c)) { Tag(text: c, color: .blue) }
                }
                ForEach(a.genres, id: \.self) { g in
                    NavigationLink(value: FilterRoute(kind: .genre, name: g)) { Tag(text: g, color: .orange) }
                }
            }
            if showFull {
                Text(a.body).font(.body).lineSpacing(10).textSelection(.enabled)
            } else {
                Text(a.summary).font(.body).lineSpacing(8)
                ForEach(a.points, id: \.self) { p in
                    HStack(alignment: .firstTextBaseline, spacing: 8) { Text("・"); Text(p).lineSpacing(6) }
                        .font(.callout).foregroundStyle(.secondary)
                }
            }
        }
    }
}

struct Tag: View {
    let text: String; let color: Color
    var body: some View {
        Text(text).font(.caption.weight(.medium)).foregroundStyle(color)
            .padding(.horizontal, 10).padding(.vertical, 4)
            .background(color.opacity(0.14), in: Capsule())
    }
}

struct FlowLayout: Layout {
    var spacing: CGFloat = 6
    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        arrange(proposal.width ?? 300, subviews).size
    }
    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let r = arrange(bounds.width, subviews)
        for (i, p) in r.points.enumerated() {
            subviews[i].place(at: CGPoint(x: bounds.minX + p.x, y: bounds.minY + p.y), proposal: .unspecified)
        }
    }
    private func arrange(_ width: CGFloat, _ subviews: Subviews) -> (size: CGSize, points: [CGPoint]) {
        var x: CGFloat = 0, y: CGFloat = 0, rowH: CGFloat = 0, maxW: CGFloat = 0
        var pts: [CGPoint] = []
        for s in subviews {
            let sz = s.sizeThatFits(.unspecified)
            if x > 0 && x + sz.width > width { x = 0; y += rowH + spacing; rowH = 0 }
            pts.append(CGPoint(x: x, y: y))
            x += sz.width + spacing; rowH = max(rowH, sz.height); maxW = max(maxW, x - spacing)
        }
        return (CGSize(width: maxW, height: y + rowH), pts)
    }
}

// MARK: 設定
struct SettingsView: View {
    @EnvironmentObject var store: Store
    @State private var copied = false
    var body: some View {
        Form {
            Section("通知") {
                LabeledContent("許可の状態", value: store.notifStatus)
                VStack(alignment: .leading, spacing: 8) {
                    Text("デバイストークン").font(.caption).foregroundStyle(.secondary)
                    Text(store.deviceToken.isEmpty ? "（まだ取得できていません）" : store.deviceToken)
                        .font(.system(.footnote, design: .monospaced)).textSelection(.enabled)
                    Button(copied ? "コピーしました" : "トークンをコピー") {
                        UIPasteboard.general.string = store.deviceToken
                        copied = true
                    }.disabled(store.deviceToken.isEmpty)
                }
            }
            Section("データ") {
                LabeledContent("最終更新", value: store.lastUpdated.map { DateParse.label($0) } ?? "未取得")
                LabeledContent("表示中のデータ", value: store.usingSample ? "サンプル" : "取得済み")
                LabeledContent("号の数", value: "\(store.issues.count)")
                if let e = store.lastError { Text(e).font(.footnote).foregroundStyle(.orange) }
                Button { Task { await store.refresh() } } label: {
                    HStack { Text("今すぐ更新"); if store.isRefreshing { Spacer(); ProgressView() } }
                }
            }
        }
        .navigationTitle("設定")
        .task { await store.refreshNotifStatus() }
    }
}
