import asyncio
import datetime
import os
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv()

def log(msg: str) -> None:
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")

POLL_SECONDS = 30

# One entry per movie/showtime/day you want to watch
TARGETS = [
    {
        "name": "Dune - Sun Dec 20・11:00 PM",
        "url": "https://www.cineplex.com/ticketing/preview?theatreId=7408&showtimeId=531223&dbox=false",
        "wanted_seats": [],
        "number_of_showtimes": 2

    },
    {
        "name": "Dune - Sat Dec 19・11:00 PM",
        "url": "https://www.cineplex.com/ticketing/preview?theatreId=7408&showtimeId=531222&dbox=false",
        "wanted_seats": [],
        "number_of_showtimes": 2
    },
    {
        "name": "Dune - Fri Dec 18・11:00 PM",
        "url": "https://www.cineplex.com/ticketing/preview?theatreId=7408&showtimeId=531221&dbox=false",
        "wanted_seats": [],
        "number_of_showtimes": 2
    },
    {
        "name": "Dune - Thur Dec 17・11:00 PM",
        "url": "https://www.cineplex.com/ticketing/preview?locationId=7408&showtimeId=531220&dbox=false",
        "wanted_seats": [],
        "number_of_showtimes": 2
    },
    {
        "name": "Dune - Thur Dec 17・7:00 PM",
        "url": "https://www.cineplex.com/ticketing/preview?theatreId=7408&showtimeId=530758&dbox=false",
        "wanted_seats": [],
        "number_of_showtimes": 2
    },
    {
        "name": "Dune - Fri Dec 18・7:00 PM",
        "url": "https://www.cineplex.com/ticketing/preview?theatreId=7408&showtimeId=530759&dbox=false",
        "wanted_seats": [],
        "number_of_showtimes": 2
    },
    {
        "name": "Dune - Sat Dec 19・7:00 PM",
        "url": "https://www.cineplex.com/ticketing/preview?theatreId=7408&showtimeId=530760&dbox=false",
        "wanted_seats": [],
        "number_of_showtimes": 2
    },
    {
        "name": "Dune - Sun Dec 20・7:00 PM",
        "url": "https://www.cineplex.com/ticketing/preview?theatreId=7408&showtimeId=530761&dbox=false",
        "wanted_seats": [],
        "number_of_showtimes": 2
    },
    {
        "name": "The Odyssey - Thu Jul 16・2:00 PM",
        "url": "https://www.cineplex.com/ticketing/preview?theatreId=7408&showtimeId=511927&dbox=false",
        "wanted_seats": [],
        "number_of_showtimes": 1
    },
    {
        "name": "The Odyssey - Fri Jul 17・7:00 PM",
        "url": "https://www.cineplex.com/ticketing/preview?theatreId=7408&showtimeId=511924&dbox=false",
        "wanted_seats": [],
        "number_of_showtimes": 1
    },
    {
        "name": "The Odyssey - sat Jul 18・7:00 PM",
        "url": "https://www.cineplex.com/ticketing/preview?theatreId=7408&showtimeId=511925&dbox=false",
        "wanted_seats": [],
        "number_of_showtimes": 1
    },
    {
        "name": "The Odyssey - sun Jul 19・7:00 PM",
        "url": "https://www.cineplex.com/ticketing/preview?theatreId=7408&showtimeId=511926&dbox=false",
        "wanted_seats": [],
        "number_of_showtimes": 1
    },
    {
        "name": "Test - sun Jul 19・7:00 PM",
        "url": "https://www.cineplex.com/ticketing/preview?theatreId=7408&showtimeId=531246&dbox=false",
        "wanted_seats": ["F10"],
        "number_of_showtimes": 0
    }
]



EMAIL_FROM = os.environ.get("ALERT_EMAIL_FROM")
EMAIL_TO = os.environ.get("ALERT_EMAIL_TO")
SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASS = os.environ.get("SMTP_PASS")

def _send_email_sync(subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)

async def send_email(subject: str, body: str) -> None:
    if not all([EMAIL_FROM, EMAIL_TO, SMTP_HOST, SMTP_USER, SMTP_PASS]):
        log("Email not configured; printing alert instead:")
        log(subject)
        log(body)
        return
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, lambda: _send_email_sync(subject, body))
    log(f"Email sent: {subject}")

async def check_target(page, target):
    log(f"Checking: {target['name']}")
    await page.goto(target["url"], wait_until="load")
    await page.wait_for_selector('svg [data-testid^="Standard-"]', timeout=30000)

    wanted = target.get("wanted_seats", [])
    available = []
    extra_showtimes = 0

    # Run seat check and showtime count concurrently
    async def get_seats():
        if wanted:
            log(f"  Looking for specific seats: {wanted}")
            for seat in wanted:
                selector = f'svg [data-testid="Standard-available-seat-{seat}"]'
                if await page.locator(selector).count() > 0:
                    available.append(seat)
        else:
            elements = await page.locator('svg [data-testid^="Standard-available-seat-"]').all()
            for el in elements:
                test_id = await el.get_attribute("data-testid")
                seat = test_id.replace("Standard-available-seat-", "")
                available.append(seat)

    async def get_showtime_count():
        nonlocal extra_showtimes
        expected = target.get("number_of_showtimes")
        if expected is None:
            return
        container = page.locator("div.DraggableScrollContainer_scrollContent__QR6O0")
        actual = await container.locator("button").count()
        log(f"  Showtimes: {actual} found, {expected} expected")
        if actual > expected:
            extra_showtimes = actual - expected

    await asyncio.gather(get_seats(), get_showtime_count())

    if available:
        log(f"  Seats: {len(available)} available -> {available}")
    else:
        log(f"  Seats: none available")

    return available, extra_showtimes

SEAT_COOLDOWN_HOURS = 24

async def main():
    poll_count = 0
    seat_alerted: dict[str, datetime.datetime] = {}  # key -> time of last seat alert
    showtime_alerted: set[str] = set()               # keys permanently suppressed after first showtime alert

    log(f"Starting seat monitor for {len(TARGETS)} showtime(s). Polling every {POLL_SECONDS}s.")
    for t in TARGETS:
        seats = t['wanted_seats'] if t['wanted_seats'] else "any"
        log(f"  - {t['name']} | seats: {seats} | expected showtimes: {t.get('number_of_showtimes', 'N/A')}")

    async with async_playwright() as p:
        log("Launching browser...")
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()

        pages = []
        for target in TARGETS:
            page = await context.new_page()
            pages.append((page, target))
        log("Browser ready.\n")

        while True:
            poll_count += 1
            log(f"--- Poll #{poll_count} ---")
            now = datetime.datetime.now()

            results = await asyncio.gather(
                *[check_target(page, target) for page, target in pages],
                return_exceptions=True
            )

            for (page, target), result in zip(pages, results):
                key = target["name"]
                if isinstance(result, Exception):
                    log(f"ERROR checking {key}: {result}")
                    continue
                available, extra_showtimes = result

                if available:
                    last = seat_alerted.get(key)
                    if last is None or (now - last).total_seconds() >= SEAT_COOLDOWN_HOURS * 3600:
                        log(f"ALERT [SEATS]: {key} | {target['url']} -> {available}")
                        await send_email(
                            f"Seat available: {key}",
                            f"Movie/Showtime: {key}\nFound available seats: {', '.join(available)}\n{target['url']}",
                        )
                        seat_alerted[key] = now
                    else:
                        hours_left = SEAT_COOLDOWN_HOURS - (now - last).total_seconds() / 3600
                        log(f"  Seats found for {key} — suppressed (re-alerts in {hours_left:.1f}h)")

                if extra_showtimes and key not in showtime_alerted:
                    expected = target.get("number_of_showtimes")
                    log(f"ALERT [NEW SHOWTIME]: {key} | {extra_showtimes} new showtime(s) detected (expected {expected}, got {expected + extra_showtimes}) | {target['url']}")
                    await send_email(
                        f"New showtime added: {key}",
                        f"Movie/Showtime: {key}\n{extra_showtimes} new showtime(s) detected (expected {expected}, got {expected + extra_showtimes})\n{target['url']}",
                    )
                    showtime_alerted.add(key)

            log(f"Poll #{poll_count} done. Sleeping {POLL_SECONDS}s...\n")
            await asyncio.sleep(POLL_SECONDS)

if __name__ == "__main__":
    asyncio.run(main())
