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

POLL_SECONDS = 1
CONCURRENCY = 5  # max pages open simultaneously
SEAT_COOLDOWN_HOURS = 6

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
        "wanted_seats": ["F10", "F11"],
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
        log(f"Email not configured — alert: {subject}")
        return
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, lambda: _send_email_sync(subject, body))
    log(f"Email sent: {subject}")

async def check_target(context, target, sem):
    async with sem:
        page = await context.new_page()
        try:
            return await _check_target(page, target)
        finally:
            await page.close()

async def _check_target(page, target):
    await page.goto(target["url"], wait_until="load")
    await page.wait_for_selector('svg [data-testid^="Standard-"]', timeout=30000)
    await asyncio.sleep(1)

    wanted = target.get("wanted_seats", [])
    available = []
    extra_showtimes = 0

    async def query_any_seats():
        elements = await page.locator('svg [data-testid^="Standard-available-seat-"]').all()
        seats = []
        for el in elements:
            test_id = await el.get_attribute("data-testid")
            seats.append(test_id.replace("Standard-available-seat-", ""))
        return seats

    async def get_seats():
        if wanted:
            for seat in wanted:
                selector = f'svg [data-testid="Standard-available-seat-{seat}"]'
                if await page.locator(selector).count() > 0:
                    available.append(seat)
        else:
            seats = await query_any_seats()
            if len(seats) > 200:
                for attempt in range(3):
                    log(f"  [{target['name']}] {len(seats)} seats found — possible render glitch, retrying ({attempt + 1}/3)...")
                    await asyncio.sleep(2)
                    seats = await query_any_seats()
                    if len(seats) <= 200:
                        break
                else:
                    log(f"  [{target['name']}] still {len(seats)} seats after 3 retries — alerting anyway")
            available.extend(seats)

    async def get_showtime_count():
        nonlocal extra_showtimes
        expected = target.get("number_of_showtimes")
        if expected is None:
            return
        container = page.locator("div.DraggableScrollContainer_scrollContent__QR6O0")
        actual = await container.locator("button").count()
        if actual > expected:
            extra_showtimes = actual - expected

    await asyncio.gather(get_seats(), get_showtime_count())
    return available, extra_showtimes

async def main():
    poll_count = 0
    seat_alerted: dict[tuple[str, str], datetime.datetime] = {}  # (showtime, seat) -> last alert time
    showtime_alerted: set[str] = set()

    log(f"Starting seat monitor — {len(TARGETS)} targets, polling every {POLL_SECONDS}s, concurrency {CONCURRENCY}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-gpu",
                "--disable-extensions",
                "--disable-background-networking",
            ],
        )
        context = await browser.new_context()
        sem = asyncio.Semaphore(CONCURRENCY)

        while True:
            poll_count += 1
            log(f"--- Poll #{poll_count} ---")
            now = datetime.datetime.now()

            results = await asyncio.gather(
                *[check_target(context, target, sem) for target in TARGETS],
                return_exceptions=True
            )

            alerts = 0
            for target, result in zip(TARGETS, results):
                key = target["name"]
                if isinstance(result, Exception):
                    log(f"ERROR [{key}]: {result}")
                    continue
                available, extra_showtimes = result

                if available:
                    new_seats = []
                    suppressed_seats = []
                    for seat in available:
                        seat_key = (key, seat)
                        last = seat_alerted.get(seat_key)
                        if last is None or (now - last).total_seconds() >= SEAT_COOLDOWN_HOURS * 3600:
                            new_seats.append(seat)
                            seat_alerted[seat_key] = now
                        else:
                            suppressed_seats.append(seat)

                    if suppressed_seats:
                        log(f"SUPPRESSED [SEATS]: {key} — {suppressed_seats} already alerted within 24h")
                    if new_seats:
                        log(f"ALERT [SEATS]: {key} -> {new_seats}")
                        await send_email(
                            f"Seat available: {key}",
                            f"Movie/Showtime: {key}\nFound available seats: {', '.join(new_seats)}\n{target['url']}",
                        )
                        alerts += 1

                if extra_showtimes and key not in showtime_alerted:
                    expected = target.get("number_of_showtimes")
                    log(f"ALERT [NEW SHOWTIME]: {key} — {extra_showtimes} new (expected {expected}, got {expected + extra_showtimes})")
                    await send_email(
                        f"New showtime added: {key}",
                        f"Movie/Showtime: {key}\n{extra_showtimes} new showtime(s) detected (expected {expected}, got {expected + extra_showtimes})\n{target['url']}",
                    )
                    showtime_alerted.add(key)
                    alerts += 1

            log(f"Poll #{poll_count} done — {alerts} alert(s). Sleeping {POLL_SECONDS}s...\n")
            await asyncio.sleep(POLL_SECONDS)

if __name__ == "__main__":
    asyncio.run(main())
