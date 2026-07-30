import os
import unittest.mock as mock
import pytest

def test_whisper_service_default_model():
    """Test that Whisper service defaults to 'tiny' when WHISPER_MODEL is not set."""
    with mock.patch.dict(os.environ, {}, clear=False):
        # We delete the environment variable if it exists in mock scope
        if "WHISPER_MODEL" in os.environ:
            del os.environ["WHISPER_MODEL"]
            
        from app.ml.speech_to_text import AudioProcessingService
        # Force re-instantiation to ensure it parses the mock environment
        service = AudioProcessingService()
        assert service.model_name == "tiny"

def test_whisper_service_configured_model():
    """Test that Whisper service respects WHISPER_MODEL environment variable."""
    with mock.patch.dict(os.environ, {"WHISPER_MODEL": "base"}):
        from app.ml.speech_to_text import AudioProcessingService
        service = AudioProcessingService()
        assert service.model_name == "base"

def test_transcribe_audio_raises_on_model_error():
    """
    Kök neden (2026-07-26): transcribe_audio hatayı yutup boş transkript
    döndürüyordu; video_processor._safe_run bunu "başarılı, konuşma yok" ile
    ayırt edemiyor ve degradation raporu yanlış şekilde ✅ OK gösteriyordu.
    Artık fırlatıyor — _safe_run fallback'e düşüp doğru şekilde işaretliyor.
    """
    from app.ml.speech_to_text import AudioProcessingService

    service = AudioProcessingService()
    service.model = mock.MagicMock()
    service.model.transcribe.side_effect = RuntimeError("model çöktü")

    with pytest.raises(RuntimeError):
        service.transcribe_audio("fake_audio.wav")


def test_landmark_service_disabled_by_default():
    """Test that LandmarkDetectionService remains disabled when USE_GOOGLE_VISION is false."""
    with mock.patch.dict(os.environ, {"USE_GOOGLE_VISION": "false"}):
        from app.ml.computer_vision import LandmarkDetectionService
        service = LandmarkDetectionService()
        assert service.enabled is False
        assert service.client is None
        assert service.detect_landmarks("fake_path.jpg") == []
        assert service.detect_landmarks_in_frames(["fake_path.jpg"]) == []

def test_landmark_service_enabled_but_invalid_credentials():
    """Test that LandmarkDetectionService disables itself gracefully when credentials fail to load."""
    with mock.patch.dict(os.environ, {
        "USE_GOOGLE_VISION": "true",
        "GOOGLE_APPLICATION_CREDENTIALS": "/nonexistent_credentials_path.json"
    }):
        from app.ml.computer_vision import LandmarkDetectionService
        service = LandmarkDetectionService()
        # Should catch DefaultCredentialsError and set enabled to False
        assert service.enabled is False
        assert service.client is None


def test_rag_service_disabled_without_ollama_url():
    """Test that RAGService stays disabled and degrades gracefully when OLLAMA_URL is unset."""
    with mock.patch.dict(os.environ, {"OLLAMA_URL": ""}):
        from app.ml.rag_service import RAGService
        service = RAGService()
        assert service.enabled is False
        assert service.generate_travel_tips([{"name": "Antalya"}]) == {"tips": [], "summary": ""}


def test_rag_service_reads_url_and_model_from_env():
    """Test that RAGService reads OLLAMA_URL / OLLAMA_MODEL from the environment instead of hardcoding them."""
    with mock.patch.dict(os.environ, {
        "OLLAMA_URL": "http://ollama.internal:11434",
        "OLLAMA_MODEL": "llama3",
    }):
        from app.ml.rag_service import RAGService
        service = RAGService()
        assert service.enabled is True
        assert service.ollama_url == "http://ollama.internal:11434"
        assert service.model == "llama3"


def test_rag_service_survives_ollama_connection_failure():
    """Test that an unreachable Ollama server never raises — the pipeline must not crash."""
    with mock.patch.dict(os.environ, {"OLLAMA_URL": "http://ollama.internal:11434"}):
        from app.ml.rag_service import RAGService
        service = RAGService()
        with mock.patch("requests.post", side_effect=ConnectionError("refused")):
            result = service.generate_travel_tips([{"name": "Antalya"}])
        assert result == {"tips": [], "summary": "", "locations_covered": ["Antalya"]}


def test_places_service_scoring():
    """Test that PlacesService prioritizes candidates matching city_hint or within bbox range over importance."""
    from app.ml.places_service import PlacesService
    
    service = PlacesService()
    
    # Mock search response from Nominatim
    mock_results = [
        {
            "display_name": "Kaleköy, Ilgın, Konya, İç Anadolu Bölgesi, Türkiye",
            "place_id": 209175520,
            "osm_id": 2412378157,
            "osm_type": "node",
            "lat": "38.3309981",
            "lon": "32.0458574",
            "type": "village",
            "class": "place",
            "importance": 0.30093685,
            "address": {
                "village": "Kaleköy",
                "town": "Ilgın",
                "province": "Konya",
                "country": "Türkiye"
            }
        },
        {
            "display_name": "Kale, Kaleüçağız, Demre, Antalya, Akdeniz Bölgesi, 07573, Türkiye",
            "place_id": 55555,
            "osm_id": 99999,
            "osm_type": "node",
            "lat": "36.2283888",
            "lon": "29.8500234",
            "type": "village",
            "class": "place",
            "importance": 0.0800462,
            "address": {
                "village": "Kale",
                "town": "Demre",
                "province": "Antalya",
                "country": "Türkiye"
            }
        }
    ]
    
    with mock.patch("requests.get") as mock_get:
        mock_resp = mock.Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_results
        mock_get.return_value = mock_resp
        
        # When city_hint is Antalya, it should pick the Antalya result despite lower importance
        result_with_hint = service.search_place(
            location_name="Kaleköy",
            city_bbox=(34.88, 28.70, 38.88, 32.70),
            city_hint="Antalya"
        )
        assert result_with_hint is not None
        assert "Antalya" in result_with_hint["name"]
        
        # When city_hint is not provided, it should fall back to importance and pick Konya
        result_without_hint = service.search_place(
            location_name="Kaleköy",
            city_bbox=None,
            city_hint=None
        )
        assert result_without_hint is not None
        assert "Konya" in result_without_hint["name"]
