#!/usr/bin/env python3
"""
Integrated SalesBreachPro Application Launcher
Automatically starts Redis, Celery Worker, and Flask App together

Usage:
    python run_app.py

This script will:
1. Check if Redis is available, start embedded Redis if needed
2. Start Celery worker in background
3. Start Flask application
4. Gracefully shutdown all processes when stopped
"""

import os
import sys
import time
import signal
import subprocess
import threading
import atexit
from pathlib import Path

# Global process tracking
processes = []
redis_process = None
celery_process = None

def cleanup_processes():
    """Clean up all spawned processes"""
    global processes, redis_process, celery_process

    print("\n🛑 Shutting down SalesBreachPro...")

    # Stop Celery worker
    if celery_process and celery_process.poll() is None:
        print("  ⏹️  Stopping Celery worker...")
        celery_process.terminate()
        try:
            celery_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            celery_process.kill()

    # Stop Redis if we started it
    if redis_process and redis_process.poll() is None:
        print("  ⏹️  Stopping Redis server...")
        redis_process.terminate()
        try:
            redis_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            redis_process.kill()

    # Stop any other processes
    for process in processes:
        if process.poll() is None:
            process.terminate()

    print("  ✅ Cleanup complete")

def signal_handler(signum, frame):
    """Handle interrupt signals"""
    cleanup_processes()
    sys.exit(0)

def check_redis_available():
    """Check if Redis is already running"""
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0)
        r.ping()
        return True
    except:
        return False

def start_embedded_redis():
    """Start embedded Redis server"""
    global redis_process

    try:
        # Try to find redis-server in common locations
        redis_paths = [
            'redis-server',  # In PATH
            '/usr/local/bin/redis-server',  # macOS Homebrew
            '/usr/bin/redis-server',  # Linux
            'C:\\Program Files\\Redis\\redis-server.exe',  # Windows
        ]

        redis_cmd = None
        for path in redis_paths:
            try:
                # Test if command exists
                result = subprocess.run([path, '--version'],
                                      capture_output=True, timeout=5)
                if result.returncode == 0:
                    redis_cmd = path
                    break
            except:
                continue

        if not redis_cmd:
            print("  ❌ Redis not found. Please install Redis:")
            print("     Windows: Download from https://github.com/microsoftarchive/redis/releases")
            print("     macOS: brew install redis")
            print("     Linux: sudo apt install redis-server")
            return False

        print("  🚀 Starting Redis server...")
        redis_process = subprocess.Popen([
            redis_cmd,
            '--port', '6379',
            '--bind', '127.0.0.1',
            '--loglevel', 'warning'
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Wait for Redis to start
        for i in range(10):
            if check_redis_available():
                print("  ✅ Redis server started")
                return True
            time.sleep(1)

        print("  ❌ Redis failed to start within 10 seconds")
        return False

    except Exception as e:
        print(f"  ❌ Error starting Redis: {e}")
        return False

def start_celery_worker():
    """Start Celery worker in background"""
    global celery_process

    try:
        print("  🚀 Starting Celery worker...")

        # Import here to ensure all modules are available
        celery_process = subprocess.Popen([
            sys.executable, '-c',
            '''
import sys
import os
sys.path.insert(0, os.getcwd())
from celery_app import celery_app

celery_app.worker_main([
    "worker",
    "--loglevel=warning",  # Reduce log noise
    "--concurrency=1",
    "--queues=domain_scanning,celery",
    "--hostname=worker@salesbreachpro"
])
'''
        ], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

        # Give Celery a moment to start
        time.sleep(3)

        if celery_process.poll() is None:
            print("  ✅ Celery worker started")
            return True
        else:
            stderr = celery_process.stderr.read().decode()
            print(f"  ❌ Celery worker failed to start: {stderr}")
            return False

    except Exception as e:
        print(f"  ❌ Error starting Celery: {e}")
        return False

def start_flask_app():
    """Start Flask application"""
    try:
        print("  🚀 Starting Flask application...")

        # Import and run Flask app
        from app import create_app

        app = create_app()

        print("\n" + "="*50)
        print("🎉 SalesBreachPro is now running!")
        print("="*50)
        print("📱 Web Interface: http://localhost:5000")
        print("🔧 Celery Worker: Running in background")
        print("💾 Redis Server: Running on localhost:6379")
        print("="*50)
        print("Press Ctrl+C to stop all services")
        print("="*50)

        # Run Flask app
        app.run(
            host='0.0.0.0',
            port=5000,
            debug=False,  # Disable debug to prevent auto-restart conflicts
            use_reloader=False  # Disable reloader to prevent duplicate processes
        )

    except Exception as e:
        print(f"❌ Error starting Flask app: {e}")
        return False

def main():
    """Main application launcher"""

    # Register cleanup handlers
    atexit.register(cleanup_processes)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print("🚀 Starting SalesBreachPro with integrated services...")
    print("="*60)

    # 1. Check/Start Redis
    print("1️⃣ Setting up Redis...")
    if check_redis_available():
        print("  ✅ Redis is already running")
    else:
        if not start_embedded_redis():
            print("❌ Failed to start Redis. Exiting.")
            sys.exit(1)

    # 2. Start Celery Worker
    print("\n2️⃣ Setting up Celery worker...")
    if not start_celery_worker():
        print("❌ Failed to start Celery worker. Exiting.")
        cleanup_processes()
        sys.exit(1)

    # 3. Start Flask App
    print("\n3️⃣ Starting Flask application...")
    try:
        start_flask_app()
    except KeyboardInterrupt:
        pass
    finally:
        cleanup_processes()

if __name__ == '__main__':
    main()