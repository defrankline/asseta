#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaOwnerKit
import SwiftUI
import UIKit

/// Go-live banner on the Overview (strings doc "Go-live checklist"): tap opens the checklist.
struct SetupBannerView: View {
    let text: String
    let open: () -> Void

    var body: some View {
        Button(action: open) {
            HStack(spacing: 12) {
                Image(systemName: "checklist").font(.title2).foregroundStyle(Brand.slate).accessibilityHidden(true)
                VStack(alignment: .leading, spacing: 2) {
                    Text(text).font(.subheadline.weight(.semibold)).foregroundStyle(Brand.slate)
                    Text(SetupTexts.bannerCaption).font(.caption).foregroundStyle(Brand.slate.opacity(0.85))
                }
                Spacer(minLength: 0)
                Image(systemName: "chevron.right").foregroundStyle(Brand.slate).accessibilityHidden(true)
            }
            .padding(12)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Brand.amber.opacity(0.9), in: RoundedRectangle(cornerRadius: 12))
        }
        .buttonStyle(.plain)
        .accessibilityElement(children: .combine)
        .accessibilityAddTraits(.isButton)
        .accessibilityIdentifier("setup.banner")
    }
}

/// The go-live checklist: progress, one card per step with its parts, the step action (app screen or web) and the
/// owner's choices (not needed / undo / default controls), online only.
struct SetupChecklistView: View {
    let model: OwnerModel
    @State private var loader = Loader<SetupChecklistDTO>()
    @State private var working = false
    @State private var actionError: String?
    @State private var notNeededStep: SetupStepDTO?
    @State private var reason = ""
    @State private var confirmingControls = false
    @State private var controlsNote = ""
    @Environment(\.openURL) private var openURL

    private typealias T = SetupTexts
    private typealias P = SetupPresentation

    var body: some View {
        content
            .navigationTitle(T.title)
            .staleBanner(loader, model: model)
            .refreshable { await reload() }
            .task(id: model.changeTick) { await reload() }
            .alert(T.notNeededTitle(notNeededStep?.title ?? ""), isPresented: Binding(
                get: { notNeededStep != nil }, set: { if !$0 { notNeededStep = nil } })) {
                TextField(T.notNeededReason, text: Binding(get: { reason }, set: { reason = String($0.prefix(500)) }))
                    .accessibilityIdentifier("setup.reason")
                Button(T.cancel, role: .cancel) { notNeededStep = nil }
                Button(T.markNotNeeded) {
                    let step = notNeededStep
                    notNeededStep = nil
                    if let step { Task { await markNotNeeded(step) } }
                }
                .disabled(!P.isValidReason(reason))
            } message: {
                Text(T.notNeededHint)
            }
            .alert(T.controlsTitle, isPresented: $confirmingControls) {
                TextField(T.controlsNote, text: Binding(get: { controlsNote }, set: { controlsNote = String($0.prefix(500)) }))
                    .accessibilityIdentifier("setup.controlsNote")
                Button(T.cancel, role: .cancel) {}
                Button(T.controlsConfirm) { Task { await confirmControls() } }
                    .disabled(!P.isValidNote(controlsNote))
            } message: {
                Text(T.controlsMessage)
            }
    }

    @ViewBuilder private var content: some View {
        if let checklist = loader.value {
            list(checklist)
        } else if let error = loader.error {
            LoadFailure(message: error) { await reload() }
        } else {
            ProgressView().frame(maxWidth: .infinity, maxHeight: .infinity)
        }
    }

    /// The manage gate (nil = the choices are offered).
    private var block: MutationBlock? {
        model.mutationBlock(permitted: model.features.setupManage, showingCachedData: loader.isFromCache)
    }

    private func list(_ checklist: SetupChecklistDTO) -> some View {
        List {
            Section {
                VStack(alignment: .leading, spacing: 8) {
                    Text(T.progress(done: checklist.stepsDone, total: checklist.stepsTotal)).font(.headline)
                    ProgressView(value: Double(max(0, min(100, checklist.percent))), total: 100).tint(Brand.amber)
                    if checklist.complete { Text(T.complete).font(.subheadline).foregroundStyle(Palette.live) }
                    Text(T.asOf(OwnerFormat.stamp(checklist.asOf))).font(.caption).foregroundStyle(.secondary)
                }
                .accessibilityElement(children: .combine)
                if model.features.setupManage, let block { BlockedNote(block: block) }
                if let actionError {
                    Text(actionError).font(.footnote).foregroundStyle(Palette.offline).accessibilityIdentifier("setup.error")
                }
            }
            ForEach(checklist.orderedSteps) { step in
                Section { stepCard(step, checklist) }
            }
            Section { } footer: { Text(T.footer) }
        }
        .disabled(working)
    }

    @ViewBuilder private func stepCard(_ step: SetupStepDTO, _ checklist: SetupChecklistDTO) -> some View {
        let muted = step.status == .notApplicable
        VStack(alignment: .leading, spacing: 6) {
            HStack(alignment: .firstTextBaseline) {
                Text(P.title(step)).font(.headline)
                Spacer()
                Pill(text: T.status(step.status), color: color(step.status))
            }
            Text(step.description).font(.subheadline).foregroundStyle(.secondary)
            if let count = P.count(step) { FootNote(count) }
        }
        .opacity(muted ? 0.55 : 1)
        .accessibilityElement(children: .combine)
        ForEach(step.checks) { check in checkRow(check, step) }
        if let note = P.notNeededNote(step) { FootNote(note) }
        if let note = P.controlsNote(step, checklist: checklist) { FootNote(note) }
        if let action = P.action(for: step, features: model.features) {
            if P.needsAccess(step, features: model.features) { FootNote(T.needsAccess) }
            actionButton(action).accessibilityIdentifier("setup.action.\(step.key.rawValue)")
        }
        if model.features.setupManage {
            // Shown to manage holders, disabled with the gate's reason (once at the top) when blocked.
            let enabled = block == nil && !working
            if P.canConfirmControls(step, checklist: checklist) {
                Button(T.controlsFine) { controlsNote = ""; confirmingControls = true }
                    .disabled(!enabled)
                    .accessibilityIdentifier("setup.controlsFine")
            }
            if P.canMarkNotNeeded(step) {
                Button(T.markNotNeeded) { reason = ""; notNeededStep = step }
                    .disabled(!enabled)
                    .accessibilityIdentifier("setup.notNeeded.\(step.key.rawValue)")
            }
            if P.canUndo(step) {
                Button(T.undo) { Task { await undo(step) } }
                    .disabled(!enabled)
                    .accessibilityIdentifier("setup.undo.\(step.key.rawValue)")
            }
        }
    }

    @ViewBuilder private func checkRow(_ check: SetupCheckDTO, _ step: SetupStepDTO) -> some View {
        let row = HStack(alignment: .firstTextBaseline, spacing: 8) {
            Image(systemName: check.done ? "checkmark.circle.fill" : "circle")
                .foregroundStyle(check.done ? Palette.live : .secondary)
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 2) {
                Text(check.label).font(.subheadline)
                let details = [check.done ? T.checkDone : T.checkTodo, P.count(check), check.optional ? T.optional : nil]
                Text(details.compactMap { $0 }.joined(separator: " · ")).font(.caption).foregroundStyle(.secondary)
            }
            Spacer(minLength: 0)
        }
        .opacity(step.status == .notApplicable ? 0.55 : 1)
        .accessibilityElement(children: .combine)
        if let action = P.action(for: check, of: step, features: model.features) {
            target(action) { row }
        } else {
            row
        }
    }

    @ViewBuilder private func actionButton(_ action: SetupTarget) -> some View {
        target(action) {
            Label(action.label, systemImage: isWeb(action) ? "safari" : "arrow.right.circle")
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(Brand.amber)
        }
    }

    @ViewBuilder private func target(_ action: SetupTarget, @ViewBuilder label: () -> some View) -> some View {
        switch action {
        case let .app(route, _):
            NavigationLink(value: route) { label() }
        case let .web(path):
            Button { openWeb(path) } label: { label() }.buttonStyle(.plain)
        }
    }

    private func isWeb(_ action: SetupTarget) -> Bool {
        if case .web = action { return true }
        return false
    }

    private func openWeb(_ path: String) {
        guard let url = model.session.configuration?.webURL(for: path) else { return }
        openURL(url)
    }

    private func color(_ status: SetupStepStatus) -> Color {
        switch status {
        case .done: Palette.live
        case .todo: Palette.warning
        default: Palette.neutral
        }
    }

    // MARK: - Writes (online only, never queued)

    private func markNotNeeded(_ step: SetupStepDTO) async {
        guard P.isValidReason(reason) else { return }
        let text = reason
        await send { try await $0.send(OwnerAPI.markStepNotNeeded(step.key, reason: text, idempotencyKey: UUID())) }
    }

    private func undo(_ step: SetupStepDTO) async {
        await send { try await $0.send(OwnerAPI.undoStepNotNeeded(step.key, idempotencyKey: UUID())) }
    }

    private func confirmControls() async {
        guard P.isValidNote(controlsNote) else { return }
        let note = controlsNote
        await send { try await $0.send(OwnerAPI.confirmControls(note: note, idempotencyKey: UUID())) }
    }

    private func send(_ call: (OwnerRepository) async throws -> SetupChecklistDTO) async {
        guard let repository = model.repository, block == nil, !working else { return }
        working = true
        actionError = nil
        defer { working = false }
        do {
            let checklist = try await call(repository)
            loader.replace(checklist)
            model.noteSetup(checklist)
        } catch {
            actionError = P.errorMessage(error)
            model.handle(error)
        }
    }

    private func reload() async {
        await loader.load(model, .setupChecklist, OwnerAPI.setupChecklist())
        if let checklist = loader.value, !loader.isFromCache { model.noteSetup(checklist) }
    }
}
#endif
