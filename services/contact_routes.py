from flask import redirect, request
import logging

logger = logging.getLogger(__name__)

def init_contact_routes(app):
    """Initialize legacy contact route redirects for backward compatibility"""
    
    @app.route('/upload/csv', methods=['POST'])
    def upload_csv_redirect():
        """Redirect old upload requests to new endpoint"""
        print("DEBUG: Legacy upload route called - redirecting to /contacts/upload/csv")
        return redirect('/contacts/upload/csv', code=307)  # 307 preserves POST method
    
    @app.route('/api/contacts')
    def api_contacts_redirect():
        """Redirect legacy API contacts route"""
        print("DEBUG: Legacy API contacts route called - redirecting to contacts blueprint")
        # Preserve query parameters
        query_string = request.query_string.decode('utf-8')
        redirect_url = '/contacts/api/list'
        if query_string:
            redirect_url += f'?{query_string}'
        return redirect(redirect_url, code=301)
    
    print("Legacy contact route redirects initialized")