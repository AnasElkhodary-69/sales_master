#!/usr/bin/env python3
"""
Celery Worker Startup Script for SalesBreachPro
Starts the Celery worker for background domain scanning tasks

Usage:
    python start_celery_worker.py

Requirements:
    - Redis server running on localhost:6379
    - All dependencies installed (pip install -r requirements.txt)
"""

import os
import sys
from celery_app import celery_app

if __name__ == '__main__':
    print("Starting SalesBreachPro Celery Worker...")
    print("===========================================")
    print("Worker Configuration:")
    print(f"  - Broker: {celery_app.conf.broker_url}")
    print(f"  - Queues: domain_scanning, celery (default)")
    print(f"  - Concurrency: 1 worker (to respect 30-second delays)")
    print("  - Log Level: INFO")
    print()
    print("Make sure Redis is running: redis-server")
    print("Press Ctrl+C to stop the worker")
    print("===========================================")

    # Start worker with specific configuration
    celery_app.worker_main([
        'worker',
        '--loglevel=info',
        '--concurrency=1',  # Single worker to ensure sequential processing
        '--queues=domain_scanning,celery',
        '--hostname=worker@salesbreachpro'
    ])