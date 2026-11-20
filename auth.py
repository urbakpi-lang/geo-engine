"""
geo-engine · auth.py — accesso senza password con "link magico" via email.

Flusso:
  1. POST /auth/request {email, lang}  -> se l'email è valida si manda un link (valido 30 minuti)
  2. il link apre APP_URL#token=...    -> la pagina chiama POST /auth/verify {token}
  3. /auth/verify restituisce una sessione firmata (valida 30 giorni) da mandare come
     header  Authorization: Bearer <sessione>

Variabili d'ambiente:
  SECRET_KEY      obbligatoria in produzione (stringa lunga e casuale): firma le sessioni
  APP_URL         pagina dell'area utente, es. https://groveproof.netlify.app/app.html
  RESEND_API_KEY  invio email con Resend (consigliato); in alternativa SMTP_HOST/SMTP_USER/SMTP_PASS
  MAIL_FROM       mittente, es. "GroveProof <login@groveproof.eu>"
  AUTH_DEV_LINKS  "1" = restituisce il link anche nella risposta (SOLO per prove locali)
"""
import base64
import hashlib
import hmac
import json
import os
import re
import smtplib
import time
from datetime import timedelta
from email.message import EmailMessage

import requests
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

import db

SECRET_KEY = os.getenv("SECRET_KEY", "").strip()
if not SECRET_KEY:
    SECRET_KEY = "dev-only-" + hashlib.sha256(os.urandom(32)).hexdigest()
    print("[auth] ATTENZIONE: SECRET_KEY non impostata, sessioni valide solo fino al riavvio", flush=True)
APP_URL = os.getenv("APP_URL", "https://groveproof.netlify.app/app.html").strip()
MAIL_FROM = os.getenv("MAIL_FROM", "GroveProof <onboarding@resend.dev>").strip()
DEV_LINKS = os.getenv("AUTH_DEV_LINKS", "") == "1"
SESSION_DAYS = 30
TOKEN_MINUTES = 30
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[A-Za-z]{2,}$")

_rate: dict = {}


def _rate_ok(key: str, limit: int, window_s: int) -> bool:
    t = time.time()
    hits = [x for x in _rate.get(key, []) if t - x < window_s]
    if len(hits) >= limit:
        _rate[key] = hits
        return False
    hits.append(t)
    _rate[key] = hits
    return True


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def make_session(user_id: str) -> str:
    body = _b64(json.dumps({"u": user_id, "e": int(time.time()) + SESSION_DAYS * 86400}).encode())
    sig = _b64(hmac.new(SECRET_KEY.encode(), body.encode(), hashlib.sha256).digest())
    return body + "." + sig


def read_session(token: str) -> str | None:
    try:
        body, sig = token.split(".", 1)
        good = _b64(hmac.new(SECRET_KEY.encode(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, good):
            return None
        data = json.loads(_unb64(body))
        return data["u"] if data.get("e", 0) > time.time() else None
    except Exception:
        return None


# ---------------- email ----------------
TEXTS = {
    "en": ("Your GroveProof sign-in link", "Click to sign in to GroveProof (valid for 30 minutes):",
           "If you did not ask for this, ignore this email."),
    "de": ("Ihr Anmeldelink für GroveProof", "Klicken Sie, um sich bei GroveProof anzumelden (30 Minuten gültig):",
           "Wenn Sie das nicht angefordert haben, ignorieren Sie diese E-Mail."),
    "it": ("Il tuo link di accesso a GroveProof", "Clicca per entrare in GroveProof (valido 30 minuti):",
           "Se non l'hai chiesto tu, ignora questa email."),
}


def send_email(to: str, subject: str, text: str, html: str | None = None) -> bool:
    key = os.getenv("RESEND_API_KEY", "").strip()
    try:
        if key:
            r = requests.post("https://api.resend.com/emails", timeout=20,
                              headers={"Authorization": "Bearer " + key},
                              json={"from": MAIL_FROM, "to": [to], "subject": subject, "text": text,
                                    **({"html": html} if html else {})})
            if r.status_code >= 300:
                print("[mail] Resend %s: %s" % (r.status_code, r.text[:200]), flush=True)
                return False
            return True
        host = os.getenv("SMTP_HOST", "").strip()
        if host:
            msg = EmailMessage()
            msg["From"], msg["To"], msg["Subject"] = MAIL_FROM, to, subject
            msg.set_content(text)
            if html:
                msg.add_alternative(html, subtype="html")
            with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "587")), timeout=20) as s:
                s.starttls()
                s.login(os.getenv("SMTP_USER", ""), os.getenv("SMTP_PASS", ""))
                s.send_message(msg)
            return True
    except Exception as e:
        print("[mail] errore: %s" % e, flush=True)
        return False
    # il testo NON si scrive nei log: può contenere un link di accesso
    print("[mail] nessun servizio email configurato (RESEND_API_KEY o SMTP_HOST): non inviata a %s" % to, flush=True)
    return False


def request_login(s: Session, email: str, lang: str = "en", ip: str = "") -> dict:
    email = (email or "").strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(400, "Email non valida.")
    if not _rate_ok("mail:" + email, 5, 3600) or not _rate_ok("ip:" + ip, 20, 3600):
        raise HTTPException(429, "Troppe richieste: riprova tra un'ora.")
    raw = _b64(os.urandom(32))
    s.add(db.LoginToken(token_hash=hashlib.sha256(raw.encode()).hexdigest(), email=email,
                        expires_at=db.now() + timedelta(minutes=TOKEN_MINUTES)))
    s.commit()
    link = "%s#token=%s" % (APP_URL, raw)
    subj, line, foot = TEXTS.get(lang, TEXTS["en"])
    sent = send_email(email, subj, "%s\n\n%s\n\n%s" % (line, link, foot),
                      "<p>%s</p><p><a href=\"%s\">%s</a></p><p style=\"color:#777\">%s</p>"
                      % (line, link, subj, foot))
    out = {"ok": True, "sent": sent}
    if DEV_LINKS:
        out["dev_link"] = link
    return out


def verify_login(s: Session, raw: str) -> dict:
    h = hashlib.sha256((raw or "").encode()).hexdigest()
    t = s.get(db.LoginToken, h)
    exp = t.expires_at if t else None
    if exp is not None and exp.tzinfo is None:            # SQLite non conserva il fuso orario
        exp = exp.replace(tzinfo=db.now().tzinfo)
    if not t or t.used or exp < db.now():
        raise HTTPException(401, "Link non valido o scaduto: chiedine uno nuovo.")
    t.used = True
    user = s.query(db.User).filter(db.User.email == t.email).one_or_none()
    new = user is None
    if new:
        org = db.Org(name="", lang="en")
        s.add(org)
        s.flush()
        user = db.User(email=t.email, org_id=org.id)
        s.add(user)
    user.last_login = db.now()
    s.commit()
    return {"session": make_session(user.id), "new_account": new}


def current_user(authorization: str = Header(default=""), s: Session = Depends(db.get_db)) -> db.User:
    tok = authorization.split(" ", 1)[1] if authorization.lower().startswith("bearer ") else ""
    uid = read_session(tok) if tok else None
    user = s.get(db.User, uid) if uid else None
    if not user:
        raise HTTPException(401, "Accesso richiesto.")
    return user
