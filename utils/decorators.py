"""
Authentication and other decorators for SalesBreachPro
"""
from functools import wraps
from flask import session, redirect, url_for


def login_required(f):
    """Decorator to require login for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function