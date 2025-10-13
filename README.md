# SalesBreachPro

A comprehensive Flask-based sales and security outreach platform that leverages cybersecurity breach data to identify and engage potential customers.

## Features

- **Dynamic Dashboard**: Real-time metrics showing email campaigns, response rates, and lead tracking
- **Contact Management**: Store and organize prospect information with risk scoring
- **Campaign Management**: Create and manage email outreach campaigns
- **Breach Analysis**: Integration with cybersecurity breach data for risk assessment
- **Email Templates**: Customizable templates for different risk levels
- **Response Tracking**: Monitor email delivery, opens, clicks, and responses
- **Lead Scoring**: Automated identification of hot leads requiring attention

## Dashboard Metrics

- **Email Performance**: Track sent, delivered, opened, and bounced emails
- **Response Analytics**: Monitor response rates and sentiment analysis
- **Campaign Status**: View active campaigns and their performance
- **Contact Database**: Manage prospect database with risk scores
- **Hot Lead Detection**: Identify high-priority prospects needing immediate attention

## Technology Stack

- **Backend**: Python Flask with Blueprint architecture
- **Database**: SQLite with SQLAlchemy ORM
- **Frontend**: Bootstrap 5, HTML5, JavaScript
- **Authentication**: Session-based login system
- **Templates**: Jinja2 templating engine

## Project Structure

```
SalesBreachPro/
├── SalesBreachPro/
│   ├── app.py                 # Main Flask application
│   ├── models/
│   │   └── database.py        # Database models and schemas
│   ├── routes/
│   │   ├── auth.py           # Authentication routes
│   │   ├── dashboard.py      # Dashboard and settings
│   │   ├── campaigns.py      # Campaign management
│   │   ├── contacts.py       # Contact management
│   │   ├── api.py           # API endpoints
│   │   ├── analytics.py     # Analytics routes
│   │   └── tracking.py      # Email tracking
│   ├── templates/
│   │   ├── base.html        # Base template
│   │   ├── dashboard.html   # Main dashboard
│   │   ├── login.html       # Login page
│   │   └── ...             # Other templates
│   ├── static/
│   │   ├── css/
│   │   ├── js/
│   │   └── images/
│   ├── services/
│   │   └── template_routes.py # Email template routes
│   └── utils/
│       └── decorators.py    # Authentication decorators
└── README.md
```

## Installation & Setup

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd SalesBreachPro
   ```

2. **Create virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install flask flask-sqlalchemy
   ```

4. **Run the application**:
   ```bash
   cd SalesBreachPro
   python app.py
   ```

5. **Access the application**:
   - Open browser to `http://localhost:5000`
   - Login with credentials: `admin` / `SalesBreachPro2025!`

## Database Models

- **Contact**: Store prospect information and risk scores
- **Campaign**: Manage email outreach campaigns
- **Email**: Track individual email sends and responses
- **Response**: Store email responses with sentiment analysis
- **EmailTemplate**: Customizable email templates
- **Breach**: Cybersecurity breach data for risk assessment
- **Settings**: Application configuration settings

## Usage

1. **Dashboard**: View comprehensive metrics and campaign performance
2. **Contacts**: Add and manage prospect database
3. **Campaigns**: Create and monitor email outreach campaigns
4. **Templates**: Design custom email templates for different risk levels
5. **Analytics**: Track performance metrics and ROI

## Security Features

- Session-based authentication
- SQL injection protection via SQLAlchemy
- XSS protection through template escaping
- Secure password handling
- Input validation and sanitization

## Development

The application uses a modular Flask Blueprint architecture for scalability and maintainability. Each major feature is organized into separate blueprints with their own routes and logic.

## License

This project is for internal use and demonstration purposes.

---

**Generated with Claude Code**