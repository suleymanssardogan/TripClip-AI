import whisper
import ffmpeg
from pathlib import Path
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class AudioProcessingService:
    """Whisper ile audio transcription"""
    
    def __init__(self):
        self.model =None
        logger.info("SpeechToTextService initialized(lazy loading)")
       
    def _load_model(self):
        """Load Whisper model when needed"""
        if self.model is None:
            logger.info("Loading Whisper model...")
            self.model = whisper.load_model("base")
            logger.info("✅ Whisper model loaded!")
    
    def extract_audio(self, video_path: str, output_path: str) -> bool:
        """Video'dan audio çıkar (FFmpeg)"""
        
        try:
            (
                ffmpeg
                .input(video_path)
                .output(output_path, acodec='pcm_s16le', ac=1, ar='16k')
                .overwrite_output()
                .run(quiet=True)
            )
            logger.info(f"✅ Audio extracted: {output_path}")
            return True
        
        except Exception as e:
            logger.error(f"Audio extraction failed: {e}")
            return False
    
    def transcribe_audio(self, audio_path: str, language: str = "tr") -> Dict:
        """Audio'yu text'e çevir"""
        self._load_model()
        try:
            logger.info(f"Transcribing audio (language: {language})...")
            
            result = self.model.transcribe(
                audio_path,
                language=language,
                fp16=False  # CPU için
            )
            
            transcript = result["text"].strip()
            segments = result.get("segments", [])
            
            logger.info(f"✅ Transcription complete: {len(transcript)} chars")
            
            return {
                "transcript": transcript,
                "language": result.get("language", language),
                "segments": [
                    {
                        "start": seg["start"],
                        "end": seg["end"],
                        "text": seg["text"].strip()
                    }
                    for seg in segments
                ]
            }
        
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return {
                "transcript": "",
                "language": language,
                "segments": []
            }
    
    def process_video_audio(self, video_path: str, video_id: int) -> Optional[Dict]:
        """Video'dan audio çıkar ve transcribe et"""
        
        audio_dir = Path("/app/uploads/audio")
        audio_dir.mkdir(parents=True, exist_ok=True)
        
        audio_path = audio_dir / f"{video_id}.wav"
        
        # 1. Extract audio
        if not self.extract_audio(video_path, str(audio_path)):
            return None
        
        # 2. Transcribe
        result = self.transcribe_audio(str(audio_path), language="tr")
        
        # 3. Cleanup
        audio_path.unlink()
        
        return result