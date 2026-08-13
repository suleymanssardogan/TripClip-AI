"""
`should_retrieve_place_knowledge` birim testleri — saf fonksiyon, I/O YOK
(bkz. app/domain/assistant/retrieval_heuristic.py).
"""
import pytest

from app.domain.assistant.retrieval_heuristic import should_retrieve_place_knowledge


# ─── Milestone'un kendi örnekleri (docs/M30 Section 5) — BİREBİR ────────────

@pytest.mark.parametrize("message", [
    "Zeugma Müzesi hakkında ne biliyorsun?",
    "Gaziantep'te bu geziye yakın başka tarihi yerler neler?",
])
def test_retrieval_appropriate_examples_trigger_retrieval(message):
    assert should_retrieve_place_knowledge(message) is True


@pytest.mark.parametrize("message", [
    "Bugün kaç durağımız var?",
    "İlk durağımız saat kaçta?",
])
def test_trip_only_examples_skip_retrieval(message):
    assert should_retrieve_place_knowledge(message) is False


# ─── Genel davranış ──────────────────────────────────────────────────────────

def test_empty_message_skips_retrieval():
    assert should_retrieve_place_knowledge("") is False


def test_pure_itinerary_questions_skip_retrieval():
    for message in ["Yarın kaç durağımız var?", "Son durağımız nere?", "Sıradaki durak hangisi?"]:
        assert should_retrieve_place_knowledge(message) is False


def test_case_and_turkish_diacritics_are_normalized():
    # "HAKKINDA" (büyük harf) ve "hakkında" (Türkçe karakter) İKİSİ de
    # normalize_place_name'in ASCII-katlama + küçük harf dönüşümünden
    # sonra eşleşmeli.
    assert should_retrieve_place_knowledge("Zeugma HAKKINDA bilgi ver") is True
    assert should_retrieve_place_knowledge("bu müzenin TARİHÇESİ nedir") is True


def test_english_keywords_also_trigger_retrieval():
    assert should_retrieve_place_knowledge("Tell me about Zeugma Museum") is True
    assert should_retrieve_place_knowledge("What's the history of this place?") is True


def test_english_trip_only_question_skips_retrieval():
    assert should_retrieve_place_knowledge("How many stops do we have today?") is False


# ─── M31 — a place's own opening/closing hours vs. the trip's own schedule ──
# Gerçek doğrulama sırasında bulunan bir boşluk: "kaçta" hem "İlk durağımız
# saat KAÇTA?" (itinerary, skip — M30'un kendi kanonik örneği) hem de
# "Zeugma Müzesi kaçta AÇILIYOR?" (mekan bilgisi, retrieve GEREKİR) içinde
# geçebilir — "kaçta" tek başına ikisini AYIRT EDEMEZ, bu yüzden "açılış"/
# "kapanış" gövdeleri ayrıca eklendi.

def test_place_opening_hours_question_triggers_retrieval():
    assert should_retrieve_place_knowledge("Zeugma Müzesi kaçta açılıyor?") is True
    assert should_retrieve_place_knowledge("Bu müze kaçta kapanıyor?") is True
    assert should_retrieve_place_knowledge("Kale şu an açık mı?") is True


def test_trip_own_schedule_question_still_skips_retrieval_despite_kacta():
    # M30'un kendi kanonik örneği hâlâ False kalmalı — "açılış"/"kapanış"
    # eklenmesi bunu BOZMAMALI.
    assert should_retrieve_place_knowledge("İlk durağımız saat kaçta?") is False
    assert should_retrieve_place_knowledge("Son durağımıza kaçta varıyoruz?") is False
