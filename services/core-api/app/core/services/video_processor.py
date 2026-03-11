from pathlib import Path
import uuid
import ffmpeg
from typing import List,Dict
import logging
import time 
from app.ml.ocr_service import OCRService
from app.ml.computer_vision import ObjectDetectionService
from app.ml.computer_vision import LandmarkDetectionService

logger = logging.getLogger(__name__)

class VideoProcessingService:
    """Video processing: metadata,frames,thumbnails"""

    def __init__(self):
        self.frames_dir = Path("/app/uploads/frames")
        self.frames_dir.mkdir(parents=True,exist_ok=True)
        # AI: Object detection service
        self.detector = ObjectDetectionService()
        self.vision_detector = LandmarkDetectionService()
        self.ocr = OCRService()
        
    
    def process_video(self,video_path:str,video_id:int) -> Dict:
        """
        Videoyu İşle
        1. Metadata çıkar
        2. Frame'leri extract et
        3. Thumbnail oluştur
        4. Google Vision: Landmark Detection
        5. Text Exraction (OCR)
        """
        start_time = time.time()
        try:
            logger.info(f"Processing video {video_id}")

            # 1.Video Metadata
            metadata = self._get_metadata(video_path)
            logger.info(f"Metadata: {metadata}")

            # 2. Frame Extraction
            frame_dir = self.frames_dir / str(video_id)
            frames = self._extract_frames(video_path,frame_dir)
            logger.info(f"Extracted {len(frames)} frames")

            # 3. Thumbnail

            thumbnail = self._create_thumbnail(frames[0] if frames else None)
            logger.info(f"Thumbnail created: {thumbnail}")

            # 4. AI: Object detection
            detections = self.detector.detect_objects_in_frames(frames)
            detections = self.detector.remove_duplicate_detections(detections)
            landmarks = self.detector.get_landmark_candidates(detections)
            summary = self.detector.get_detection_summary(detections)
            vision_landmarks = self.vision_detector.detect_landmarks_in_frames(frames[:5])
            extracted_texts = self.ocr.extract_text_from_frames(frames[:10]
                                                                )

            total_time = time.time() -start_time
            logger.info(f"Performance: ")
            logger.info(f"Total Time: {total_time:.2f}s")
            logger.info(f" Frames/sec: {len(frames)/total_time:.2f}")
            logger.info(f" Time per frame: {total_time/len(frames):.2f}s")


            return{
                "duration": metadata["duration"],
                "resolution": f"{metadata['width']}x{metadata['height']}",
                "fps": metadata["fps"],
                "frame_count":len(frames),
                "frames_dir": str(frame_dir),
                "thumbnail": thumbnail,
                "detections_count": len(detections),
                "landmarks_count":len(landmarks),
                "processing_time": round(total_time,2),
                "fps_processed": round(len(frames)/total_time, 2),
                "vision_landmarks": vision_landmarks,
                "extracted_texts": extracted_texts,
                "top_objects": summary["top_5_classes"]
                

            }
        
        except Exception as e:
            logger.error(f"Video processing failed: {e}")
            raise
    
    def _get_metadata(self,video_path:str) -> Dict:
        """FFmpeg ile metadata çıkar"""
        try:
            probe = ffmpeg.probe(video_path)
            video_stream = next(
                s for s in probe['streams'] 
                if s['codec_type'] == 'video'
            )
            
            # FPS hesaplama (fraction olabilir)
            fps_str = video_stream.get('r_frame_rate', '30/1')
            fps_parts = fps_str.split('/')
            fps = float(fps_parts[0]) / float(fps_parts[1])
            
            return {
                "duration": float(probe['format']['duration']),
                "width": int(video_stream['width']),
                "height": int(video_stream['height']),
                "fps": round(fps, 2)
            }
        except Exception as e:
            logger.error(f"Metadata extraction failed: {e}")
            raise
    
    # Optimize edildi 1 fps 1 saniye idi şimdi her 2 saniyede 1 frame
    def _extract_frames(self, video_path: str, output_dir: Path, fps: int = 0.5) -> List[str]:
        """
        Video'dan frame'ler çıkar
        fps=1 → saniyede 1 frame
        """
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # FFmpeg ile frame extraction
            (
                ffmpeg
                .input(video_path)
                .filter('fps', fps=fps)
                .output(
                    str(output_dir / 'frame_%04d.jpg'),
                    quality=2  # JPEG quality
                )
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            
            # Extract edilen frame'lerin listesi
            frames = sorted(output_dir.glob('*.jpg'))
            return [str(f) for f in frames if f.name.startswith('frame_')]
        
        except ffmpeg.Error as e:
            logger.error(f"FFmpeg error: {e.stderr.decode()}")
            raise
    
    def _create_thumbnail(self, first_frame: str) -> str:
        """İlk frame'den thumbnail oluştur (320px width)"""
        if not first_frame:
            return None
        
        try:
            thumb_path = Path(first_frame).parent / "thumbnail.jpg"
            
            (
                ffmpeg
                .input(first_frame)
                .filter('scale', 320, -1)  # Width 320, height auto
                .output(str(thumb_path))
                .overwrite_output()
                .run(quiet=True)
            )
            
            return str(thumb_path)
        
        except Exception as e:
            logger.error(f"Thumbnail creation failed: {e}")
            return None
    
