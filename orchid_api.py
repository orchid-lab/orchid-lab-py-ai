from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import gc
from ultralytics import YOLO
from PIL import Image
from io import BytesIO
import uvicorn

class Config:
    STAGE_MODEL_PATH = './models/stage_model.pt'
    DISEASE_MODEL_PATH = './models/disease_model_ver3.pt'
    IMG_SIZE = 224

class OrchidClassifier:
    def __init__(self, config: Config):
        self.stage_model = YOLO(config.STAGE_MODEL_PATH)
        self.disease_model = YOLO(config.DISEASE_MODEL_PATH)

    def classify(self, image_bytes: bytes) -> dict:
       try: 
            img = Image.open(BytesIO(image_bytes)).convert('RGB')
            #take probabilities from the model

            #output
            stage_result = self.stage_model.predict(img, imgsz=Config.IMG_SIZE, verbose=False)
            stage_class = stage_result[0].probs.top1
            stage_label = self.stage_model.model.names[stage_class]

            disease_result = self.disease_model.predict(img, imgsz=Config.IMG_SIZE, verbose=False)
            disease_probs = disease_result[0].probs.data.cpu().numpy()
            disease_label = self.disease_model.model.names[disease_result[0].probs.top1]

            return {
                'stage': stage_label,
                'disease': {
                    'predict': disease_label,
                    'probability': {
                        self.disease_model.model.names[i]: round(float(disease_probs[i]), 6)
                        for i in range(len(disease_result[0].probs))
                    }
                }
            }
       finally: 
           del stage_result, disease_result
           gc.collect()

app = FastAPI()
classifier = OrchidClassifier(Config())

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    try:
        image_bytes = await file.read()
        result = classifier.classify(image_bytes)
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("orchid_api:app", host="0.0.0.0", port=8000)