import SwiftUI

struct LibraryView: View {

    @Environment(AuthEnvironment.self) private var auth
    @State private var vm = LibraryViewModel()
    @State private var searchText = ""
    /// nil → "Tümü" (filtre yok). places_service._categorize'ın sabit
    /// taksonomisinden geliyor, bu yüzden serbest metin değil seçim listesi.
    @State private var selectedCategory: String?

    // MARK: - Trip Builder seçim modu

    @State private var isSelecting  = false
    @State private var selectedIDs: Set<Int> = []
    @State private var showTitlePrompt = false
    @State private var tripTitle = ""
    /// Oluşturulan gezi — `.navigationDestination(item:)` bunu tetikleyip
    /// Trip Detail'e geçer, sonra otomatik nil'e döner.
    @State private var createdTrip: TripDetail?

    // Sunucu city/q/category filtresini destekliyor, ama ilk sürümde tüm
    // kütüphane (≤50 mekan) zaten tek seferde çekiliyor — arama-her-tuşta-ağ
    // isteği yerine yerinde filtrelemek daha basit ve anında yanıt veriyor.
    private var filteredPlaces: [LibraryPlace] {
        var places = vm.places
        if let selectedCategory {
            places = places.filter { $0.category == selectedCategory }
        }
        guard !searchText.isEmpty else { return places }
        let q = searchText.lowercased()
        return places.filter {
            $0.name.lowercased().contains(q) || ($0.city?.lowercased().contains(q) ?? false)
        }
    }

    /// Kütüphanede fiilen görülen kategoriler, ilk görülme sırasına göre —
    /// var olmayan kategoriler için boş bir filtre satırı göstermeyiz.
    private var availableCategories: [String] {
        var seen = Set<String>()
        var ordered: [String] = []
        for place in vm.places {
            guard let category = place.category, !category.isEmpty, !seen.contains(category) else { continue }
            seen.insert(category)
            ordered.append(category)
        }
        return ordered
    }

    var body: some View {
        ZStack(alignment: .bottom) {
            AppColors.background.ignoresSafeArea()

            VStack(spacing: 0) {
                if !availableCategories.isEmpty {
                    categoryChips
                        .padding(.top, 8)
                }

                if vm.isLoading && vm.places.isEmpty {
                    Spacer()
                    ProgressView().tint(AppColors.accentText)
                    Spacer()
                } else if let error = vm.error, vm.places.isEmpty {
                    errorState(error)
                } else if vm.places.isEmpty {
                    emptyState
                } else if filteredPlaces.isEmpty {
                    noResultsState
                } else {
                    list
                }
            }
            .frame(maxHeight: .infinity)

            if isSelecting && !selectedIDs.isEmpty {
                selectionBar
            }
        }
        .navigationTitle("Kütüphane")
        .navigationBarTitleDisplayMode(.inline)
        .searchable(text: $searchText, prompt: "Mekan veya şehir ara")
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                HStack(spacing: 16) {
                    if !vm.places.isEmpty {
                        Button(isSelecting ? "Vazgeç" : "Gezi Oluştur") {
                            withAnimation {
                                isSelecting.toggle()
                                if !isSelecting { selectedIDs.removeAll() }
                            }
                        }
                        .font(.system(size: 14, weight: .semibold))
                    }
                    NavigationLink(destination: TripsListView()) {
                        Image(systemName: "map")
                            .foregroundStyle(AppColors.accentText)
                    }
                }
            }
        }
        .task { await vm.load(auth: auth) }
        .refreshable { await vm.load(auth: auth) }
        .navigationDestination(item: $createdTrip) { trip in
            TripDetailView(tripID: trip.id, preloaded: trip)
        }
        .alert("Gezi Adı", isPresented: $showTitlePrompt) {
            TextField("Örn. Fethiye Turu", text: $tripTitle)
            Button("Oluştur") { Task { await createTrip() } }
            Button("Vazgeç", role: .cancel) { }
        } message: {
            Text("\(selectedIDs.count) mekandan bir rota oluşturulacak.")
        }
        .alert(
            "Gezi oluşturulamadı",
            isPresented: Binding(
                get: { vm.tripCreationError != nil },
                set: { if !$0 { vm.tripCreationError = nil } }
            )
        ) {
            Button("Tamam", role: .cancel) { vm.tripCreationError = nil }
        } message: {
            Text(vm.tripCreationError ?? "")
        }
    }

    // MARK: - Trip Builder

    private func createTrip() async {
        let title = tripTitle.trimmingCharacters(in: .whitespaces)
        guard let trip = await vm.createTrip(
            title: title.isEmpty ? "Yeni Gezi" : title,
            placeIDs: Array(selectedIDs),
            auth: auth
        ) else { return }

        isSelecting = false
        selectedIDs.removeAll()
        tripTitle = ""
        createdTrip = trip
    }

    private var categoryChips: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                categoryChip(label: "Tümü", isSelected: selectedCategory == nil) {
                    selectedCategory = nil
                }
                ForEach(availableCategories, id: \.self) { category in
                    categoryChip(label: category, isSelected: selectedCategory == category) {
                        selectedCategory = (selectedCategory == category) ? nil : category
                    }
                }
            }
            .padding(.horizontal, 16)
        }
    }

    private func categoryChip(label: String, isSelected: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(label)
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(isSelected ? Color.white : AppColors.textSecondary)
                .padding(.horizontal, 14)
                .padding(.vertical, 8)
                .background(isSelected ? AppColors.accent : AppColors.surface)
                .clipShape(Capsule())
                .overlay(
                    Capsule().stroke(isSelected ? Color.clear : AppColors.border, lineWidth: 1)
                )
        }
        .buttonStyle(PressableButtonStyle())
    }

    private var selectionBar: some View {
        HStack {
            Text("\(selectedIDs.count) mekan seçildi")
                .font(.system(size: 14, weight: .semibold))
                .foregroundStyle(AppColors.text)
            Spacer()
            if vm.isCreatingTrip {
                ProgressView().tint(AppColors.accentText)
            } else {
                Button("Rota Oluştur") { showTitlePrompt = true }
                    .font(.system(size: 14, weight: .bold))
                    .padding(.horizontal, 16)
                    .padding(.vertical, 10)
                    .background(AppColors.accent)
                    .foregroundStyle(Color.white)
                    .clipShape(Capsule())
            }
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 14)
        .background(.ultraThinMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 20))
        .overlay(RoundedRectangle(cornerRadius: 20).stroke(AppColors.border, lineWidth: 1))
        .padding(.horizontal, 16)
        .padding(.bottom, 12)
    }

    private var list: some View {
        ScrollView {
            LazyVStack(spacing: 10) {
                ForEach(filteredPlaces) { place in
                    if isSelecting {
                        Button {
                            withAnimation(.easeOut(duration: 0.15)) {
                                if selectedIDs.contains(place.id) {
                                    selectedIDs.remove(place.id)
                                } else {
                                    selectedIDs.insert(place.id)
                                }
                            }
                        } label: {
                            LibraryRowView(place: place, isSelected: selectedIDs.contains(place.id))
                        }
                        .buttonStyle(PressableButtonStyle())
                    } else {
                        LibraryRowView(place: place)
                    }
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 12)
            .padding(.bottom, isSelecting && !selectedIDs.isEmpty ? 60 : 0)
        }
    }

    private var emptyState: some View {
        VStack(spacing: 16) {
            Spacer()
            Image(systemName: "books.vertical")
                .font(.system(size: 52))
                .foregroundStyle(AppColors.textTertiary)
            Text("Kütüphanen henüz boş")
                .font(.system(size: 18, weight: .semibold))
                .foregroundStyle(AppColors.text)
            Text("Instagram'da paylaştığın her Reels'ten\nçıkarılan mekanlar burada birikir.")
                .font(.system(size: 14))
                .foregroundStyle(AppColors.textSecondary)
                .multilineTextAlignment(.center)
            Spacer()
        }
        .padding(.horizontal, 32)
    }

    private var noResultsState: some View {
        VStack(spacing: 12) {
            Spacer()
            Image(systemName: "magnifyingglass")
                .font(.system(size: 40))
                .foregroundStyle(AppColors.textTertiary)
            Text("Sonuç bulunamadı")
                .font(.system(size: 15))
                .foregroundStyle(AppColors.textSecondary)
            Spacer()
        }
    }

    private func errorState(_ error: APIError) -> some View {
        VStack(spacing: 16) {
            Spacer()
            Image(systemName: "wifi.exclamationmark")
                .font(.system(size: 48))
                .foregroundStyle(AppColors.destructive)
            Text(error.localizedDescription ?? "Bir hata oluştu.")
                .font(.system(size: 15))
                .foregroundStyle(AppColors.textSecondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 40)
            Button("Tekrar Dene") { Task { await vm.load(auth: auth) } }
                .foregroundStyle(AppColors.accentText)
            Spacer()
        }
    }
}
