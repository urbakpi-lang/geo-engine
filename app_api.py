"""
geo-engine · app_api.py — API dell'area utente di GroveProof (montate da main.py).

Pubbliche:   POST /auth/request · POST /auth/verify · POST /leads · POST /reports · GET /reports/{id}
             GET /reports/{id}/pdf · GET /public/{slug} · GET /badge/{slug}.svg · GET /qr/{slug}.svg
Con accesso: GET/PATCH /me · /suppliers · /lots · /plots (+ /plots/import, /plots/check)
             GET /registry.csv · GET /registry.pdf
Admin:       POST /admin/plan  (header X-Admin-Token = ADMIN_TOKEN) — finché non c'è il pagamento online
"""
import csv
import io
import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

import auth
import db
from engine import analyze

router = APIRouter()
SITE_URL = os.getenv("SITE_URL", "https://groveproof.netlify.app").rstrip("/")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "").strip()
MAX_CHECK = 200

VERDICT_TXT = {
    "en": {"OK": "Deforestation-free", "OK_NO_FOREST_2020": "No forest in 2020", "A_RISCHIO": "At risk - review",
           "DATI_MANCANTI": "Data needed", None: "Not checked"},
    "de": {"OK": "Entwaldungsfrei", "OK_NO_FOREST_2020": "Kein Wald 2020", "A_RISCHIO": "Risiko - pruefen",
           "DATI_MANCANTI": "Daten fehlen", None: "Nicht geprueft"},
    "it": {"OK": "Senza deforestazione", "OK_NO_FOREST_2020": "Nessuna foresta nel 2020",
           "A_RISCHIO": "A rischio - da rivedere", "DATI_MANCANTI": "Dati mancanti", None: "Non verificata"},
}
OK_VERDICTS = ("OK", "OK_NO_FOREST_2020")
CONF_TXT = {"en": {"alta": "high", "media": "medium", "bassa": "low"},
            "de": {"alta": "hoch", "media": "mittel", "bassa": "niedrig"},
            "it": {"alta": "alta", "media": "media", "bassa": "bassa"}}


def _lang(x):
    return x if x in ("en", "de", "it") else "en"


def _iso(d):
    return d.isoformat() if isinstance(d, datetime) else d


def _row(o, fields):
    return {f: _iso(getattr(o, f)) for f in fields}


# ======================= account =======================
class LoginReq(BaseModel):
    email: str
    lang: Optional[str] = "en"


class VerifyReq(BaseModel):
    token: str


@router.post("/auth/request")
def auth_request(req: LoginReq, request: Request, s: Session = Depends(db.get_db)):
    ip = request.client.host if request.client else ""
    return auth.request_login(s, req.email, _lang(req.lang), ip)


@router.post("/auth/verify")
def auth_verify(req: VerifyReq, s: Session = Depends(db.get_db)):
    return auth.verify_login(s, req.token)


ORG_FIELDS = ["id", "name", "kind", "country", "plan", "slug", "public", "public_text", "website",
              "share_plots", "lang", "created_at"]


def _usage(s, org):
    n = s.query(func.count(db.Plot.id)).filter(db.Plot.org_id == org.id).scalar() or 0
    return {"plots": n, "limits": db.PLANS.get(org.plan, db.PLANS["free"])}


@router.get("/me")
def me(user: db.User = Depends(auth.current_user), s: Session = Depends(db.get_db)):
    org = s.get(db.Org, user.org_id)
    return {"user": {"email": user.email, "role": user.role}, "org": _row(org, ORG_FIELDS), "usage": _usage(s, org)}


class OrgPatch(BaseModel):
    name: Optional[str] = None
    kind: Optional[str] = None
    country: Optional[str] = None
    slug: Optional[str] = None
    public: Optional[bool] = None
    public_text: Optional[str] = Field(None, max_length=2000)
    website: Optional[str] = None
    share_plots: Optional[bool] = None
    lang: Optional[str] = None


SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,58}[a-z0-9])$")


@router.patch("/me")
def me_patch(p: OrgPatch, user: db.User = Depends(auth.current_user), s: Session = Depends(db.get_db)):
    org = s.get(db.Org, user.org_id)
    data = p.model_dump(exclude_none=True)
    if "slug" in data:
        slug = data["slug"].strip().lower()
        if not SLUG_RE.match(slug):
            raise HTTPException(400, "Indirizzo pubblico: 3-60 caratteri, solo lettere minuscole, numeri e trattini.")
        other = s.query(db.Org).filter(db.Org.slug == slug, db.Org.id != org.id).first()
        if other:
            raise HTTPException(409, "Questo indirizzo pubblico è già usato.")
        data["slug"] = slug
    if "website" in data and data["website"] and not re.match(r"^https?://", data["website"]):
        data["website"] = "https://" + data["website"]
    if "lang" in data:
        data["lang"] = _lang(data["lang"])
    for k, v in data.items():
        setattr(org, k, v)
    s.commit()
    return {"org": _row(org, ORG_FIELDS), "usage": _usage(s, org)}


# ======================= registro: fornitori =======================
SUP_FIELDS = ["id", "name", "role", "country", "address", "email", "eori", "notes", "created_at"]


class SupplierIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    role: Optional[str] = "importer"
    country: Optional[str] = ""
    address: Optional[str] = ""
    email: Optional[str] = ""
    eori: Optional[str] = ""
    notes: Optional[str] = ""


def _own(s, model, oid, user):
    o = s.get(model, oid)
    if not o or o.org_id != user.org_id:
        raise HTTPException(404, "Non trovato.")
    return o


@router.get("/suppliers")
def suppliers(user: db.User = Depends(auth.current_user), s: Session = Depends(db.get_db)):
    q = s.query(db.Supplier).filter(db.Supplier.org_id == user.org_id).order_by(db.Supplier.name)
    return {"suppliers": [_row(x, SUP_FIELDS) for x in q]}


@router.post("/suppliers")
def supplier_new(p: SupplierIn, user: db.User = Depends(auth.current_user), s: Session = Depends(db.get_db)):
    x = db.Supplier(org_id=user.org_id, **p.model_dump())
    s.add(x)
    s.commit()
    return _row(x, SUP_FIELDS)


@router.patch("/suppliers/{sid}")
def supplier_edit(sid: str, p: SupplierIn, user: db.User = Depends(auth.current_user),
                  s: Session = Depends(db.get_db)):
    x = _own(s, db.Supplier, sid, user)
    for k, v in p.model_dump().items():
        setattr(x, k, v)
    s.commit()
    return _row(x, SUP_FIELDS)


@router.delete("/suppliers/{sid}")
def supplier_del(sid: str, user: db.User = Depends(auth.current_user), s: Session = Depends(db.get_db)):
    s.delete(_own(s, db.Supplier, sid, user))
    s.commit()
    return {"ok": True}


# ======================= registro: lotti =======================
LOT_FIELDS = ["id", "supplier_id", "direction", "code", "product", "origin_country", "quantity_kg", "hs_code",
              "dds_reference", "dds_verification", "date", "notes", "created_at"]


class LotIn(BaseModel):
    supplier_id: Optional[str] = None
    direction: Optional[str] = "in"
    code: Optional[str] = ""
    product: Optional[str] = ""
    origin_country: Optional[str] = ""
    quantity_kg: Optional[float] = None
    hs_code: Optional[str] = "0901"
    dds_reference: Optional[str] = ""
    dds_verification: Optional[str] = ""
    date: Optional[str] = ""
    notes: Optional[str] = ""


def _check_supplier(s, user, sid):
    if sid:
        _own(s, db.Supplier, sid, user)


@router.get("/lots")
def lots(user: db.User = Depends(auth.current_user), s: Session = Depends(db.get_db)):
    q = s.query(db.Lot).filter(db.Lot.org_id == user.org_id).order_by(db.Lot.date.desc(), db.Lot.created_at.desc())
    return {"lots": [_row(x, LOT_FIELDS) for x in q]}


@router.post("/lots")
def lot_new(p: LotIn, user: db.User = Depends(auth.current_user), s: Session = Depends(db.get_db)):
    _check_supplier(s, user, p.supplier_id)
    x = db.Lot(org_id=user.org_id, **p.model_dump())
    s.add(x)
    s.commit()
    return _row(x, LOT_FIELDS)


@router.patch("/lots/{lid}")
def lot_edit(lid: str, p: LotIn, user: db.User = Depends(auth.current_user), s: Session = Depends(db.get_db)):
    x = _own(s, db.Lot, lid, user)
    _check_supplier(s, user, p.supplier_id)
    for k, v in p.model_dump().items():
        setattr(x, k, v)
    s.commit()
    return _row(x, LOT_FIELDS)


@router.delete("/lots/{lid}")
def lot_del(lid: str, user: db.User = Depends(auth.current_user), s: Session = Depends(db.get_db)):
    s.delete(_own(s, db.Lot, lid, user))
    s.commit()
    return {"ok": True}


# ======================= particelle =======================
PLOT_FIELDS = ["id", "supplier_id", "lot_id", "ref", "country", "lat", "lng", "area_ha", "geometry", "producer",
               "public", "verdict", "confidence", "checked_at", "created_at"]


class PlotIn(BaseModel):
    ref: str = Field(..., min_length=1, max_length=80)
    country: Optional[str] = ""
    lat: Optional[float] = None
    lng: Optional[float] = None
    area_ha: Optional[float] = None
    geometry: Optional[dict] = None
    producer: Optional[str] = ""
    supplier_id: Optional[str] = None
    lot_id: Optional[str] = None
    public: Optional[bool] = True


def _limit(s, user, adding):
    org = s.get(db.Org, user.org_id)
    lim = db.PLANS.get(org.plan, db.PLANS["free"])["plots"]
    n = s.query(func.count(db.Plot.id)).filter(db.Plot.org_id == org.id).scalar() or 0
    if n + adding > lim:
        raise HTTPException(402, "Limite del piano %s: %d particelle. Passa a un piano superiore." % (org.plan, lim))


@router.get("/plots")
def plots(user: db.User = Depends(auth.current_user), s: Session = Depends(db.get_db)):
    q = s.query(db.Plot).filter(db.Plot.org_id == user.org_id).order_by(db.Plot.ref)
    return {"plots": [_row(x, PLOT_FIELDS) for x in q]}


@router.post("/plots/import")
def plots_import(items: List[PlotIn], user: db.User = Depends(auth.current_user), s: Session = Depends(db.get_db)):
    """Aggiunge o aggiorna (per riferimento) fino a 500 particelle in una volta."""
    if len(items) > 500:
        raise HTTPException(413, "Massimo 500 particelle per importazione.")
    existing = {p.ref: p for p in s.query(db.Plot).filter(db.Plot.org_id == user.org_id)}
    new = [i for i in items if i.ref not in existing]
    _limit(s, user, len(new))
    added = updated = 0
    for i in items:
        _check_supplier(s, user, i.supplier_id)
        data = i.model_dump()
        if i.ref in existing:
            p = existing[i.ref]
            for k, v in data.items():
                setattr(p, k, v)
            p.verdict = p.confidence = None              # dati cambiati: va riverificata
            updated += 1
        else:
            s.add(db.Plot(org_id=user.org_id, **data))
            added += 1
    s.commit()
    return {"added": added, "updated": updated}


@router.patch("/plots/{pid}")
def plot_edit(pid: str, p: PlotIn, user: db.User = Depends(auth.current_user), s: Session = Depends(db.get_db)):
    x = _own(s, db.Plot, pid, user)
    _check_supplier(s, user, p.supplier_id)
    for k, v in p.model_dump().items():
        setattr(x, k, v)
    x.verdict = x.confidence = None
    s.commit()
    return _row(x, PLOT_FIELDS)


@router.delete("/plots/{pid}")
def plot_del(pid: str, user: db.User = Depends(auth.current_user), s: Session = Depends(db.get_db)):
    s.delete(_own(s, db.Plot, pid, user))
    s.commit()
    return {"ok": True}


@router.get("/plots/{pid}/history")
def plot_history(pid: str, user: db.User = Depends(auth.current_user), s: Session = Depends(db.get_db)):
    _own(s, db.Plot, pid, user)
    q = s.query(db.Check).filter(db.Check.plot_id == pid).order_by(db.Check.created_at.desc()).limit(50)
    return {"checks": [{"id": c.id, "verdict": c.verdict, "confidence": c.confidence, "created_at": _iso(c.created_at),
                        "result": c.result} for c in q]}


class CheckReq(BaseModel):
    ids: Optional[List[str]] = None          # vuoto = tutte quelle mai verificate o con dati cambiati
    all: Optional[bool] = False
    lang: Optional[str] = None


def run_check(p_ref, geometry, area_ha, country, lang):
    return analyze("eudr_v2", geometry, {"area_ha": area_ha, "country": country, "lang": lang})


def _check_plot(p, lang):
    geom = p.geometry or ({"type": "Point", "coordinates": [p.lng, p.lat]}
                          if p.lat is not None and p.lng is not None else None)
    if not geom:
        return p, {"verdict": "DATI_MANCANTI", "confidence": "bassa", "reasons": ["Coordinate mancanti."]}
    try:
        return p, run_check(p.ref, geom, p.area_ha, p.country, lang)
    except Exception as e:
        return p, {"verdict": "DATI_MANCANTI", "confidence": "bassa", "error": str(e)[:300],
                   "reasons": ["Errore durante la verifica: riprova più tardi."]}


@router.post("/plots/check")
def plots_check(req: CheckReq, user: db.User = Depends(auth.current_user), s: Session = Depends(db.get_db)):
    org = s.get(db.Org, user.org_id)
    lang = _lang(req.lang or org.lang)
    q = s.query(db.Plot).filter(db.Plot.org_id == org.id)
    if req.ids:
        q = q.filter(db.Plot.id.in_(req.ids))
    elif not req.all:
        q = q.filter(db.Plot.verdict.is_(None))
    todo = q.limit(MAX_CHECK).all()

    with ThreadPoolExecutor(max_workers=6) as ex:
        results = list(ex.map(lambda p: _check_plot(p, lang), todo))
    out = []
    for p, r in results:
        p.verdict, p.confidence, p.checked_at = r.get("verdict"), r.get("confidence"), db.now()
        s.add(db.Check(plot_id=p.id, verdict=p.verdict, confidence=p.confidence, result=r))
        out.append({"id": p.id, "ref": p.ref, **r})
    s.commit()
    remaining = s.query(func.count(db.Plot.id)).filter(db.Plot.org_id == org.id, db.Plot.verdict.is_(None)).scalar()
    return {"checked": len(out), "remaining_unchecked": remaining, "results": out}


# ======================= export del registro =======================
def _registry_rows(s, org_id):
    sup = {x.id: x for x in s.query(db.Supplier).filter(db.Supplier.org_id == org_id)}
    lots = s.query(db.Lot).filter(db.Lot.org_id == org_id).order_by(db.Lot.date).all()
    plots = s.query(db.Plot).filter(db.Plot.org_id == org_id).order_by(db.Plot.ref).all()
    return sup, lots, plots


@router.get("/registry.csv")
def registry_csv(user: db.User = Depends(auth.current_user), s: Session = Depends(db.get_db)):
    sup, lots, plots = _registry_rows(s, user.org_id)
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["# REGISTRO EUDR - lotti (acquisti e vendite)"])
    w.writerow(["data", "direzione", "fornitore/cliente", "ruolo", "paese", "EORI", "lotto", "prodotto", "origine",
                "kg", "codice HS", "riferimento DDS", "verifica DDS", "note"])
    for l in lots:
        x = sup.get(l.supplier_id)
        w.writerow([l.date, "acquisto" if l.direction == "in" else "vendita", x.name if x else "", x.role if x else "",
                    x.country if x else "", x.eori if x else "", l.code, l.product, l.origin_country,
                    l.quantity_kg or "", l.hs_code, l.dds_reference, l.dds_verification, l.notes])
    w.writerow([])
    w.writerow(["# PARTICELLE"])
    w.writerow(["riferimento", "produttore", "paese", "lat", "lng", "ettari", "poligono", "esito", "confidenza",
                "verificata il", "fornitore"])
    for p in plots:
        x = sup.get(p.supplier_id)
        w.writerow([p.ref, p.producer, p.country, p.lat or "", p.lng or "", p.area_ha or "", "si" if p.geometry else "no",
                    p.verdict or "", p.confidence or "", _iso(p.checked_at) or "", x.name if x else ""])
    return Response(buf.getvalue().encode("utf-8-sig"), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=registro-eudr.csv"})


def _pdf_text(t):
    t = str(t if t is not None else "")
    for a, b in (("€", "EUR"), ("–", "-"), ("—", "-"), ("’", "'"), ("“", '"'), ("”", '"'), ("→", "->"), ("≥", ">=")):
        t = t.replace(a, b)
    return t.encode("latin-1", "replace").decode("latin-1")


def _pdf_table(pdf, headers, widths, rows):
    from fpdf import FPDF  # noqa: F401
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(235, 230, 220)
    for h, w in zip(headers, widths):
        pdf.cell(w, 6, _pdf_text(h), border=1, fill=True)
    pdf.ln()
    pdf.set_font("Helvetica", "", 8)
    for r in rows:
        if pdf.get_y() > 270:
            pdf.add_page()
        for v, w in zip(r, widths):
            txt = _pdf_text(v)
            while txt and pdf.get_string_width(txt) > w - 2:
                txt = txt[:-1]
            pdf.cell(w, 5.5, txt, border=1)
        pdf.ln()


def _pdf_doc(title, subtitle):
    from fpdf import FPDF
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(True, 15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 8.5)
    pdf.set_text_color(46, 125, 82)
    pdf.cell(0, 5, _pdf_text("GroveProof - EUDR deforestation check for coffee"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "B", 15)
    pdf.cell(0, 9, _pdf_text(title), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(90, 90, 90)
    pdf.multi_cell(0, 5, _pdf_text(subtitle))
    pdf.set_text_color(0, 0, 0)
    pdf.ln(3)
    return pdf


DISCLAIMER = ("Evidence to support due diligence under Regulation (EU) 2023/1115. Satellite data: UMD/Hansen tree "
              "cover loss, JRC Global Forest Cover 2020, WRI/Google DeepMind drivers, WDPA, LandMark (via Global "
              "Forest Watch). 'At risk' and low-confidence results need human review. Responsibility for the due "
              "diligence statement remains with the operator. Methodology: " + SITE_URL + "/#method")


@router.get("/registry.pdf")
def registry_pdf(user: db.User = Depends(auth.current_user), s: Session = Depends(db.get_db)):
    org = s.get(db.Org, user.org_id)
    sup, lots, plots = _registry_rows(s, org.id)
    vt = VERDICT_TXT[_lang(org.lang)]
    ct = CONF_TXT[_lang(org.lang)]
    pdf = _pdf_doc("EUDR register - %s" % (org.name or user.email),
                   "Generated by GroveProof on %s. Records of suppliers, customers and plots to keep for 5 years "
                   "(Regulation (EU) 2023/1115)." % db.now().strftime("%Y-%m-%d %H:%M UTC"))
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, "Lots (purchases and sales)", new_x="LMARGIN", new_y="NEXT")
    _pdf_table(pdf, ["Date", "In/out", "Supplier/customer", "Product", "Origin", "kg", "DDS reference"],
               [20, 13, 42, 40, 22, 15, 38],
               [[l.date, "in" if l.direction == "in" else "out", (sup.get(l.supplier_id).name if sup.get(l.supplier_id) else ""),
                 l.product, l.origin_country, l.quantity_kg or "", l.dds_reference] for l in lots])
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, "Plots of origin", new_x="LMARGIN", new_y="NEXT")
    _pdf_table(pdf, ["Plot", "Country", "Lat", "Lng", "ha", "Polygon", "Result", "Conf.", "Checked"],
               [28, 24, 17, 17, 12, 14, 38, 14, 26],
               [[p.ref, p.country, "%.5f" % p.lat if p.lat is not None else "", "%.5f" % p.lng if p.lng is not None else "",
                 p.area_ha or "", "yes" if p.geometry else "no", vt.get(p.verdict, p.verdict or ""), ct.get(p.confidence, p.confidence or ""),
                 (_iso(p.checked_at) or "")[:10]] for p in plots])
    pdf.ln(4)
    pdf.set_font("Helvetica", "", 7.5)
    pdf.set_text_color(90, 90, 90)
    pdf.multi_cell(0, 4, _pdf_text(DISCLAIMER))
    return Response(bytes(pdf.output()), media_type="application/pdf",
                    headers={"Content-Disposition": "attachment; filename=eudr-register.pdf"})


# ======================= contatti =======================
class LeadIn(BaseModel):
    email: str
    company: Optional[str] = ""
    source: Optional[str] = ""
    kind: Optional[str] = ""
    message: Optional[str] = Field("", max_length=2000)


def save_lead(email, company="", source="", kind="", message=""):
    email = (email or "").strip().lower()
    if not auth.EMAIL_RE.match(email):
        raise HTTPException(400, "Email non valida.")
    s = db.SessionLocal()
    try:
        s.add(db.Lead(email=email, company=(company or "")[:200], source=(source or "")[:60], kind=(kind or "")[:30],
                      message=message or ""))
        s.commit()
    finally:
        s.close()
    print("[lead] %s | %s | %s" % (email, company or "", source or ""), flush=True)
    notify = os.getenv("LEAD_NOTIFY_EMAIL", "").strip()
    if notify:
        auth.send_email(notify, "Nuovo contatto GroveProof: %s" % email,
                        "Email: %s\nAzienda: %s\nFonte: %s\nTipo: %s\n\n%s" % (email, company, source, kind, message))
    return {"ok": True}


@router.post("/leads")
def lead_new(p: LeadIn, request: Request):
    ip = request.client.host if request.client else ""
    if not auth._rate_ok("lead:" + ip, 20, 3600):
        raise HTTPException(429, "Troppe richieste.")
    return save_lead(p.email, p.company, p.source, p.kind, p.message)


@router.get("/admin/leads")
def admin_leads(x_admin_token: str = Header(default=""), s: Session = Depends(db.get_db)):
    _admin(x_admin_token)
    q = s.query(db.Lead).order_by(db.Lead.created_at.desc()).limit(1000)
    return {"leads": [{"email": l.email, "company": l.company, "source": l.source, "kind": l.kind,
                       "message": l.message, "created_at": _iso(l.created_at)} for l in q]}


# ======================= report condivisibili =======================
class ReportIn(BaseModel):
    results: list
    title: Optional[str] = ""
    lang: Optional[str] = "en"
    email: Optional[str] = ""
    company: Optional[str] = ""


@router.post("/reports")
def report_new(p: ReportIn, request: Request, authorization: str = Header(default=""),
               s: Session = Depends(db.get_db)):
    ip = request.client.host if request.client else ""
    if not auth._rate_ok("report:" + ip, 30, 3600):
        raise HTTPException(429, "Troppe richieste.")
    if len(p.results) > MAX_CHECK:
        raise HTTPException(413, "Troppe particelle.")
    keep = ("plot_id", "origine", "lat", "lon", "verdict", "confidence", "country_risk", "country_detected",
            "forest_ha_2020", "disturb_ha_post2020", "loss_in_forest2020_ha", "loss_by_year", "drivers_ha",
            "protected_ha", "indigenous_ha", "reasons", "issues", "geometry_type", "checked_on", "datasets")
    clean = [{k: r.get(k) for k in keep if k in r} for r in p.results if isinstance(r, dict)]
    uid = auth.read_session(authorization.split(" ", 1)[1]) if authorization.lower().startswith("bearer ") else None
    user = s.get(db.User, uid) if uid else None
    rep = db.Report(title=(p.title or "")[:200], lang=_lang(p.lang), results=clean, email=(p.email or "")[:320],
                    org_id=user.org_id if user else None)
    s.add(rep)
    s.commit()
    if p.email:
        try:
            save_lead(p.email, p.company, "report-pdf", "", "report %s" % rep.id)
        except HTTPException:
            pass
    return {"id": rep.id, "url": "%s/r.html?id=%s" % (SITE_URL, rep.id),
            "pdf": "/reports/%s/pdf" % rep.id}


def _get_report(s, rid):
    rep = s.get(db.Report, rid)
    if not rep:
        raise HTTPException(404, "Report non trovato.")
    return rep


@router.get("/reports/{rid}")
def report_get(rid: str, s: Session = Depends(db.get_db)):
    rep = _get_report(s, rid)
    return {"id": rep.id, "title": rep.title, "lang": rep.lang, "created_at": _iso(rep.created_at),
            "results": rep.results}


@router.get("/reports/{rid}/pdf")
def report_pdf(rid: str, s: Session = Depends(db.get_db)):
    rep = _get_report(s, rid)
    vt = VERDICT_TXT[_lang(rep.lang)]
    ct = CONF_TXT[_lang(rep.lang)]
    pdf = _pdf_doc(rep.title or "GroveProof EUDR screening",
                   "Report %s - created %s - %s/r.html?id=%s" % (rep.id, rep.created_at.strftime("%Y-%m-%d"),
                                                               SITE_URL, rep.id))
    _pdf_table(pdf, ["Plot", "Origin", "Lat", "Lng", "Result", "Conf.", "Forest 2020 ha", "Loss after 2020 ha"],
               [26, 24, 17, 17, 40, 15, 25, 26],
               [[r.get("plot_id"), r.get("origine"), r.get("lat"), r.get("lon"), vt.get(r.get("verdict"), r.get("verdict")),
                 ct.get(r.get("confidence"), r.get("confidence") or ""), r.get("forest_ha_2020") if r.get("forest_ha_2020") is not None else "",
                 r.get("disturb_ha_post2020") if r.get("disturb_ha_post2020") is not None else ""] for r in rep.results])
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "Reasons and warnings", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 8)
    for r in rep.results:
        lines = list(r.get("reasons") or []) + ["! " + i.get("msg", "") for i in (r.get("issues") or [])
                                                 if isinstance(i, dict) and i.get("level") == "avviso"]
        if lines:
            pdf.multi_cell(0, 4.5, _pdf_text("%s: %s" % (r.get("plot_id"), " | ".join(lines))))
    pdf.ln(3)
    pdf.set_font("Helvetica", "", 7.5)
    pdf.set_text_color(90, 90, 90)
    pdf.multi_cell(0, 4, _pdf_text(DISCLAIMER))
    return Response(bytes(pdf.output()), media_type="application/pdf",
                    headers={"Content-Disposition": "inline; filename=groveproof-%s.pdf" % rep.id})


# ======================= pagina pubblica, badge, QR =======================
def _public_org(s, slug):
    org = s.query(db.Org).filter(db.Org.slug == (slug or "").lower(), db.Org.public.is_(True)).one_or_none()
    if not org:
        raise HTTPException(404, "Pagina non trovata.")
    return org


def _public_stats(s, org):
    pl = s.query(db.Plot).filter(db.Plot.org_id == org.id, db.Plot.public.is_(True)).all()
    checked = [p for p in pl if p.verdict]
    ok = [p for p in checked if p.verdict in OK_VERDICTS]
    last = max([p.checked_at for p in checked if p.checked_at], default=None)
    return pl, checked, ok, last


@router.get("/public/{slug}")
def public_page(slug: str, s: Session = Depends(db.get_db)):
    org = _public_org(s, slug)
    pl, checked, ok, last = _public_stats(s, org)
    countries = sorted({p.country for p in pl if p.country})
    return {
        "name": org.name, "text": org.public_text, "website": org.website, "plan": org.plan, "lang": org.lang,
        "summary": {"plots": len(pl), "checked": len(checked), "deforestation_free": len(ok),
                    "at_risk": sum(1 for p in checked if p.verdict == "A_RISCHIO"), "countries": countries,
                    "last_check": _iso(last)},
        # privacy dei produttori: posizione arrotondata a ~1 km, nessun nome del produttore
        "plots": [{"ref": p.ref, "country": p.country, "verdict": p.verdict, "confidence": p.confidence,
                   "checked_at": _iso(p.checked_at), "lat": round(p.lat, 2) if p.lat is not None else None,
                   "lng": round(p.lng, 2) if p.lng is not None else None,
                   "area_ha": round(p.area_ha, 1) if p.area_ha else None} for p in pl],
        "methodology": SITE_URL + "/#method",
    }


def _esc(t):
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


@router.get("/badge/{slug}.svg")
def badge(slug: str, lang: str = "en", s: Session = Depends(db.get_db)):
    org = _public_org(s, slug)
    pl, checked, ok, last = _public_stats(s, org)
    lang = _lang(lang)
    head = {"en": "ORIGINS VERIFIED", "de": "HERKUNFT GEPRÜFT", "it": "ORIGINI VERIFICATE"}[lang]
    if checked and len(ok) == len(checked):
        line = {"en": "%d plots deforestation-free", "de": "%d Flurstücke entwaldungsfrei",
                "it": "%d particelle senza deforestazione"}[lang] % len(ok)
        color = "#2F6B47"
    else:
        line = {"en": "%d of %d plots verified", "de": "%d von %d Flurstücken geprüft",
                "it": "%d di %d particelle verificate"}[lang] % (len(ok), len(pl))
        color = "#8A6A1F"
    date = (_iso(last) or "")[:10]
    tag = {"en": "EUDR check for coffee", "de": "EUDR-Nachweis für Kaffee", "it": "verifica EUDR per il caffè"}[lang]
    svg = ("<svg xmlns='http://www.w3.org/2000/svg' width='320' height='64' viewBox='0 0 320 64' role='img' "
           "aria-label='{h}: {l}'><rect x='0.5' y='0.5' width='319' height='63' rx='10' fill='#FBF8F2' "
           "stroke='{c}'/><circle cx='30' cy='32' r='15' fill='{c}'/><path d='M23 32l5 5 10-11' stroke='#fff' "
           "stroke-width='3' fill='none' stroke-linecap='round' stroke-linejoin='round'/><text x='54' y='22' "
           "font-family='Arial,Helvetica,sans-serif' font-size='10' font-weight='700' fill='{c}' "
           "letter-spacing='.8'>{h}</text><text x='54' y='39' font-family='Arial,Helvetica,sans-serif' "
           "font-size='12.5' font-weight='700' fill='#1E1912'>{l}</text><text x='54' y='54' "
           "font-family='Arial,Helvetica,sans-serif' font-size='9.5' fill='#6B6155'><tspan font-weight='700'>GroveProof</tspan> · {t}{d}</text></svg>"
           ).format(h=_esc(head), l=_esc(line), c=color, d=_esc(" · " + date if date else ""), t=_esc(tag))
    return Response(svg, media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=3600"})


@router.get("/qr/{slug}.svg")
def qr(slug: str, s: Session = Depends(db.get_db)):
    import segno
    _public_org(s, slug)
    buf = io.BytesIO()
    segno.make("%s/o.html?s=%s" % (SITE_URL, slug.lower()), error="m").save(buf, kind="svg", scale=8, border=2,
                                                                             dark="#1E1912")
    return Response(buf.getvalue(), media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=86400"})


# ======================= admin =======================
def _admin(tok):
    if not ADMIN_TOKEN or tok != ADMIN_TOKEN:
        raise HTTPException(404, "Not Found")


class PlanReq(BaseModel):
    email: str
    plan: str


@router.post("/admin/plan")
def admin_plan(p: PlanReq, x_admin_token: str = Header(default=""), s: Session = Depends(db.get_db)):
    _admin(x_admin_token)
    if p.plan not in db.PLANS:
        raise HTTPException(400, "Piano: %s" % ", ".join(db.PLANS))
    u = s.query(db.User).filter(db.User.email == p.email.strip().lower()).one_or_none()
    if not u:
        raise HTTPException(404, "Utente non trovato.")
    org = s.get(db.Org, u.org_id)
    org.plan = p.plan
    s.commit()
    return {"ok": True, "org": org.id, "plan": org.plan}


@router.get("/admin/stats")
def admin_stats(x_admin_token: str = Header(default=""), s: Session = Depends(db.get_db)):
    _admin(x_admin_token)
    c = lambda m: s.query(func.count()).select_from(m).scalar()
    plans = dict(s.query(db.Org.plan, func.count()).group_by(db.Org.plan).all())
    return {"orgs": c(db.Org), "users": c(db.User), "plots": c(db.Plot), "checks": c(db.Check), "lots": c(db.Lot),
            "leads": c(db.Lead), "reports": c(db.Report), "plans": plans,
            "public_pages": s.query(func.count(db.Org.id)).filter(db.Org.public.is_(True)).scalar()}


# ======================= monitoraggio periodico (piani Pro e Business) =======================
# Chiamato da un job programmato (GitHub Actions) con X-Admin-Token. Riverifica le particelle
# scadute e manda un'email agli utenti dell'organizzazione se un esito cambia.
MONITOR_DAYS = {"mensile": 30, "settimanale": 7}
ALERT_TXT = {
    "en": ("GroveProof: %d plot(s) changed", "Your periodic satellite re-check found changes:", "Open your account"),
    "de": ("GroveProof: %d Flurstück(e) geändert", "Die regelmäßige Satellitenprüfung hat Änderungen gefunden:", "Konto öffnen"),
    "it": ("GroveProof: %d particella/e cambiata/e", "La riverifica satellitare periodica ha trovato cambiamenti:", "Apri il tuo account"),
}


def _due_plots(s, org, limit):
    every = MONITOR_DAYS.get((db.PLANS.get(org.plan) or {}).get("monitoring"))
    if not every:
        return []
    cutoff = db.now() - timedelta(days=every)
    return (s.query(db.Plot).filter(db.Plot.org_id == org.id)
            .filter((db.Plot.checked_at.is_(None)) | (db.Plot.checked_at < cutoff))
            .order_by(db.Plot.checked_at).limit(limit).all())


@router.post("/admin/monitor")
def admin_monitor(x_admin_token: str = Header(default=""), s: Session = Depends(db.get_db)):
    _admin(x_admin_token)
    budget, summary = MAX_CHECK, []
    for org in s.query(db.Org).filter(db.Org.plan.in_(["pro", "business"])).all():
        if budget <= 0:
            break
        due = _due_plots(s, org, budget)
        if not due:
            continue
        budget -= len(due)
        lang = _lang(org.lang)
        prev = {p.id: p.verdict for p in due}
        with ThreadPoolExecutor(max_workers=6) as ex:
            results = list(ex.map(lambda p: _check_plot(p, lang), due))
        changed = []
        for p, r in results:
            if r.get("error"):          # errore temporaneo dei dati: non cambia l'esito salvato
                continue
            p.verdict, p.confidence, p.checked_at = r.get("verdict"), r.get("confidence"), db.now()
            s.add(db.Check(plot_id=p.id, verdict=p.verdict, confidence=p.confidence, result=r))
            if prev[p.id] and prev[p.id] != p.verdict:
                changed.append((p, prev[p.id], p.verdict))
        s.commit()
        mailed = 0
        if changed:
            vt, subj = VERDICT_TXT[lang], ALERT_TXT[lang]
            lines = ["- %s (%s): %s -> %s" % (p.ref, p.country or "", vt.get(a, a), vt.get(b, b)) for p, a, b in changed]
            app_url = os.getenv("APP_URL", SITE_URL + "/app.html")
            body = "%s\n\n%s\n\n%s: %s\n" % (subj[1], "\n".join(lines), subj[2], app_url)
            for u in s.query(db.User).filter(db.User.org_id == org.id).all():
                try:
                    if auth.send_email(u.email, subj[0] % len(changed), body):
                        mailed += 1
                except Exception as e:
                    print("[monitor] email non inviata a %s: %s" % (u.email, e), flush=True)
        summary.append({"org": org.id, "checked": len(due), "changed": len(changed), "emails": mailed})
    pending = sum(len(_due_plots(s, o, MAX_CHECK)) for o in s.query(db.Org).filter(db.Org.plan.in_(["pro", "business"])))
    return {"orgs": summary, "pending": pending}
