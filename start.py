#!/usr/bin/env python3
"""
Simple SalesBreachPro Startup Script
Just run: python start.py

This is the simplest way to run SalesBreachPro with automatic background scanning.
No Redis or Celery setup required - the system will automatically choose the best available backend.
"""

if __name__ == '__main__':
    print("Starting SalesBreachPro...")
    print("=================================")
    print("Background domain scanning will be automatically configured")
    print("Web interface will be available at: http://localhost:5000")
    print("Press Ctrl+C to stop")
    print("=================================")

    try:
        from app import create_app
        app = create_app()

        app.run(
            host='0.0.0.0',
            port=5000,
            debug=False
        )
    except KeyboardInterrupt:
        print("\nSalesBreachPro stopped")
    except Exception as e:
        print(f"Error starting SalesBreachPro: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure you've installed dependencies: pip install -r requirements.txt")
        print("2. Check that the database file exists and is readable")
        print("3. Verify your environment variables in the 'env' file")