"""
Authentication routes for SalesBreachPro
Handles login, logout, and session management
"""
from flask import Blueprint, render_template, request, session, flash, redirect, url_for, current_app

# Create authentication blueprint
auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if (username == current_app.config['ADMIN_USERNAME'] and 
            password == current_app.config['ADMIN_PASSWORD']):
            session['logged_in'] = True
            session['username'] = username
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard.index'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html')


@auth_bp.route('/logout')
def logout():
    """Handle user logout"""
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/')
def root():
    """Root route redirects based on login status"""
    if session.get('logged_in'):
        return redirect(url_for('dashboard.index'))
    return redirect(url_for('auth.login'))