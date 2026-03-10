from ultralytics import YOLO
from pathlib import Path
from typing import List,Dict
import logging

logger = logging.getLogger(__name__)

class ObjectDetectionService:
    """YOLOV8 ile object detection"""

    def __init__(self):
        "YOLOv8 nano model"

        logger.info("Loading YOLO model..")
        self.model = YOLO('yolov8n.pt')
        logger.info("YOLO model loaded successfully")

    def detect_objects_in_frames(self, frame_paths: List[str]) -> List[Dict]:
        """
        Frame'lerde object detection
        Returns: List of detections with class, confidence, bbox
        """
        all_detections = []
        
        logger.info(f"Running YOLO on {len(frame_paths)} frames...")
        
        for i, frame_path in enumerate(frame_paths):
            results = self.model(frame_path, verbose=False)
            
            # results[0] → ilk (ve tek) sonuç
            result = results[0]
            
            if result.boxes is not None:
                for box in result.boxes:
                    detection = {
                        "frame": Path(frame_path).name,
                        "frame_index": i,
                        "class_name": result.names[int(box.cls)],
                        "class_id": int(box.cls),
                        "confidence": float(box.conf),
                        "bbox": box.xyxy[0].tolist()  # [x1, y1, x2, y2]
                    }
                    
                    # Sadece yüksek confidence (>50%)
                    if detection["confidence"] > 0.5:
                        all_detections.append(detection)
        
        logger.info(f"Detected {len(all_detections)} objects")
        return all_detections

    def get_landmark_candidates(self,detections:List[Dict])-> List[Dict]:
        """
        Landmark olabilecek objeleri filtrele
        """

        landmark_classes =[
            "person",
            "car",
            "traffic light",
            "bench",
            "clock",
        ]

        landmarks =[
            d for d in detections
            if d["class_name"] in landmark_classes
        ]

        logger.info(f"Found {len(landmarks)} landmark candidates")
        return landmarks
    

    def get_detection_summary(self,detections:List[Dict])->Dict:

        """ Tespit edilen objelerin özeti"""

        #Classlara göre grupla
        class_counts ={}

        for d in detections:
            class_name = d["class_name"]
            class_counts[class_name] = class_counts.get(class_name,0)+1
        
        # En çok tespit edilenler
        top_classes = sorted(
            class_counts.items(),
            key =lambda x: x[1],
            reverse=True
        )[:5]

        return {
            "total_detections": len(detections),
            "unique_classes":len(class_counts),
            "top_5_classes":dict(top_classes),
            "all_classes": class_counts     
        }

        