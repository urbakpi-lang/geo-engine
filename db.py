"""
geo-engine · db.py — database di GroveProof (account, registro EUDR, verifiche, contatti).

DATABASE_URL:
  - non impostata  -> SQLite locale (solo per prove: su Render free il disco si azzera a ogni riavvio)
  - postgresql://… -> Postgres (Supabase, Neon, Render Postgres…) per la produzione
Le tabelle si creano da sole all'avvio (create_all). Nessuna migrazione manuale per ora.
"""
import os
import secrets
import string
from datetime import datetime, timezone

from sqlalchemy import (JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text,
                        UniqueConstraint, create_engine, event)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "").strip() or "sqlite:///./groveproof.db"
if DATABASE_URL.startswith("postgres://"):            # alcuni provider usano ancora il vecchio prefisso
    DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]
if DATABASE_URL.startswith("postgresql://") and "+psycopg" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

_kw = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    _kw["connect_args"] = {"check_same_thread": False}
engine = create_engine(DATABASE_URL, **_kw)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")


def now():
    return datetime.now(timezone.utc)


def new_id(n=12):
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(n))


class Base(DeclarativeBase):
    pass


# ---------------- account ----------------
PLANS = {
    # piano: (particelle massime, utenti, verifica periodica, badge personalizzato, report PDF)
    "free": {"plots": 25, "users": 1, "monitoring": None, "custom_badge": False, "pdf": True, "api": False},
    "pro": {"plots": 500, "users": 3, "monitoring": "mensile", "custom_badge": True, "pdf": True, "api": False},
    "business": {"plots": 5000, "users": 10, "monitoring": "settimanale", "custom_badge": True, "pdf": True,
                 "api": True},
}


class Org(Base):
    __tablename__ = "orgs"
    id: Mapped[str] = mapped_column(String(16), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), default="")
    kind: Mapped[str] = mapped_column(String(30), default="roaster")        # roaster | importer | exporter
    country: Mapped[str] = mapped_column(String(3), default="")
    plan: Mapped[str] = mapped_column(String(20), default="free")
    slug: Mapped[str | None] = mapped_column(String(80), unique=True, nullable=True)  # pagina pubblica
    public: Mapped[bool] = mapped_column(Boolean, default=False)
    public_text: Mapped[str] = mapped_column(Text, default="")
    website: Mapped[str] = mapped_column(String(300), default="")
    share_plots: Mapped[bool] = mapped_column(Boolean, default=False)       # archivio condiviso (consenso)
    lang: Mapped[str] = mapped_column(String(2), default="en")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    users = relationship("User", back_populates="org")


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(16), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    org_id: Mapped[str] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(20), default="owner")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    org = relationship("Org", back_populates="users")


class LoginToken(Base):
    """Link magico: si salva solo l'impronta (hash) del token, mai il token in chiaro."""
    __tablename__ = "login_tokens"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used: Mapped[bool] = mapped_column(Boolean, default=False)


# ---------------- registro EUDR ----------------
class Supplier(Base):
    __tablename__ = "suppliers"
    id: Mapped[str] = mapped_column(String(16), primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(30), default="importer")   # importer | exporter | cooperative | farm | customer
    country: Mapped[str] = mapped_column(String(80), default="")
    address: Mapped[str] = mapped_column(String(400), default="")
    email: Mapped[str] = mapped_column(String(320), default="")
    eori: Mapped[str] = mapped_column(String(40), default="")           # numero EORI/registrazione, se c'è
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Lot(Base):
    """Un acquisto (o una vendita) registrato: è la riga del registro da conservare 5 anni."""
    __tablename__ = "lots"
    id: Mapped[str] = mapped_column(String(16), primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"), index=True)
    supplier_id: Mapped[str | None] = mapped_column(ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True)
    direction: Mapped[str] = mapped_column(String(10), default="in")   # in = acquisto, out = vendita
    code: Mapped[str] = mapped_column(String(80), default="")          # codice lotto / contratto
    product: Mapped[str] = mapped_column(String(200), default="")      # es. "Caffè verde Huila washed"
    origin_country: Mapped[str] = mapped_column(String(80), default="")
    quantity_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    hs_code: Mapped[str] = mapped_column(String(12), default="0901")
    dds_reference: Mapped[str] = mapped_column(String(80), default="")  # numero di riferimento DDS
    dds_verification: Mapped[str] = mapped_column(String(80), default="")  # numero di verifica DDS
    date: Mapped[str] = mapped_column(String(10), default="")          # AAAA-MM-GG
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Plot(Base):
    __tablename__ = "plots"
    id: Mapped[str] = mapped_column(String(16), primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"), index=True)
    supplier_id: Mapped[str | None] = mapped_column(ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True)
    lot_id: Mapped[str | None] = mapped_column(ForeignKey("lots.id", ondelete="SET NULL"), nullable=True)
    ref: Mapped[str] = mapped_column(String(80))                       # id della particella (del fornitore)
    country: Mapped[str] = mapped_column(String(80), default="")
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    area_ha: Mapped[float | None] = mapped_column(Float, nullable=True)
    geometry: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    producer: Mapped[str] = mapped_column(String(200), default="")
    public: Mapped[bool] = mapped_column(Boolean, default=True)        # mostrata nella pagina pubblica
    verdict: Mapped[str | None] = mapped_column(String(30), nullable=True)
    confidence: Mapped[str | None] = mapped_column(String(10), nullable=True)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("org_id", "ref", name="uq_plot_ref"),)


class Check(Base):
    """Storico delle verifiche: ogni verifica resta salvata (prova per l'ispezione)."""
    __tablename__ = "checks"
    id: Mapped[str] = mapped_column(String(16), primary_key=True, default=new_id)
    plot_id: Mapped[str] = mapped_column(ForeignKey("plots.id", ondelete="CASCADE"), index=True)
    verdict: Mapped[str] = mapped_column(String(30))
    confidence: Mapped[str | None] = mapped_column(String(10), nullable=True)
    result: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


# ---------------- crescita ----------------
class Lead(Base):
    __tablename__ = "leads"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(320), index=True)
    company: Mapped[str] = mapped_column(String(200), default="")
    source: Mapped[str] = mapped_column(String(60), default="")       # groveproof-form, report-pdf, importers…
    kind: Mapped[str] = mapped_column(String(30), default="")         # roaster | importer | exporter | sponsor
    message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Report(Base):
    """Risultato di un controllo (anche gratuito) salvato con un link condivisibile."""
    __tablename__ = "reports"
    id: Mapped[str] = mapped_column(String(16), primary_key=True, default=lambda: new_id(14))
    org_id: Mapped[str | None] = mapped_column(ForeignKey("orgs.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(200), default="")
    lang: Mapped[str] = mapped_column(String(2), default="en")
    results: Mapped[list] = mapped_column(JSON)
    email: Mapped[str] = mapped_column(String(320), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


def init_db():
    Base.metadata.create_all(engine)


def get_db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()
