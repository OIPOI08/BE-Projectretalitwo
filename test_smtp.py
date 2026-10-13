
import smtplib
import ssl
from app.config import (
    EMAIL_USER,
    EMAIL_APP_PASSWORD,
    SMTP_HOST,
    SMTP_PORT,
)

print("SMTP:", SMTP_HOST, SMTP_PORT)
print("Email tersedia:", bool(EMAIL_USER))
print("Panjang App Password:", len(EMAIL_APP_PASSWORD or ""))

try:
    context = ssl.create_default_context()

    with smtplib.SMTP(
        SMTP_HOST,
        SMTP_PORT,
        timeout=30,
    ) as server:
        

        print("1. Koneksi SMTP berhasil")

        server.ehlo()
        server.starttls(context=context)
        server.ehlo()

        print("2. STARTTLS berhasil")

        server.login(EMAIL_USER, EMAIL_APP_PASSWORD)

        print("3. Login Gmail berhasil")

except Exception as e:
    print("Tipe error:", type(e).__name__)
    print("Detail error:", repr(e))
