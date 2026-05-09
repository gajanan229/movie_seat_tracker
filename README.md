# Movie Seat Tracker

Monitors Cineplex showtimes for available seats and new showtime additions, sending email alerts when either is detected.

## How It Works

- Polls a configurable list of Cineplex ticketing URLs in parallel every 30 seconds
- For each target, simultaneously checks for available seats and compares the current showtime count against an expected value
- Sends an email alert when seats become available or new showtimes are added
- Seat alerts are suppressed for 24 hours after firing to avoid duplicate notifications; showtime alerts fire once permanently

## Configuration

### Targets

Edit the `TARGETS` list in `src/webclient.py`. Each entry requires:

```python
{
    "name": "Movie - Date・Time",
    "url": "https://www.cineplex.com/ticketing/preview?...",
    "wanted_seats": [],        # leave empty for any seat, or specify e.g. ["F14", "F15"]
    "number_of_showtimes": 2   # current number of showtimes shown on the page
}
```

### Environment Variables

Create a `.env` file in the project root:

```
ALERT_EMAIL_FROM=you@gmail.com
ALERT_EMAIL_TO=you@gmail.com
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASS=your_app_password
```

For Gmail, `SMTP_PASS` must be an [App Password](https://myaccount.google.com/apppasswords) — not your regular account password. App Passwords require 2-Step Verification to be enabled on your Google account.

## Running

### Docker (recommended)

```bash
docker build -t movie-tracker .
docker run --env-file .env movie-tracker
```

### Local

```bash
python -m venv venv
.\venv\Scripts\Activate.ps1       # Windows
pip install -r requirements.txt
playwright install chromium
playwright install-deps chromium
python src/webclient.py
```

## Requirements

- Python 3.12+
- Playwright (Chromium)
- python-dotenv
