# Orchid API Optimization Notes

## Các tối ưu đã implement (CPU-only for Docker Linux)

### 1. **Model Warmup**
- ✅ Models được warmup khi app startup
- ✅ Loại bỏ cold start delay (~100-500ms) cho request đầu tiên
- ✅ Dummy prediction để load models vào memory

### 2. **Inference Optimization**
- ✅ **torch.inference_mode()** - Giảm overhead ~10-20%
- ✅ Disable gradient tracking và autograd
- ✅ Faster inference path trong PyTorch

### 3. **Memory Management - BỎ GC FORCING**
- ✅ **BỎ gc.collect() mỗi request** - Tránh latency spike 10-50ms
- ✅ **BỎ del statements trong finally** - Unsafe và không có lợi
- ✅ Để Python GC tự quản lý tự nhiên
- ✅ GC sẽ chạy khi cần, không block request path

### 4. **Timing Logs - Performance Monitoring**
- ✅ Chi tiết từng phase: decode, stage_predict, disease_predict, serialize
- ✅ Total request time logging
- ✅ Có thể tắt trong production: `ENABLE_TIMING_LOGS = False`

### 5. **Horizontal Scaling - Multiple Workers**
- ✅ Uvicorn workers support (default: 2 workers)
- ✅ Configure via environment: `WORKERS=4 python orchid_api.py`
- ✅ Mỗi worker = 1 process riêng với model riêng
- ⚠️ Trade-off: Nhiều RAM hơn nhưng throughput cao hơn

### 6. **Service Architecture**
- ✅ Health check endpoint: `/health`
- ✅ Service readiness check (trả 503 nếu chưa ready)
- ✅ Proper error handling và logging

### 7. **Response Format**
- ✅ Trả về tất cả disease probabilities
- ✅ Precision: 4 chữ số thập phân
- ✅ Clear structure: stage + disease prediction + probabilities

## Lý do không dùng GPU optimization

**Docker Linux Environment:**
- Linux server thường không có GPU
- Docker không có CUDA/GPU support mặc định
- GPU optimization (FP16, CUDA) không phù hợp
- CPU-only là lựa chọn đúng cho production

## Cách tinh chỉnh thêm (CPU-only)

### Nếu vẫn chậm, tune các parameters sau:

```python
class Config:
    # Giảm image size (trade-off: accuracy giảm nhẹ)
    IMG_SIZE = 160  # Thay vì 224 → tăng tốc ~40%
    
    # CPU only for Docker
    DEVICE = 'cpu'
```

### Monitoring performance:
```bash
# Test response time
curl -X POST "http://localhost:8000/analyze" \
  -F "file=@test_image.jpg" \
  -w "\nTime: %{time_total}s\n"

# Check health
curl http://localhost:8000/health
```

## Bottleneck Analysis

### Current architecture:
```
.NET → [Network] → Python API → [Model Inference] → .NET → DB → Frontend
```

### Thời gian breakdown (CPU-only):
- Network latency (.NET → Python): 5-30ms
- Image decode: 5-15ms
- Stage model inference (CPU): 50-150ms
- Disease model inference (CPU): 50-150ms
- Response serialization: 10-20ms
- Network latency (Python → .NET): 5-30ms

**Total: 125-395ms** (CPU-only on Linux Docker)

### Nếu cần tối ưu thêm:

1. **Batch processing** - Nếu .NET gửi nhiều ảnh cùng lúc:
   ```python
   # Process multiple images in one request
   results = model.predict([img1, img2, img3])
   ```

2. **Model quantization** - Giảm model size:
   ```python
   # Export to ONNX với quantization
   model.export(format='onnx', int8=True)
   ```

3. **Caching** - Cache results cho ảnh giống nhau:
   ```python
   from functools import lru_cache
   import hashlib
   
   @lru_cache(maxsize=100)
   def classify_cached(image_hash):
       # Cache based on image hash
   ```

4. **Connection pooling** - .NET nên reuse HTTP connections để giảm network overhead

5. **gRPC instead of REST** - Nếu network là bottleneck lớn (unlikely)

6. **Model optimization** - ONNX Runtime với quantization:
   ```python
   # Export to ONNX và sử dụng ONNXRuntime
   # Có thể giảm 20-30% inference time
   ```

## Performance Expectations (CPU-only Docker Linux)

### Current Performance (Với các optimizations):
- Image decode: ~5-15ms
- Stage inference: ~50-150ms (CPU-dependent)
- Disease inference: ~50-150ms (CPU-dependent) 
- Serialization: ~5-10ms
- **Total: ~110-325ms** (không có GC spike)

### So sánh với code cũ:
- **Trước**: 150-400ms (có GC spike 10-50ms mỗi request)
- **Sau**: 110-325ms (stable, không có spike)
- **Improvement**: ~20-30% faster và ổn định hơn

### Timing Logs Example:
```
INFO: Inference timings (ms): {
  'decode': 8.2, 
  'stage_predict': 95.3, 
  'disease_predict': 98.7, 
  'serialize': 6.1, 
  'total': 208.3
}
INFO: Total request time: 211.45ms
```

### Workers Configuration:

| Workers | RAM Usage | Throughput | Use Case |
|---------|-----------|------------|----------|
| 1 | ~500MB-1GB | ~3-5 req/s | RAM limited |
| 2 | ~1-2GB | ~6-10 req/s | **Recommended** |
| 4 | ~2-4GB | ~12-20 req/s | High traffic |

**Công thức ước tính:**
- RAM per worker: ~500MB-1GB (model + runtime)
- Throughput per worker: ~3-5 req/s (CPU-bound)

### Bottleneck Priority:
1. **Model inference** (~70-80% of time) - Main bottleneck
2. **Network latency** (~10-15%) - .NET ↔ Python
3. **Image decode** (~5-10%) - Minimal
4. **Serialization** (~3-5%) - Negligible

### Optimization Tips for .NET side:
- ✅ HTTP connection pooling (HttpClientFactory)
- ✅ Compress images trước khi gửi (đã làm)
- ✅ Health check trước khi gửi requests
- ✅ Timeout handling (set reasonable timeout ~5s)
- ✅ Retry logic với exponential backoff
