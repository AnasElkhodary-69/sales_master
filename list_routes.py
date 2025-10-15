"""
List all registered routes in the Flask app
"""
from app import create_app

app = create_app()

print("\n" + "=" * 80)
print("REGISTERED ROUTES")
print("=" * 80)

routes = []
for rule in app.url_map.iter_rules():
    routes.append({
        'endpoint': rule.endpoint,
        'methods': ','.join(sorted(rule.methods - {'HEAD', 'OPTIONS'})),
        'url': str(rule)
    })

# Sort by URL
routes.sort(key=lambda x: x['url'])

# Print routes
for route in routes:
    if '/clients' in route['url']:
        print(f">>> {route['methods']:8} {route['url']:40} -> {route['endpoint']}")
    else:
        print(f"    {route['methods']:8} {route['url']:40} -> {route['endpoint']}")

print("=" * 80)
print(f"\nTotal routes: {len(routes)}")
print("\nLooking for /clients routes...")
client_routes = [r for r in routes if '/clients' in r['url']]
if client_routes:
    print(f"Found {len(client_routes)} client routes!")
    for r in client_routes:
        print(f"  - {r['url']}")
else:
    print("No /clients routes found!")
