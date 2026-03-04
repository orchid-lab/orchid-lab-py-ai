# Orchid API - Run Configuration

## Quick Start

### Development (Single worker, with timing logs):
```bash
python orchid_api.py
```

### Production (Multiple workers):
```bash
# 2 workers (recommended)
WORKERS=2 python orchid_api.py

# 4 workers (high traffic)
WORKERS=4 python orchid_api.py

# Single worker (RAM limited)
WORKERS=1 python orchid_api.py
```

### Docker Compose:
```yaml
services:
  orchid-api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - WORKERS=2  # Configure workers
    volumes:
      - ./models:/app/models
```

## Configuration Options

### Environment Variables:
- `WORKERS`: Number of workers (default: 2)
  - RAM limited: Use 1
  - Normal: Use 2
  - High traffic: Use 4

### Code Configuration in `orchid_api.py`:

```python
class Config:
    IMG_SIZE = 224  # Giảm xuống 160 để tăng tốc ~40%
    DEVICE = 'cpu'  # Always CPU for Docker Linux
    ENABLE_TIMING_LOGS = True  # Set False in production
```

## Performance Tuning

### 1. Tắt timing logs trong production:
```python
ENABLE_TIMING_LOGS = False  # Tiết kiệm ~2-5ms per request
```

### 2. Giảm IMG_SIZE nếu cần tốc độ:
```python
IMG_SIZE = 160  # Trade-off: -10% accuracy, +40% speed
```

### 3. Workers configuration:
- **1 worker**: 3-5 req/s, ~500MB-1GB RAM
- **2 workers**: 6-10 req/s, ~1-2GB RAM (recommended)
- **4 workers**: 12-20 req/s, ~2-4GB RAM

### 4. Monitor với timing logs:
```bash
# Check logs
docker logs -f orchid-api

# Example output:
INFO: Inference timings (ms): {'decode': 8.2, 'stage_predict': 95.3, ...}
INFO: Total request time: 211.45ms
```

## Testing

### Health Check:
```bash
curl http://localhost:8000/health
# Response: {"status": "healthy", "device": "cpu"}
```

### Analyze Image:
```bash
curl -X POST http://localhost:8000/analyze \
  -F "file=@test_orchid.jpg" \
  -w "\nTime: %{time_total}s\n"
```

### Load Testing:
```bash
# Using Apache Bench
ab -n 100 -c 10 -p image.jpg -T 'multipart/form-data' \
  http://localhost:8000/analyze

# Expected: ~3-5 req/s per worker
```

## Memory Management

### Không cần quan tâm GC nữa:
- ✅ Python tự quản lý garbage collection
- ✅ GC chạy tự nhiên khi cần
- ✅ Không block request path
- ✅ Không có latency spike

### Monitor memory:
```bash
# Docker stats
docker stats orchid-api

# System monitor
htop  # Check memory per worker
```

## Troubleshooting

### Issue: High latency (>500ms)
**Solutions:**
1. Check CPU usage: `htop`
2. Reduce IMG_SIZE: 224 → 160
3. Increase workers (nếu có RAM)
4. Check timing logs để tìm bottleneck

### Issue: Out of Memory
**Solutions:**
1. Giảm workers: 4 → 2 → 1
2. Check memory usage per worker
3. Restart service định kỳ nếu cần

### Issue: Low throughput
**Solutions:**
1. Tăng workers (nếu có RAM)
2. Optimize CPU allocation
3. Check network latency .NET ↔ Python

## Expected Performance

### Development (1 worker, timing logs ON):
- Latency: 150-350ms
- Throughput: 3-5 req/s

### Production (2 workers, timing logs OFF):
- Latency: 110-325ms (stable, no spikes)
- Throughput: 6-10 req/s

### High Traffic (4 workers):
- Latency: 110-325ms
- Throughput: 12-20 req/s
