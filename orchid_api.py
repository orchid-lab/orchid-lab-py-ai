from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import torch
from ultralytics import YOLO
from PIL import Image
from io import BytesIO
import uvicorn
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Config:
    STAGE_MODEL_PATH = './models/stage_model.pt'
    DISEASE_MODEL_PATH = './models/disease_model_ver3.pt'
    IMG_SIZE = 224
    DEVICE = 'cpu'  # Docker Linux environment - CPU only
    ENABLE_TIMING_LOGS = True  # Set to False in production for better performance

class OrchidClassifier:
    def __init__(self, config: Config):
        self.config = config
        self.stage_model = YOLO(config.STAGE_MODEL_PATH)
        self.disease_model = YOLO(config.DISEASE_MODEL_PATH)
        
        # Warm-up models để tránh cold start
        self._warmup()
    
    def _warmup(self):
        """Warm-up models với dummy image để tránh cold start delay"""
        try:
            dummy_img = Image.new('RGB', (self.config.IMG_SIZE, self.config.IMG_SIZE), color='white')
            self.stage_model.predict(dummy_img, imgsz=self.config.IMG_SIZE, verbose=False)
            self.disease_model.predict(dummy_img, imgsz=self.config.IMG_SIZE, verbose=False)
            print(f"✓ Models warmed up successfully on CPU")
        except Exception as e:
            print(f"Warning: Warmup failed - {e}")

    def classify(self, image_bytes: bytes) -> dict:
        timings = {} if self.config.ENABLE_TIMING_LOGS else None
        start_total = time.perf_counter() if timings is not None else None
        
        # Sử dụng inference_mode để giảm overhead
        with torch.inference_mode():
            # 1. Decode image
            t0 = time.perf_counter() if timings is not None else None
            img = Image.open(BytesIO(image_bytes)).convert('RGB')
            if timings is not None:
                timings['decode'] = (time.perf_counter() - t0) * 1000
            
            # 2. Stage prediction
            t1 = time.perf_counter() if timings is not None else None
            stage_result = self.stage_model.predict(
                img, 
                imgsz=self.config.IMG_SIZE, 
                verbose=False
            )
            stage_class = stage_result[0].probs.top1
            stage_label = self.stage_model.model.names[stage_class]
            if timings is not None:
                timings['stage_predict'] = (time.perf_counter() - t1) * 1000

            # 3. Disease prediction
            t2 = time.perf_counter() if timings is not None else None
            disease_result = self.disease_model.predict(
                img, 
                imgsz=self.config.IMG_SIZE, 
                verbose=False
            )
            disease_probs = disease_result[0].probs.data.cpu().numpy()
            disease_label = self.disease_model.model.names[disease_result[0].probs.top1]
            if timings is not None:
                timings['disease_predict'] = (time.perf_counter() - t2) * 1000
            
            # 4. Serialize probabilities
            t3 = time.perf_counter() if timings is not None else None
            all_probs = {
                self.disease_model.model.names[i]: round(float(disease_probs[i]), 4)
                for i in range(len(disease_probs))
            }
            if timings is not None:
                timings['serialize'] = (time.perf_counter() - t3) * 1000
                timings['total'] = (time.perf_counter() - start_total) * 1000
                logger.info(f"Inference timings (ms): {timings}")

            return {
                'stage': stage_label,
                'disease': {
                    'predict': disease_label,
                    'probability': all_probs
                }
            }
        # Không cần finally block với del và gc.collect() - để Python GC tự quản lý

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    """Initialize classifier khi app startup"""
    global classifier
    print("Initializing Orchid Classifier...")
    classifier = OrchidClassifier(Config())
    print(f"✓ Classifier ready - Device: {Config.DEVICE}")

classifier = None

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy" if classifier is not None else "initializing",
        "device": Config.DEVICE
    }

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    if classifier is None:
        raise HTTPException(status_code=503, detail="Service not ready")
    
    request_start = time.perf_counter()
    try:
        # Đọc file
        image_bytes = await file.read()
        
        # Classify
        result = classifier.classify(image_bytes)
        
        # Log total request time
        if Config.ENABLE_TIMING_LOGS:
            total_time = (time.perf_counter() - request_start) * 1000
            logger.info(f"Total request time: {total_time:.2f}ms")
        
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import os
    
    # Uvicorn configuration for production
    workers = int(os.getenv('WORKERS', '2'))  # Default 2 workers for CPU-bound tasks
    
    # Note: Với multiple workers, mỗi worker sẽ load riêng model vào memory
    # Nếu RAM hạn chế, giảm workers xuống 1
    
    uvicorn.run(
        "orchid_api:app", 
        host="0.0.0.0", 
        port=8000,
        workers=workers if workers > 1 else None,  # None = single worker mode
        log_level="info"
    )