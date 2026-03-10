from ultralytics import YOLO
from pathlib import Path
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

class ObjectDetectionService:
    """YOLOv8 ile object detection"""

    def __init__(self):
        """YOLOv8 nano model"""
        logger.info("Loading YOLO model...")
        self.model = YOLO('yolov8n.pt')
        logger.info("✅ YOLO model loaded successfully!")

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
                    
                    # Sadece yüksek confidence (>40%)
                    if detection["confidence"] > 0.4:
                        all_detections.append(detection)
        
        logger.info(f"✅ Detected {len(all_detections)} objects")
        return all_detections

    def get_landmark_candidates(self, detections: List[Dict]) -> List[Dict]:
        """Landmark olabilecek objeleri filtrele"""
        
        # Tüm araç tipleri
        vehicle_classes = ["car", "truck", "bus", "motorcycle"]
        
        # İnsan yoğunluğu (turist alanı işareti)
        crowd_classes = ["person"]
        
        # Urban landmark işaretleri
        urban_classes = ["traffic light", "stop sign", "parking meter", 
                         "bench", "clock", "fire hydrant"]
        
        landmark_classes = vehicle_classes + crowd_classes + urban_classes
        
        # ← BURASI EKSİKTİ!
        landmarks = [
            d for d in detections 
            if d["class_name"] in landmark_classes
        ]
        
        logger.info(f"Found {len(landmarks)} landmark candidates")
        return landmarks

    def get_detection_summary(self, detections: List[Dict]) -> Dict:
        """Tespit edilen objelerin özeti"""
        
        # Class'lara göre grupla
        class_counts = {}
        for d in detections:
            class_name = d["class_name"]
            class_counts[class_name] = class_counts.get(class_name, 0) + 1
        
        # En çok tespit edilenler
        top_classes = sorted(
            class_counts.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:5]
        
        return {
            "total_detections": len(detections),
            "unique_classes": len(class_counts),
            "top_5_classes": dict(top_classes),
            "all_classes": class_counts
        }
    
    def remove_duplicate_detections(self,detections: List[Dict]) -> List[Dict]:
        """
        Ardışık framlerde aynı objeyi tekmiş olarak algılatmak
        """

        if not detections:
            return []
        
        # Class'a göre grupla
        grouped = {}
        for d in detections:
            cls = d["class_name"]
            if cls not in grouped:
                grouped[cls] = []
            grouped[cls].append(d)
        unique_detections =[]

        for cls,dets in grouped.items():
            #Confidence'a göre sıralama
            dets_sorted = sorted(dets,key=lambda x:x["confidence"],reverse=True)

            # En yüksek confidence'lı N tanesini al
            # Her 5 detection'dan 1 tanesini al
            top_n = min(len(dets_sorted),max(3,len(dets_sorted)//5))
            unique_detections.extend(dets_sorted[:top_n])

        logger.info(f"Reduced {len(detections)} -> {len(unique_detections)} detections")
        return unique_detections