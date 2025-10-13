"""
Celery application configuration for SalesBreachPro background tasks
Handles FlawTrack domain scanning and other background operations
"""

import os
from celery import Celery
from dotenv import load_dotenv

# Load environment variables
basedir = os.path.abspath(os.path.dirname(__file__))
env_file = os.path.join(basedir, 'env')
if os.path.exists(env_file):
    load_dotenv(env_file)

# Configure Celery
def make_celery(app_name=__name__):
    """Create and configure Celery instance"""

    # Redis configuration (default to localhost)
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

    celery = Celery(
        app_name,
        broker=redis_url,
        backend=redis_url,
        include=['tasks.domain_scanning', 'tasks.email_processing']
    )

    # Celery configuration
    celery.conf.update(
        # Task routing
        task_routes={
            'tasks.domain_scanning.scan_domain_batch': {'queue': 'domain_scanning'},
            'tasks.domain_scanning.scan_single_domain': {'queue': 'domain_scanning'},
            'tasks.email_processing.*': {'queue': 'email_processing'},
        },

        # Task execution settings
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        timezone='UTC',
        enable_utc=True,

        # Retry settings
        task_acks_late=True,
        worker_prefetch_multiplier=1,

        # Task time limits (30 minutes max per task)
        task_time_limit=1800,
        task_soft_time_limit=1500,

        # Result backend settings
        result_expires=3600,  # Results expire after 1 hour

        # Worker settings
        worker_disable_rate_limits=True,
        worker_max_tasks_per_child=1000,
    )

    return celery

# Create Celery instance
celery_app = make_celery()

if __name__ == '__main__':
    celery_app.start()