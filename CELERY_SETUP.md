# Background Domain Scanning Setup

## Overview

SalesBreachPro provides **automatic background domain scanning** with the following features:
- **30-second delays** between domain scans (FlawTrack API rate limiting)
- **3 automatic retries** for failed scans with exponential backoff
- **Real-time progress updates** in the upload interface
- **FIFO processing** to ensure proper scan order
- **Multiple backend options** for different deployment scenarios

## Quick Start Options

### ⚡ **Simplest Option: Zero Configuration** (Recommended)
```bash
python start.py
```
**This is all you need!**
- ✅ No Redis installation required
- ✅ No Celery setup required
- ✅ Works out of the box
- ✅ Automatic background domain scanning with 30-second delays
- ✅ Real-time progress updates
- ✅ Same functionality as full Celery setup

### 🚀 Option 2: Enhanced Performance (Full Services)
```bash
python run_app.py
```
This **automatically manages enhanced setup**:
- Checks for Redis and starts it if needed
- Starts Celery worker in background
- Launches Flask application
- Provides distributed task processing
- Gracefully shuts down all services with Ctrl+C

### 🔧 Option 3: Manual Control (Advanced Users)
If you prefer full control or already have Redis running:
```bash
# Terminal 1: Start Redis (if not running)
redis-server

# Terminal 2: Start Celery Worker
python start_celery_worker.py

# Terminal 3: Start Flask App
python app.py
```

### 📋 Installation Requirements

**For Option 1 (Zero Config):**
```bash
pip install -r requirements.txt
```

**For Options 2-3 (Enhanced Performance):**
```bash
pip install -r requirements-enhanced.txt
```

## Installation Requirements

### Dependencies

**Required for all modes:**
```bash
pip install -r requirements.txt
```

**Optional for enhanced performance (Redis + Celery):**

**Windows:**
- Download Redis from: https://github.com/microsoftarchive/redis/releases
- Or use Windows Subsystem for Linux (WSL)

**macOS:**
```bash
brew install redis
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update && sudo apt install redis-server
```

## System Behavior

### Automatic Backend Selection
The system **intelligently chooses** the best available backend:

1. **First Choice: Celery + Redis** (Best performance, production-ready)
   - If Redis is available and Celery imports successfully
   - Provides distributed task processing and persistence

2. **Fallback: Simple Thread Scanner** (Zero-config, works everywhere)
   - If Redis/Celery unavailable or fail to start
   - Uses Python threading with same 30-second delays and retry logic
   - **No external dependencies required**

### Visual Indicators
The upload interface shows which backend is being used:
- "🔧 Started scanning X domains using **celery** backend"
- "🧵 Started scanning X domains using **simple** backend"

## How It Works

### Contact Upload Flow
1. User uploads CSV file with contacts
2. Contacts are saved to database immediately
3. Unique domains are extracted automatically
4. Background scanning task is queued in Celery
5. User sees real-time progress in the upload interface

### Domain Scanning Process
1. **Sequential Processing**: Domains are scanned one by one
2. **30-Second Delays**: Automatic delay between each domain scan
3. **Retry Logic**: Failed scans are retried up to 3 times
4. **Progress Updates**: Real-time status updates via API endpoints
5. **Database Updates**: Breach status updated as scans complete

### API Endpoints

- `GET /api/scan/progress/<task_id>` - Get scan progress for specific task
- `GET /api/scan/status` - Get overall scan statistics
- `GET /api/scan/domains` - Get scan results for all domains
- `POST /api/scan/start-batch` - Manually start domain scan batch
- `POST /api/scan/retry-failed` - Retry all failed scans
- `POST /api/scan/cancel/<task_id>` - Cancel running scan task

## Configuration

### Environment Variables
```bash
# Redis Configuration (default values)
REDIS_URL=redis://localhost:6379/0

# FlawTrack API Configuration
FLAWTRACK_SCANNING_ENABLED=True
FLAWTRACK_API_TOKEN=your_api_token_here
```

### Celery Configuration
The system is configured for:
- **Single worker concurrency** to respect API rate limits
- **Task routing** to dedicated `domain_scanning` queue
- **Acknowledgment on completion** to prevent task loss
- **Worker prefetch multiplier of 1** for strict FIFO processing

## Monitoring

### Upload Interface
- Real-time progress bar showing scan completion
- Current domain being scanned
- Estimated completion time
- Success/failure status updates

### Celery Worker Logs
The worker displays detailed logs including:
- Task start/completion messages
- Progress updates for each domain
- Error messages for failed scans
- Retry attempts and backoff delays

### Redis Monitoring
```bash
# Connect to Redis CLI
redis-cli

# Monitor commands being processed
MONITOR

# Check queue status
LLEN celery
LLEN domain_scanning
```

## Troubleshooting

### Common Issues

**1. "Connection refused" errors**
- Ensure Redis server is running: `redis-server`
- Check Redis is accessible: `redis-cli ping`

**2. Tasks not processing**
- Verify Celery worker is running
- Check worker logs for errors
- Confirm queue names match configuration

**3. Slow scan performance**
- This is intentional due to 30-second delays
- Monitor progress in upload interface
- Check FlawTrack API rate limits

**4. Failed scans**
- Review worker logs for specific errors
- Use retry functionality: POST to `/api/scan/retry-failed`
- Check FlawTrack API token and connectivity

### Debug Commands

```bash
# Check Celery worker status
celery -A celery_app inspect active

# View scheduled tasks
celery -A celery_app inspect scheduled

# Check worker stats
celery -A celery_app inspect stats

# Purge all tasks (caution!)
celery -A celery_app purge
```

## Production Deployment

For production environments:

1. **Use process manager** (systemd, supervisor) for Celery worker
2. **Configure Redis persistence** and backup
3. **Set up monitoring** (Flower, Prometheus)
4. **Scale workers** based on load requirements
5. **Implement log rotation** for worker logs

### Systemd Service Example
```ini
[Unit]
Description=SalesBreachPro Celery Worker
After=network.target redis.service

[Service]
Type=forking
User=salesbreach
Group=salesbreach
WorkingDirectory=/path/to/salesbreachpro
ExecStart=/path/to/venv/bin/python start_celery_worker.py
Restart=always

[Install]
WantedBy=multi-user.target
```

## Performance Notes

- **Scanning Speed**: ~30 seconds per domain + processing time
- **Batch Size**: No limit, but expect linear time scaling
- **Memory Usage**: Low, as tasks are processed sequentially
- **Reliability**: High, with automatic retries and persistence

The system prioritizes **reliability and API compliance** over speed, ensuring consistent domain scanning without overwhelming the FlawTrack API.