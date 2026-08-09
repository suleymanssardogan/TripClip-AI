import SwiftUI

struct TripDetailView: View {

    let tripID:        Int
    var preloaded:     TripDetail? = nil

    @Environment(AuthEnvironment.self) private var auth
    @Environment(\.dismiss) private var dismiss
    @State private var vm = TripDetailViewModel()
    @State private var focusedPin: LocationPin?
    @State private var isEditing = false
    @State private var showDeleteConfirm = false

    private static let mapAnchor = "trip-detail-map"

    var body: some View {
        ZStack {
            AppColors.background.ignoresSafeArea()

            if vm.isLoading {
                ProgressView().tint(AppColors.accentText)
            } else if let error = vm.error {
                errorView(error)
            } else if let trip = vm.trip {
                tripContent(trip)
            }
        }
        .navigationTitle(vm.trip?.title ?? "Gezi")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            if let trip = vm.trip, !trip.allStops.isEmpty {
                ToolbarItem(placement: .navigationBarTrailing) {
                    NavigationLink(
                        destination: TripOptimizerView(
                            mode: .generate(tripID: trip.id, placeIDs: trip.allStops.map(\.placeId)),
                            onApplied: { Task { await vm.load(tripID: tripID, auth: auth) } }
                        )
                    ) {
                        Image(systemName: "sparkles")
                            .foregroundStyle(AppColors.accentText)
                    }
                }
            }
            if let trip = vm.trip, vm.hasItineraryHistory {
                ToolbarItem(placement: .navigationBarTrailing) {
                    NavigationLink(
                        destination: ItineraryHistoryView(
                            tripID: trip.id,
                            onApplied: { Task { await vm.load(tripID: tripID, auth: auth) } }
                        )
                    ) {
                        Image(systemName: "clock.arrow.circlepath")
                            .foregroundStyle(AppColors.accentText)
                    }
                }
            }
            if vm.trip != nil {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(role: .destructive) {
                        showDeleteConfirm = true
                    } label: {
                        Image(systemName: "trash")
                            .foregroundStyle(AppColors.destructive)
                    }
                }
            }
        }
        .confirmationDialog(
            "Bu geziyi silmek istiyor musun?",
            isPresented: $showDeleteConfirm,
            titleVisibility: .visible
        ) {
            Button("Sil", role: .destructive) {
                Task {
                    if await vm.deleteTrip(auth: auth) { dismiss() }
                }
            }
            Button("Vazgeç", role: .cancel) { }
        } message: {
            Text("Bu işlem geri alınamaz.")
        }
        .alert(
            "Değişiklik kaydedilemedi",
            isPresented: Binding(
                get: { vm.stopEditError != nil },
                set: { if !$0 { vm.stopEditError = nil } }
            )
        ) {
            Button("Tamam", role: .cancel) { vm.stopEditError = nil }
        } message: {
            Text(vm.stopEditError ?? "")
        }
        .task { await vm.load(tripID: tripID, auth: auth, preloaded: preloaded) }
        .task { await vm.refreshItineraryHistoryFlag(tripID: tripID, auth: auth) }
    }

    @ViewBuilder
    private func tripContent(_ trip: TripDetail) -> some View {
        let stops: [TripStop] = trip.allStops
        let pins: [LocationPin] = stops.map(\.asLocationPin)
        let route: [RoutePoint]? = mapRoute(for: stops)

        ScrollViewReader { proxy in
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {

                if !stops.isEmpty {
                    TripMapView(locations: pins, route: route, focusedPin: focusedPin)
                        .frame(height: 260)
                        .clipShape(RoundedRectangle(cornerRadius: 20))
                        .padding(.horizontal, 16)
                        .id(Self.mapAnchor)
                }

                statsStrip(trip).padding(.horizontal, 16)

                if !stops.isEmpty {
                    stopsHeader(stops.count)
                    VStack(spacing: 8) {
                        ForEach(Array(stops.enumerated()), id: \.element.placeId) { offset, stop in
                            if isEditing {
                                LocationCard(
                                    number: offset + 1,
                                    pin:    stop.asLocationPin,
                                    edit:   editActions(for: offset, stop: stop, count: stops.count)
                                )
                            } else {
                                Button {
                                    focusedPin = stop.asLocationPin
                                    withAnimation { proxy.scrollTo(Self.mapAnchor, anchor: .top) }
                                } label: {
                                    LocationCard(number: offset + 1, pin: stop.asLocationPin)
                                }
                                .buttonStyle(PressableButtonStyle())
                            }
                        }
                    }
                    .padding(.horizontal, 16)
                    .disabled(vm.isSavingStops)
                } else {
                    emptyStopsState.padding(.horizontal, 16)
                }

                Color.clear.frame(height: 40)
            }
            .padding(.top, 16)
        }
        }
    }

    private func stopsHeader(_ count: Int) -> some View {
        HStack {
            Text("Duraklar (\(count))")
                .font(.system(size: 14, weight: .semibold))
                .foregroundStyle(AppColors.textSecondary)
                .textCase(.uppercase)
                .tracking(0.8)

            Spacer()

            if vm.isSavingStops {
                ProgressView().controlSize(.small).tint(AppColors.accentText)
            } else {
                Button(isEditing ? "Bitti" : "Düzenle") {
                    withAnimation { isEditing.toggle() }
                }
                .font(.system(size: 14, weight: .semibold))
                .foregroundStyle(AppColors.accentText)
            }
        }
        .padding(.horizontal, 16)
    }

    private func editActions(for offset: Int, stop: TripStop, count: Int) -> LocationCard.EditActions {
        LocationCard.EditActions(
            canMoveUp:   offset > 0,
            canMoveDown: offset < count - 1,
            onMoveUp: {
                Task { await vm.moveStops(from: [offset], to: offset - 1, auth: auth) }
            },
            onMoveDown: {
                Task { await vm.moveStops(from: [offset], to: offset + 2, auth: auth) }
            },
            onDelete: {
                if focusedPin?.index == stop.placeId { focusedPin = nil }
                Task { await vm.deleteStop(stop, auth: auth) }
            }
        )
    }

    private var emptyStopsState: some View {
        VStack(spacing: 10) {
            Image(systemName: "mappin.slash")
                .font(.system(size: 32))
                .foregroundStyle(AppColors.textTertiary)
            Text("Tüm duraklar silindi")
                .font(.system(size: 14))
                .foregroundStyle(AppColors.textSecondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 24)
    }

    private func statsStrip(_ trip: TripDetail) -> some View {
        HStack(spacing: 0) {
            statCell(icon: "mappin.circle.fill", value: "\(trip.allStops.count)", label: "Durak")
            Divider().frame(height: 36).background(AppColors.border)
            statCell(icon: "arrow.triangle.swap", value: distanceString(trip.totalDistanceKm), label: "Mesafe")
            Divider().frame(height: 36).background(AppColors.border)
            statCell(icon: "calendar", value: trip.formattedCreatedAt.isEmpty ? "—" : trip.formattedCreatedAt, label: "Oluşturuldu")
        }
        .padding(.vertical, 14)
        .background(AppColors.surface)
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .overlay(RoundedRectangle(cornerRadius: 16).stroke(AppColors.border, lineWidth: 1))
    }

    private func statCell(icon: String, value: String, label: String) -> some View {
        VStack(spacing: 4) {
            Image(systemName: icon).foregroundStyle(AppColors.textTertiary).font(.system(size: 16))
            Text(value).font(.system(size: 13, weight: .bold)).foregroundStyle(AppColors.text).lineLimit(1)
            Text(label).font(.system(size: 11)).foregroundStyle(AppColors.textSecondary)
        }
        .frame(maxWidth: .infinity)
    }

    private func mapRoute(for stops: [TripStop]) -> [RoutePoint]? {
        guard stops.count > 1 else { return nil }
        return stops.map { RoutePoint(latitude: $0.latitude, longitude: $0.longitude, name: $0.name) }
    }

    private func distanceString(_ km: Double?) -> String {
        guard let km, km > 0 else { return "—" }
        return String(format: "%.1f km", km)
    }

    private func errorView(_ error: APIError) -> some View {
        VStack(spacing: 16) {
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 48))
                .foregroundStyle(AppColors.destructive)
            Text(error.localizedDescription ?? "Yüklenemedi.")
                .foregroundStyle(AppColors.textSecondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 40)
            Button("Tekrar Dene") {
                Task { await vm.load(tripID: tripID, auth: auth) }
            }
            .foregroundStyle(AppColors.accentText)
        }
    }
}
