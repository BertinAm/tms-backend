# TMS Backend

Django REST API backend for the Tangento Management System (TMS).

## Features

- **Email Monitoring**: Automated monitoring of Contabo abuse emails
- **AI Integration**: Grok API integration for ticket analysis
- **WhatsApp Notifications**: Real-time notifications via pywhatkit
- **Authentication**: JWT-based authentication with OTP verification
- **Real-time Updates**: WebSocket support with Django Channels
- **REST API**: Comprehensive API endpoints for ticket management

## Tech Stack

- **Django 4.2+**
- **Django REST Framework**
- **Django Channels** (WebSockets)
- **Redis** (Channel Layer)
- **SQLite** (Development)
- **PostgreSQL** (Production)
- **JWT Authentication**
- **IMAP Email Monitoring**
- **Grok AI Integration**

## Quick Start

### Prerequisites

- Python 3.8+
- Redis Server
- Virtual Environment

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/BertinAm/tms-backend.git
   cd tms-backend
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Setup**
   ```bash
   cp env.example .env
   # Edit .env with your configuration
   ```

5. **Database Setup**
   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   ```

6. **Run the server**
   ```bash
   python manage.py runserver
   ```

## Environment Variables

Create a `.env` file with the following variables:

```env
# Django
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_URL=sqlite:///db.sqlite3

# Email (Gmail)
GMAIL_USER=your-email@gmail.com
GMAIL_PASSWORD=your-app-password

# WhatsApp
WHATSAPP_PHONE=+xxx xxxxxxxxx

# AI Integration
GROK_API_KEY=your-grok-api-key

# Redis
REDIS_URL=redis://localhost:6379/0
```

## API Endpoints

### Authentication
- `POST /api/auth/register` - User registration
- `POST /api/auth/login` - User login
- `POST /api/auth/logout` - User logout
- `POST /api/auth/forgot-password` - Forgot password
- `POST /api/auth/check-otp` - OTP verification
- `POST /api/auth/reset-password` - Reset password

### Tickets
- `GET /api/tickets/` - List all tickets
- `GET /api/tickets/{id}/` - Get ticket details
- `GET /api/tickets/analytics` - Ticket analytics
- `POST /api/tickets/{id}/analyze` - Analyze ticket with AI

### Chat
- `POST /api/chat` - Chat with AI
- `GET /api/chat/history` - Chat history

### Monitoring
- `POST /api/monitor/email` - Start/stop email monitoring
- `GET /api/monitor/service` - Monitor service status

### Notifications
- `GET /api/notifications` - Get notifications
- `WS /ws/notifications/` - WebSocket notifications

## Email Monitoring

The system automatically monitors emails from `abuse@contabo.com` and creates tickets.

### Manual Commands

```bash
# Start email monitoring
python manage.py monitor_emails

# Export existing emails
python manage.py export_contabo_emails

# Test WhatsApp connection
python manage.py test_whatsapp
```

## Deployment

### Render Deployment

1. Connect your repository to Render
2. Set environment variables in Render dashboard
3. Configure build command: `pip install -r requirements.txt`
4. Configure start command: `gunicorn --bind 0.0.0.0:$PORT backend.wsgi:application`

### Environment Variables for Production

```env
DEBUG=False
ALLOWED_HOSTS=your-domain.com
DATABASE_URL=postgresql://user:pass@host:port/db
REDIS_URL=redis://your-redis-url
```

## Development

### Running Tests
```bash
python manage.py test
```

### Code Formatting
```bash
black .
isort .
```

### Database Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is licensed under the MIT License.
