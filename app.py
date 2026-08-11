import csv
import io
import json
import os
import re
import secrets
import shutil
import socket
import sqlite3
import unicodedata
import zipfile

import qrcode
from contextlib import closing
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo
from functools import wraps
from pathlib import Path
from xml.etree import ElementTree as ET

from flask import (
    Flask,
    Response,
    abort,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix

from database import (
    DB_INTEGRITY_ERRORS,
    connect_database,
    is_postgres_url,
)

from stock_xlsx import build_stock_workbook, build_stock_template_workbook
from lists_xlsx import build_lists_workbook
from stock_logic import calculate_event_yield
from stock_import_parser import parse_stock_file, normalize as normalize_stock_text
from lists_pdf import build_lists_pdf
from access_rules import (
    BIRTHDAY_DISCOUNT_CUTOFF_LABEL,
    FREE_ENTRY_CUTOFF_LABEL,
    birthday_discount_available,
    free_entry_available,
)

from master_list_parser import (
    COMMON_LIST_LABEL,
    PROMO_LIST_LABEL,
    docx_text_lines,
    normalize_promoter_name,
    normalize_text_key,
    parse_master_file,
    parse_master_lines,
)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
BACKUP_DIR = BASE_DIR / "backups"
DATABASE = DATA_DIR / "floki.db"
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
APP_VERSION = "2.9.4"
ARGENTINA_TZ = ZoneInfo("America/Argentina/Buenos_Aires")

PAYMENT_METHODS = {"cash", "mercadopago", "transfer", "debit", "credit", "other"}
# Las categorías advance/vip se conservan únicamente para leer eventos históricos.
SALE_CATEGORIES = {"general", "drink", "drink_special", "rrpp_benefit", "birthday_benefit", "birthday_discount", "cloakroom", "other"}
ENTRY_CATEGORIES = {"general", "free"}
HISTORICAL_ENTRY_CATEGORIES = {"general", "advance", "vip", "free"}
PRICE_STEP = 1000
BEVERAGE_PRICE_STEP = 500
BIRTHDAY_MAX_FRIENDS = 9
BIRTHDAY_MAX_PEOPLE = 10
BIRTHDAY_GIFT_MIN_CHECKINS = 5
PRICE_OPTIONS = tuple(range(0, 301000, PRICE_STEP))
BEVERAGE_PRICE_OPTIONS = tuple(range(0, 301000, BEVERAGE_PRICE_STEP))
ALLOWED_LIST_EXTENSIONS = {".csv", ".txt", ".xlsx", ".docx"}
CASHIER_SECTORS = {"ticketing", "beverages"}
SECTOR_LABELS = {"ticketing": "Caja de boletería", "beverages": "Caja de bebidas", "all": "Administración"}

# Categorías visibles del sector Bebidas. Las variantes existentes se agrupan
# automáticamente sin perder su marca, nombre ni historial.
BEVERAGE_CATEGORY_OPTIONS = (
    "CERVEZAS", "FERNET", "VODKA", "WHISKY", "TRAGOS", "GASEOSAS", "SHOTS", "CHAMPAGNE",
)
BEVERAGE_TYPE_OPTIONS = (
    "Cerveza", "Fernet", "Vodka", "Gin", "Whisky", "Ron", "Gancia",
    "Tequila", "Aperitivo", "Licor", "Vino", "Espumante", "Energizante",
    "Agua", "Gaseosa", "Trago preparado", "Otro",
)
BEVERAGE_BRAND_OPTIONS = (
    "Sin marca", "Quilmes", "Brahma", "Andes Origen", "Schneider", "Imperial",
    "Heineken", "Stella Artois", "Corona", "Budweiser", "Patagonia", "Miller",
    "Branca", "1882", "Vittone", "Smirnoff", "Absolut", "Skyy", "Sernova",
    "Gordon's", "Bombay Sapphire", "Beefeater", "Tanqueray", "Heráclito", "Bosque",
    "Johnnie Walker", "Chivas Regal", "Jack Daniel's", "Jameson", "Ballantine's",
    "Bacardí", "Havana Club", "Gancia", "Speed", "Red Bull", "Monster",
    "Coca-Cola", "Sprite", "Fanta", "Schweppes", "Pepsi", "7Up",
    "Villavicencio", "Eco de los Andes", "Kin", "Chandon", "Norton", "Zuccardi",
)
BEVERAGE_PRESENTATION_OPTIONS = (
    "vaso", "vaso chico", "vaso grande 750 ml", "lata", "lata 250 ml", "lata 354 ml",
    "lata 473 ml", "botella", "botella 330 ml", "botella 500 ml", "botella 710 ml",
    "botella 750 ml", "botella 1 l", "copa", "shot", "jarra", "balde", "unidad",
)
BEVERAGE_STOCK_UNIT_OPTIONS = ("botella", "lata", "caja", "pack", "barril", "bidón", "unidad")
APPROX_YIELD_OPTIONS = tuple([0.0] + [step / 2 for step in range(2, 41)])  # 1 a 20 por unidad de stock

EVENT_IMAGE_MAX_BYTES = 6 * 1024 * 1024
EVENT_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
EVENT_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}

PAYMENT_LABELS = {
    "cash": "Efectivo",
    "mercadopago": "Mercado Pago",
    "transfer": "Transferencia",
    "debit": "Débito",
    "credit": "Crédito",
    "other": "Otro",
}
CATEGORY_LABELS = {
    "general": "Entrada general",
    "advance": "Anticipada",
    "vip": "VIP",
    "drink": "Consumición",
    "drink_special": "Bebida especial",
    "rrpp_benefit": "BENEFICIO RRPP",
    "birthday_benefit": "BENEFICIO CUMPLEAÑOS",
    "birthday_discount": "50% OFF CUMPLEAÑOS",
    "champagne_speed": "SPEED INCLUIDO CON CHAMPAGNE",
    "free": "Entrada FREE",
    "cloakroom": "Guardarropa",
    "other": "Otro",
    "expense": "Gasto",
}

app = Flask(__name__)
IS_CLOUD = is_postgres_url(DATABASE_URL) or os.getenv("FLOKI_ENV", "").lower() == "production"
SECRET_KEY_VALUE = os.getenv("FLOKI_SECRET_KEY", "").strip()
if IS_CLOUD and len(SECRET_KEY_VALUE) < 32:
    raise RuntimeError("En producción debés configurar FLOKI_SECRET_KEY con al menos 32 caracteres")
if not SECRET_KEY_VALUE:
    SECRET_KEY_VALUE = "cambiar-esta-clave-solo-para-pruebas-locales"
app.config.update(
    SECRET_KEY=SECRET_KEY_VALUE,
    DATABASE=str(DATABASE),
    DATABASE_URL=DATABASE_URL,
    MAX_CONTENT_LENGTH=8 * 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=IS_CLOUD or os.getenv("FLOKI_SECURE_COOKIES") == "1",
    PERMANENT_SESSION_LIFETIME=60 * 60 * 12,
    PREFERRED_URL_SCHEME="https" if IS_CLOUD else "http",
)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

DATA_DIR.mkdir(exist_ok=True)
BACKUP_DIR.mkdir(exist_ok=True)


def get_db():
    if "db" not in g:
        g.db = connect_database(app.config.get("DATABASE_URL"), app.config["DATABASE"])
    return g.db


@app.teardown_appcontext
def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers["X-Floki-Version"] = APP_VERSION
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    offline_shell = request.path in {"/offline", "/offline-operations", "/service-worker.js", "/manifest.webmanifest"} or request.path.startswith("/static/")
    # HTML dinámico, login y datos privados nunca deben persistirse en la caché de la PWA.
    if not offline_shell and (response.mimetype == "text/html" or session.get("user_id") or request.path.startswith(("/api/", "/history", "/stock", "/promoter", "/login", "/logout"))):
        response.headers["Cache-Control"] = "no-store, private, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


def argentina_now():
    """Hora oficial usada por Floki, independiente de la zona horaria de Railway."""
    return datetime.now(ARGENTINA_TZ).replace(tzinfo=None, microsecond=0)


def now_iso():
    return argentina_now().isoformat(sep=" ")


def public_base_url():
    configured = os.getenv("FLOKI_PUBLIC_URL", "").strip().rstrip("/")
    if configured:
        return configured
    hostname = request.host.split(":", 1)[0].strip("[]").lower()
    if hostname not in {"127.0.0.1", "localhost", "0.0.0.0"}:
        return request.url_root.rstrip("/")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        local_ip = sock.getsockname()[0]
    except OSError:
        local_ip = "127.0.0.1"
    finally:
        sock.close()
    port = request.host.rsplit(":", 1)[1] if ":" in request.host else "5000"
    return f"http://{local_ip}:{port}"


def promoter_public_url(token):
    return public_base_url() + url_for("promoter_qr_landing", token=token)


def money_to_float(value):
    if value is None:
        raise ValueError("Monto faltante")
    text = str(value).strip().replace("$", "").replace(" ", "")
    if not text:
        raise ValueError("Monto faltante")

    # Acepta 8.000, 8000,50, 8.000,50 y el decimal con punto del navegador.
    if "," in text and "." in text:
        normalized = text.replace(".", "").replace(",", ".") if text.rfind(",") > text.rfind(".") else text.replace(",", "")
    elif "," in text:
        normalized = text.replace(".", "").replace(",", ".")
    elif "." in text:
        right = text.rsplit(".", 1)[1]
        normalized = text.replace(".", "") if len(right) == 3 else text
    else:
        normalized = text

    try:
        amount = float(normalized)
    except ValueError as exc:
        raise ValueError("Ingresá un monto válido") from exc
    if amount < 0:
        raise ValueError("El monto no puede ser negativo")
    return round(amount, 2)


def positive_int(value, label, maximum=100000, allow_zero=False):
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} inválida") from exc
    minimum = 0 if allow_zero else 1
    if number < minimum or number > maximum:
        raise ValueError(f"{label} debe estar entre {minimum} y {maximum}")
    return number


def non_negative_number(value, label, maximum=100000, allow_zero=True):
    raw = str(value or "").strip().replace(" ", "")
    if not raw:
        raise ValueError(f"{label} inválida")
    if "," in raw and "." in raw:
        normalized = raw.replace(".", "").replace(",", ".") if raw.rfind(",") > raw.rfind(".") else raw.replace(",", "")
    else:
        normalized = raw.replace(",", ".")
    try:
        number = float(normalized)
    except ValueError as exc:
        raise ValueError(f"{label} inválida") from exc
    minimum = 0 if allow_zero else 0.01
    if number < minimum or number > maximum:
        raise ValueError(f"{label} debe estar entre {minimum} y {maximum}")
    return round(number, 3)


def price_from_option(value, allow_zero=True):
    amount = money_to_float(value)
    if not allow_zero and amount <= 0:
        raise ValueError("Seleccioná un precio mayor a cero")
    if amount % PRICE_STEP != 0 or amount not in PRICE_OPTIONS:
        raise ValueError(f"El precio debe ser una opción en múltiplos de $ {PRICE_STEP:,}".replace(",", "."))
    return amount


def beverage_price_from_option(value, allow_zero=True):
    amount = money_to_float(value)
    if not allow_zero and amount <= 0:
        raise ValueError("Seleccioná un precio de bebida mayor a cero")
    if amount % BEVERAGE_PRICE_STEP != 0 or amount not in BEVERAGE_PRICE_OPTIONS:
        raise ValueError(f"El precio de la bebida debe ir de $ {BEVERAGE_PRICE_STEP:,} en $ {BEVERAGE_PRICE_STEP:,}".replace(",", "."))
    return amount


def beverage_stock_consumption(product, quantity):
    # quantity siempre representa lo que se entregó al cliente: 1 Fernet = 1 vaso,
    # 1 cerveza en lata = 1 lata. El stock físico se expresa aparte (botella/lata/etc.).
    approx_yield = float(product["approx_yield"] or 0)
    if approx_yield <= 0:
        approx_yield = suggested_approx_yield(
            product["stock_unit"], product["sale_unit"],
            product["beverage_type"], product["brand"], product["name"],
        )
    if approx_yield <= 0:
        return 0.0
    return round(float(quantity) / approx_yield, 4)


def beverage_option(value, allowed, label):
    cleaned = re.sub(r"\s+", " ", str(value or "").strip()).casefold()
    lookup = {item.casefold(): item for item in allowed}
    if cleaned not in lookup:
        raise ValueError(f"Seleccioná una opción válida para {label}")
    return lookup[cleaned]


def build_beverage_name(beverage_type, brand, presentation):
    base = beverage_type if brand == "Sin marca" else f"{beverage_type} {brand}"
    return f"{base} · {presentation.title()}"[:80]


def infer_beverage_category(beverage_type=None, brand=None, sale_unit=None, name=None):
    text = " ".join(str(value or "") for value in (beverage_type, brand, sale_unit, name)).casefold()
    sale = str(sale_unit or "").casefold()
    if "cerve" in text or any(token in text for token in ("quilmes", "brahma", "heineken", "stella", "corona", "budweiser", "patagonia", "miller", "imperial", "schneider")):
        return "CERVEZAS"
    # La presentación SHOT manda sobre la familia de alcohol: un shot de vodka va a SHOTS.
    if sale == "shot" or " shot" in f" {text}" or any(token in text for token in ("tequila", "shot")):
        return "SHOTS"
    if "fernet" in text or any(token in text for token in ("branca", "1882", "vittone")):
        return "FERNET"
    if "vodka" in text or any(token in text for token in ("smirnoff", "absolut", "skyy", "sernova")):
        return "VODKA"
    if "whisky" in text or "whiskey" in text or any(token in text for token in ("johnnie", "chivas", "jack daniel", "jameson", "ballantine")):
        return "WHISKY"
    if any(token in text for token in ("champagne", "espumante", "chandon")):
        return "CHAMPAGNE"
    if any(token in text for token in ("gaseosa", "energizante", "agua", "coca-cola", "sprite", "fanta", "schweppes", "pepsi", "7up", "speed", "red bull", "monster", "villavicencio", "eco de los andes", "kin")):
        return "GASEOSAS"
    return "TRAGOS"


def group_beverages(rows, *, product_ranking=None, category_ranking=None, sold_counts=None):
    """Agrupa bebidas y permite priorizar lo más vendido del evento anterior."""
    product_ranking = product_ranking or {}
    category_ranking = category_ranking or {}
    sold_counts = sold_counts or {}
    grouped = {label: [] for label in BEVERAGE_CATEGORY_OPTIONS}
    for row in rows:
        item = dict(row)
        label = infer_beverage_category(item.get("beverage_type"), item.get("brand"), item.get("sale_unit"), item.get("name"))
        item["sold_count"] = int(sold_counts.get(item.get("id"), 0) or 0)
        item["previous_sold_count"] = int(product_ranking.get(item.get("id"), 0) or 0)
        grouped[label].append(item)
    for label in grouped:
        grouped[label].sort(key=lambda row: (-int(row.get("previous_sold_count", 0)), str(row.get("name") or "").casefold()))
    category_order = {label: index for index, label in enumerate(BEVERAGE_CATEGORY_OPTIONS)}
    labels = [label for label in BEVERAGE_CATEGORY_OPTIONS if grouped[label]]
    labels.sort(key=lambda label: (-int(category_ranking.get(label, 0)), category_order[label]))
    return [{"label": label, "items": grouped[label], "previous_sold_count": int(category_ranking.get(label, 0) or 0)} for label in labels]


def beverage_paid_sales_by_product(cash_session_id):
    """Unidades pagas por producto; beneficios $0 no alteran el ranking."""
    rows = get_db().execute(
        """SELECT beverage_product_id, COALESCE(SUM(quantity), 0) AS sold
           FROM movements
           WHERE cash_session_id=? AND movement_type='sale' AND sector='beverages'
             AND voided=0 AND beverage_product_id IS NOT NULL AND total>0
             AND category NOT IN ('rrpp_benefit','birthday_benefit','champagne_speed')
           GROUP BY beverage_product_id""",
        (cash_session_id,),
    ).fetchall()
    return {int(row["beverage_product_id"]): int(row["sold"] or 0) for row in rows}


def previous_event_beverage_ranking(current_cash_session_id):
    previous = get_db().execute(
        """SELECT id FROM cash_sessions
           WHERE id<>? AND status='closed'
           ORDER BY event_date DESC, id DESC LIMIT 1""",
        (current_cash_session_id,),
    ).fetchone()
    if not previous:
        return {}, {}
    product_sales = beverage_paid_sales_by_product(previous["id"])
    if not product_sales:
        return {}, {}
    placeholders = ",".join("?" for _ in product_sales)
    products = get_db().execute(
        f"SELECT id, beverage_type, brand, sale_unit, name FROM beverage_products WHERE id IN ({placeholders})",
        tuple(product_sales.keys()),
    ).fetchall()
    category_sales = {}
    for product in products:
        label = infer_beverage_category(product["beverage_type"], product["brand"], product["sale_unit"], product["name"])
        category_sales[label] = category_sales.get(label, 0) + product_sales.get(int(product["id"]), 0)
    return product_sales, category_sales


def suggested_approx_yield(stock_unit, sale_unit, beverage_type=None, brand=None, name=None):
    """Rendimiento operativo automático por presentación; el real se calcula al cierre."""
    stock_key = str(stock_unit or "").casefold()
    sale_key = str(sale_unit or "").casefold()
    category = infer_beverage_category(beverage_type, brand, sale_unit, name)

    # Venta física 1 a 1: una lata vendida descuenta una lata; una botella, una botella.
    if stock_key in {"lata", "botella", "unidad"} and (sale_key.startswith(stock_key) or sale_key == "unidad"):
        return 1.0
    if stock_key in {"caja", "pack", "barril", "bidón"}:
        return 0.0

    if stock_key == "botella":
        if sale_key == "shot" or category == "SHOTS":
            return 20.0
        if sale_key == "copa":
            return 6.0
        if sale_key == "vaso chico":
            return 12.0
        if sale_key in {"vaso", "vaso grande 750 ml"}:
            # En tragos mezclados la botella de destilado no equivale al vaso completo.
            return 8.0
        if sale_key in {"jarra", "balde"}:
            return 4.0
    return 1.0 if stock_key == "unidad" else 0.0


def is_champagne_product(product):
    if not product:
        return False
    return infer_beverage_category(
        product["beverage_type"], product["brand"], product["sale_unit"], product["name"]
    ) == "CHAMPAGNE"


def find_speed_product(db):
    """Devuelve la variante activa de Speed usada como acompañamiento de Champagne."""
    return db.execute(
        """SELECT * FROM beverage_products
           WHERE active=1 AND (lower(brand)='speed' OR lower(name) LIKE '%speed%')
           ORDER BY
             CASE WHEN lower(stock_unit)='lata' THEN 0 ELSE 1 END,
             CASE WHEN lower(sale_unit) LIKE 'lata%' THEN 0 ELSE 1 END,
             sort_order, id
           LIMIT 1"""
    ).fetchone()


def add_champagne_speed_stock(db, cash, user, parent_movement_id, champagne_product, champagne_quantity, *, promoter_id=None, created_at=None):
    """Descuenta los 2 Speed incluidos sin poner en riesgo la venta principal.

    v2.9.3 endurece este punto para PostgreSQL/Railway. Primero intenta guardar el
    componente en ``beverage_stock_adjustments``. Si esa escritura falla por una
    diferencia de esquema o una incidencia puntual de PostgreSQL, revierte SOLO ese
    componente mediante SAVEPOINT y usa el formato histórico ``champagne_speed`` en
    ``movements``. Ese movimiento vale $0, queda vinculado a la venta principal y ya
    está excluido de tickets, recaudación y ranking de bebidas pagas.

    De esta forma: 1 Champagne = 1 ticket y 1 venta paga, pero el stock sigue
    descontando 2 Speed. Una falla secundaria de stock nunca vuelve a borrar el cobro
    del Champagne.
    """
    if not is_champagne_product(champagne_product):
        return "not_champagne"
    speed = find_speed_product(db)
    if not speed:
        return "missing_speed"
    speed_quantity = int(champagne_quantity) * 2
    if speed_quantity <= 0:
        return "no_quantity"

    stock_units = beverage_stock_consumption(speed, speed_quantity)
    stamp = created_at or now_iso()
    savepoint = "floki_champagne_speed_component"

    # Ruta preferida: tabla dedicada de ajustes de stock.
    try:
        db.execute(f"SAVEPOINT {savepoint}")
        ensure_beverage_in_event_stock(db, cash["id"], speed, user["id"])
        cursor = db.execute(
            """INSERT OR IGNORE INTO beverage_stock_adjustments(
                   cash_session_id, parent_movement_id, beverage_product_id, reason,
                   quantity, stock_units, created_at, created_by, voided
               ) VALUES (?, ?, ?, 'champagne_speed', ?, ?, ?, ?, 0)""",
            (
                cash["id"], parent_movement_id, speed["id"], speed_quantity,
                stock_units, stamp, user["id"],
            ),
        )
        db.execute(f"RELEASE SAVEPOINT {savepoint}")
        return "adjustment" if cursor.lastrowid else "adjustment_existing"
    except Exception:
        app.logger.exception(
            "No se pudo guardar el ajuste dedicado Champagne + Speed; se usará el fallback compatible"
        )
        try:
            db.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
            db.execute(f"RELEASE SAVEPOINT {savepoint}")
        except Exception:
            app.logger.exception("No se pudo cerrar el savepoint del ajuste Champagne + Speed")

    # Fallback compatible con bases históricas. No cuenta como ticket ni ingreso.
    fallback_savepoint = "floki_champagne_speed_fallback"
    try:
        db.execute(f"SAVEPOINT {fallback_savepoint}")
        db.execute(
            """INSERT INTO movements(
                   cash_session_id, movement_type, category, sector, description,
                   quantity, unit_price, total, payment_method, created_at, created_by,
                   promoter_id, beverage_product_id, stock_units, linked_movement_id
               ) VALUES (?, 'sale', 'champagne_speed', 'beverages', ?, ?, 0, 0, 'other', ?, ?, ?, ?, ?, ?)""",
            (
                cash["id"],
                f"Speed incluido con Champagne · combo #{parent_movement_id}",
                speed_quantity, stamp, user["id"], promoter_id, speed["id"],
                stock_units, parent_movement_id,
            ),
        )
        db.execute(f"RELEASE SAVEPOINT {fallback_savepoint}")
        return "legacy_movement"
    except Exception:
        app.logger.exception(
            "También falló el fallback de stock Champagne + Speed; se conserva la venta principal"
        )
        try:
            db.execute(f"ROLLBACK TO SAVEPOINT {fallback_savepoint}")
            db.execute(f"RELEASE SAVEPOINT {fallback_savepoint}")
        except Exception:
            app.logger.exception("No se pudo cerrar el savepoint fallback Champagne + Speed")
        return "stock_warning"


def normalize_guest_name(value):
    text = re.sub(r"^\s*\d+\s*[.\-)]+\s*", "", str(value or "").strip())
    text = re.sub(r"\s+", " ", text)
    folded = unicodedata.normalize("NFKD", text)
    folded = "".join(char for char in folded if not unicodedata.combining(char))
    normalized = re.sub(r"[^a-z0-9 ]+", "", folded.casefold())
    return text[:120], re.sub(r"\s+", " ", normalized).strip()[:140]


def require_full_name(value, label="El nombre completo"):
    display, normalized = normalize_guest_name(value)
    parts = [part for part in display.split(" ") if len(part.strip(".-'")) >= 2]
    if len(parts) < 2:
        raise ValueError(f"{label} debe incluir nombre y apellido")
    return display, normalized


def parse_birthday_guest_names(raw_text):
    guests = []
    seen = set()
    for raw_line in str(raw_text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        display, normalized = require_full_name(line, "Cada integrante")
        if normalized in seen:
            continue
        seen.add(normalized)
        guests.append((display, normalized))
    if len(guests) > 9:
        raise ValueError("El cumpleaños permite como máximo 9 amigos además del cumpleañero")
    return guests


def decode_text_file(raw):
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("No se pudo leer la codificación del archivo")


def xlsx_first_values(raw):
    names = []
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            shared = []
            if "xl/sharedStrings.xml" in archive.namelist():
                root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
                namespace = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
                for item in root.findall("m:si", namespace):
                    shared.append("".join(node.text or "" for node in item.findall(".//m:t", namespace)))
            workbook = ET.fromstring(archive.read("xl/workbook.xml"))
            rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
            rel_map = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}
            ns = {
                "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
                "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
            }
            sheet = workbook.find("m:sheets/m:sheet", ns)
            if sheet is None:
                return []
            target = rel_map[sheet.attrib[f"{{{ns['r']}}}id"]]
            clean_target = target.lstrip("/")
            sheet_path = clean_target if clean_target.startswith("xl/") else "xl/" + clean_target
            root = ET.fromstring(archive.read(sheet_path))
            for row in root.findall(".//m:sheetData/m:row", ns):
                row_values = []
                for cell in row.findall("m:c", ns):
                    cell_type = cell.attrib.get("t")
                    value_node = cell.find("m:v", ns)
                    inline_node = cell.find("m:is/m:t", ns)
                    value = ""
                    if inline_node is not None:
                        value = inline_node.text or ""
                    elif value_node is not None:
                        value = value_node.text or ""
                        if cell_type == "s" and value.isdigit():
                            index = int(value)
                            value = shared[index] if index < len(shared) else ""
                    if str(value).strip():
                        row_values.append(str(value))
                if row_values:
                    names.append(row_values[0])
    except (KeyError, zipfile.BadZipFile, ET.ParseError) as exc:
        raise ValueError("El archivo XLSX no es válido o está dañado") from exc
    return names


def parse_guest_file(file_storage):
    filename = Path(file_storage.filename or "").name
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_LIST_EXTENSIONS:
        raise ValueError("Usá un archivo CSV, TXT, XLSX o DOCX")
    raw = file_storage.read()
    if not raw:
        raise ValueError("El archivo está vacío")
    if extension == ".xlsx":
        candidates = xlsx_first_values(raw)
    elif extension == ".docx":
        candidates = docx_text_lines(raw)
    else:
        text = decode_text_file(raw)
        if extension == ".txt":
            candidates = [line for line in text.splitlines()]
        else:
            sample = text[:4096]
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=";,\t|")
            except csv.Error:
                dialect = csv.excel
                dialect.delimiter = ";"
            candidates = []
            for row in csv.reader(io.StringIO(text), dialect):
                first = next((cell for cell in row if str(cell).strip()), "")
                if first:
                    candidates.append(first)

    header_words = {"nombre", "nombres", "persona", "personas", "invitado", "invitados", "lista", "guest", "guests"}
    parsed = []
    for candidate in candidates:
        display, normalized = normalize_guest_name(candidate)
        if not normalized or normalized in header_words or len(normalized) < 2:
            continue
        parsed.append((display, normalized))
    if not parsed:
        raise ValueError("No se encontraron nombres válidos en el archivo")
    return filename[:180], parsed


def table_columns(db, table_name):
    if db.is_postgres:
        rows = db.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=?",
            (table_name,),
        ).fetchall()
        return {row[0] for row in rows}
    return {row[1] for row in db.execute(f"PRAGMA table_info({table_name})").fetchall()}


def add_column_if_missing(db, table_name, column_name, definition):
    if column_name not in table_columns(db, table_name):
        db.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")


def new_qr_token():
    return secrets.token_urlsafe(24)


def validate_event_image(file_storage):
    """Valida y devuelve una imagen de evento segura para SQLite/PostgreSQL."""
    if not file_storage or not getattr(file_storage, "filename", ""):
        return None, None, None
    filename = Path(file_storage.filename).name[:180]
    extension = Path(filename).suffix.lower()
    if extension not in EVENT_IMAGE_EXTENSIONS:
        raise ValueError("La imagen del evento debe ser JPG, PNG o WEBP")
    data = file_storage.read(EVENT_IMAGE_MAX_BYTES + 1)
    if not data:
        raise ValueError("La imagen del evento está vacía")
    if len(data) > EVENT_IMAGE_MAX_BYTES:
        raise ValueError("La imagen del evento no puede superar 6 MB")
    detected_mime = None
    if data.startswith(b"\xff\xd8\xff"):
        detected_mime = "image/jpeg"
    elif data.startswith(b"\x89PNG\r\n\x1a\n"):
        detected_mime = "image/png"
    elif len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        detected_mime = "image/webp"
    if detected_mime is None:
        raise ValueError("El archivo no contiene una imagen válida")
    extension_matches = (
        (extension in {".jpg", ".jpeg"} and detected_mime == "image/jpeg")
        or (extension == ".png" and detected_mime == "image/png")
        or (extension == ".webp" and detected_mime == "image/webp")
    )
    if not extension_matches:
        raise ValueError("La extensión del archivo no coincide con la imagen")
    return data, detected_mime, filename


def find_promoter_by_key(db, normalized_key):
    for promoter in db.execute("SELECT * FROM promoters ORDER BY id").fetchall():
        stored_key = promoter["normalized_name"] if "normalized_name" in promoter.keys() else None
        if (stored_key or normalize_text_key(promoter["name"])) == normalized_key:
            return promoter
    return None


def ensure_common_promoter(db):
    common_key = normalize_text_key(COMMON_LIST_LABEL)
    common = db.execute("SELECT * FROM promoters WHERE is_common=1 ORDER BY id LIMIT 1").fetchone()
    if not common:
        common = find_promoter_by_key(db, common_key)
    if common:
        db.execute(
            "UPDATE promoters SET name=?, normalized_name=?, is_common=1, is_promo=0, is_birthday=0, active=1, qr_token=NULL, qr_updated_at=NULL WHERE id=?",
            (COMMON_LIST_LABEL, common_key, common["id"]),
        )
        return common["id"]
    cursor = db.execute(
        "INSERT INTO promoters(name, normalized_name, active, is_common, is_promo, qr_token, qr_updated_at, created_at) VALUES (?, ?, 1, 1, 0, NULL, NULL, ?)",
        (COMMON_LIST_LABEL, common_key, now_iso()),
    )
    return cursor.lastrowid


def ensure_promo_promoter(db):
    promo_key = normalize_text_key(PROMO_LIST_LABEL)
    promo = db.execute("SELECT * FROM promoters WHERE is_promo=1 ORDER BY id LIMIT 1").fetchone()
    if not promo:
        promo = find_promoter_by_key(db, promo_key)
    if promo:
        db.execute(
            "UPDATE promoters SET name=?, normalized_name=?, is_common=0, is_promo=1, is_birthday=0, active=1, qr_token=NULL, qr_updated_at=NULL WHERE id=?",
            (PROMO_LIST_LABEL, promo_key, promo["id"]),
        )
        return promo["id"]
    cursor = db.execute(
        "INSERT INTO promoters(name, normalized_name, active, is_common, is_promo, qr_token, qr_updated_at, created_at) VALUES (?, ?, 1, 0, 1, NULL, NULL, ?)",
        (PROMO_LIST_LABEL, promo_key, now_iso()),
    )
    return cursor.lastrowid


def get_or_create_promoter(db, promoter_name):
    display, normalized_key = normalize_promoter_name(promoter_name)
    if normalized_key in {"lista comun", "lista general", "comun", "promo", "promos"}:
        raise ValueError("LISTA COMÚN y PROMOS son listas automáticas y no pueden crearse como promotores")
    existing = find_promoter_by_key(db, normalized_key)
    if existing:
        db.execute(
            "UPDATE promoters SET name=?, normalized_name=?, active=1, is_common=0, is_promo=0 WHERE id=?",
            (display, normalized_key, existing["id"]),
        )
        if not existing["qr_token"]:
            db.execute(
                "UPDATE promoters SET qr_token=?, qr_updated_at=? WHERE id=?",
                (new_qr_token(), now_iso(), existing["id"]),
            )
        return existing["id"], False
    cursor = db.execute(
        "INSERT INTO promoters(name, normalized_name, active, is_common, is_promo, qr_token, qr_updated_at, created_at) VALUES (?, ?, 1, 0, 0, ?, ?, ?)",
        (display, normalized_key, new_qr_token(), now_iso(), now_iso()),
    )
    return cursor.lastrowid, True


def rotate_promoter_qr_tokens(db):
    promoters = db.execute("SELECT id FROM promoters WHERE active=1 AND is_common=0 AND is_promo=0").fetchall()
    stamp = now_iso()
    for promoter in promoters:
        db.execute(
            "UPDATE promoters SET qr_token=?, qr_updated_at=? WHERE id=?",
            (new_qr_token(), stamp, promoter["id"]),
        )
    return len(promoters)


def init_db():
    db = connect_database(app.config.get("DATABASE_URL"), app.config["DATABASE"])
    with closing(db):
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin', 'cashier')),
                sector TEXT NOT NULL DEFAULT 'ticketing',
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS cash_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                opened_at TEXT NOT NULL,
                opened_by INTEGER NOT NULL,
                opening_amount REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open', 'closed')),
                closed_at TEXT,
                closed_by INTEGER,
                declared_cash REAL,
                declared_mercadopago REAL,
                declared_total REAL,
                expected_cash REAL,
                expected_total REAL,
                difference REAL,
                notes TEXT,
                event_name TEXT NOT NULL DEFAULT 'Noche Floki',
                event_date TEXT NOT NULL DEFAULT '',
                capacity INTEGER NOT NULL DEFAULT 0,
                event_image_data BYTEA,
                event_image_mime TEXT,
                event_image_name TEXT,
                FOREIGN KEY(opened_by) REFERENCES users(id),
                FOREIGN KEY(closed_by) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS promoters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS price_presets (
                category TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                price REAL NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS entry_prices (
                category TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                cutoff_time TEXT NOT NULL DEFAULT '03:30',
                before_price REAL NOT NULL DEFAULT 0,
                after_price REAL NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS beverage_products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                price REAL NOT NULL DEFAULT 0,
                stock_unit TEXT NOT NULL DEFAULT 'unidad',
                sale_unit TEXT NOT NULL DEFAULT 'unidad',
                servings_per_stock_unit REAL NOT NULL DEFAULT 1,
                approx_yield REAL NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1,
                sort_order INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS ticketing_products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                price REAL NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1,
                sort_order INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS beverage_stock (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cash_session_id INTEGER NOT NULL,
                beverage_id INTEGER NOT NULL,
                beverage_name TEXT NOT NULL,
                initial_quantity INTEGER NOT NULL DEFAULT 0,
                final_quantity INTEGER,
                updated_at TEXT NOT NULL,
                updated_by INTEGER NOT NULL,
                FOREIGN KEY(cash_session_id) REFERENCES cash_sessions(id),
                FOREIGN KEY(beverage_id) REFERENCES beverage_products(id),
                FOREIGN KEY(updated_by) REFERENCES users(id),
                UNIQUE(cash_session_id, beverage_id)
            );

            CREATE TABLE IF NOT EXISTS birthday_benefits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cash_session_id INTEGER NOT NULL,
                promoter_id INTEGER NOT NULL,
                redeemed_at TEXT NOT NULL,
                redeemed_by INTEGER NOT NULL,
                UNIQUE(cash_session_id, promoter_id),
                FOREIGN KEY(cash_session_id) REFERENCES cash_sessions(id),
                FOREIGN KEY(promoter_id) REFERENCES promoters(id),
                FOREIGN KEY(redeemed_by) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS birthday_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cash_session_id INTEGER NOT NULL,
                promoter_id INTEGER NOT NULL,
                birthday_person_name TEXT NOT NULL,
                date_of_birth TEXT NOT NULL,
                max_people INTEGER NOT NULL DEFAULT 10,
                confirmed_at TEXT NOT NULL,
                created_by INTEGER NOT NULL,
                UNIQUE(cash_session_id, promoter_id),
                FOREIGN KEY(cash_session_id) REFERENCES cash_sessions(id),
                FOREIGN KEY(promoter_id) REFERENCES promoters(id),
                FOREIGN KEY(created_by) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS promoter_guests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cash_session_id INTEGER NOT NULL,
                promoter_id INTEGER NOT NULL,
                guest_name TEXT NOT NULL,
                normalized_name TEXT NOT NULL,
                source_filename TEXT,
                imported_at TEXT NOT NULL,
                imported_by INTEGER NOT NULL,
                FOREIGN KEY(cash_session_id) REFERENCES cash_sessions(id),
                FOREIGN KEY(promoter_id) REFERENCES promoters(id),
                FOREIGN KEY(imported_by) REFERENCES users(id),
                UNIQUE(cash_session_id, promoter_id, normalized_name)
            );

            CREATE TABLE IF NOT EXISTS guest_checkins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cash_session_id INTEGER NOT NULL,
                promoter_guest_id INTEGER NOT NULL,
                promoter_id INTEGER NOT NULL,
                guest_name TEXT NOT NULL,
                normalized_name TEXT NOT NULL,
                checked_in_at TEXT NOT NULL,
                checked_in_by INTEGER NOT NULL,
                movement_id INTEGER,
                FOREIGN KEY(cash_session_id) REFERENCES cash_sessions(id),
                FOREIGN KEY(promoter_guest_id) REFERENCES promoter_guests(id),
                FOREIGN KEY(promoter_id) REFERENCES promoters(id),
                FOREIGN KEY(checked_in_by) REFERENCES users(id),
                UNIQUE(cash_session_id, normalized_name)
            );

            CREATE TABLE IF NOT EXISTS list_imports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cash_session_id INTEGER NOT NULL,
                source_filename TEXT NOT NULL,
                import_mode TEXT NOT NULL DEFAULT 'sync',
                promoter_count INTEGER NOT NULL DEFAULT 0,
                common_count INTEGER NOT NULL DEFAULT 0,
                guest_count INTEGER NOT NULL DEFAULT 0,
                added_count INTEGER NOT NULL DEFAULT 0,
                removed_count INTEGER NOT NULL DEFAULT 0,
                retained_checked_count INTEGER NOT NULL DEFAULT 0,
                imported_at TEXT NOT NULL,
                imported_by INTEGER NOT NULL,
                FOREIGN KEY(cash_session_id) REFERENCES cash_sessions(id),
                FOREIGN KEY(imported_by) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS list_workspaces (
                cash_session_id INTEGER PRIMARY KEY,
                source_text TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL,
                updated_by INTEGER NOT NULL,
                FOREIGN KEY(cash_session_id) REFERENCES cash_sessions(id),
                FOREIGN KEY(updated_by) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS movements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cash_session_id INTEGER NOT NULL,
                movement_type TEXT NOT NULL CHECK(movement_type IN ('sale', 'expense')),
                category TEXT NOT NULL,
                sector TEXT NOT NULL DEFAULT 'ticketing',
                description TEXT,
                quantity INTEGER NOT NULL DEFAULT 1,
                unit_price REAL NOT NULL,
                total REAL NOT NULL,
                payment_method TEXT NOT NULL CHECK(payment_method IN ('cash', 'mercadopago', 'transfer', 'debit', 'credit', 'other')),
                created_at TEXT NOT NULL,
                created_by INTEGER NOT NULL,
                voided INTEGER NOT NULL DEFAULT 0,
                voided_at TEXT,
                voided_by INTEGER,
                void_reason TEXT,
                promoter_id INTEGER,
                beverage_product_id INTEGER,
                stock_units REAL NOT NULL DEFAULT 0,
                linked_movement_id INTEGER,
                FOREIGN KEY(cash_session_id) REFERENCES cash_sessions(id),
                FOREIGN KEY(created_by) REFERENCES users(id),
                FOREIGN KEY(voided_by) REFERENCES users(id),
                FOREIGN KEY(promoter_id) REFERENCES promoters(id),
                FOREIGN KEY(beverage_product_id) REFERENCES beverage_products(id),
                FOREIGN KEY(linked_movement_id) REFERENCES movements(id)
            );

            CREATE TABLE IF NOT EXISTS beverage_stock_adjustments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cash_session_id INTEGER NOT NULL,
                parent_movement_id INTEGER NOT NULL,
                beverage_product_id INTEGER NOT NULL,
                reason TEXT NOT NULL DEFAULT 'bundle',
                quantity REAL NOT NULL DEFAULT 0,
                stock_units REAL NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                created_by INTEGER NOT NULL,
                voided INTEGER NOT NULL DEFAULT 0,
                voided_at TEXT,
                voided_by INTEGER,
                FOREIGN KEY(cash_session_id) REFERENCES cash_sessions(id),
                FOREIGN KEY(parent_movement_id) REFERENCES movements(id),
                FOREIGN KEY(beverage_product_id) REFERENCES beverage_products(id),
                FOREIGN KEY(created_by) REFERENCES users(id),
                FOREIGN KEY(voided_by) REFERENCES users(id),
                UNIQUE(parent_movement_id, beverage_product_id, reason)
            );

            CREATE TABLE IF NOT EXISTS offline_operations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation_id TEXT NOT NULL UNIQUE,
                cash_session_id INTEGER NOT NULL,
                operation_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                result_json TEXT,
                client_created_at TEXT NOT NULL,
                synced_at TEXT NOT NULL,
                created_by INTEGER NOT NULL,
                device_id TEXT NOT NULL,
                FOREIGN KEY(cash_session_id) REFERENCES cash_sessions(id),
                FOREIGN KEY(created_by) REFERENCES users(id)
            );

            CREATE INDEX IF NOT EXISTS idx_movements_session ON movements(cash_session_id);
            CREATE INDEX IF NOT EXISTS idx_movements_created_at ON movements(created_at);
            CREATE INDEX IF NOT EXISTS idx_beverage_stock_adjustments_session ON beverage_stock_adjustments(cash_session_id);
            CREATE INDEX IF NOT EXISTS idx_beverage_stock_adjustments_parent ON beverage_stock_adjustments(parent_movement_id);
            CREATE INDEX IF NOT EXISTS idx_beverage_stock_adjustments_product ON beverage_stock_adjustments(beverage_product_id);
            CREATE INDEX IF NOT EXISTS idx_promoter_guests_session ON promoter_guests(cash_session_id);
            CREATE INDEX IF NOT EXISTS idx_promoter_guests_normalized ON promoter_guests(cash_session_id, normalized_name);
            CREATE INDEX IF NOT EXISTS idx_guest_checkins_session ON guest_checkins(cash_session_id);
            CREATE INDEX IF NOT EXISTS idx_beverage_stock_session ON beverage_stock(cash_session_id);
            CREATE INDEX IF NOT EXISTS idx_offline_operations_session ON offline_operations(cash_session_id);
            CREATE INDEX IF NOT EXISTS idx_offline_operations_device ON offline_operations(device_id, status);
            """
        )

        # Migraciones automáticas para bases v1.0 ya existentes.
        add_column_if_missing(db, "cash_sessions", "event_name", "TEXT NOT NULL DEFAULT 'Noche Floki'")
        add_column_if_missing(db, "cash_sessions", "capacity", "INTEGER NOT NULL DEFAULT 0")
        add_column_if_missing(db, "cash_sessions", "event_date", "TEXT NOT NULL DEFAULT ''")
        add_column_if_missing(db, "cash_sessions", "event_image_data", "BYTEA")
        add_column_if_missing(db, "cash_sessions", "event_image_mime", "TEXT")
        add_column_if_missing(db, "cash_sessions", "event_image_name", "TEXT")
        add_column_if_missing(db, "cash_sessions", "declared_mercadopago", "REAL")
        add_column_if_missing(db, "cash_sessions", "declared_total", "REAL")
        add_column_if_missing(db, "cash_sessions", "expected_total", "REAL")
        add_column_if_missing(db, "users", "sector", "TEXT NOT NULL DEFAULT 'ticketing'")
        add_column_if_missing(db, "movements", "promoter_id", "INTEGER")
        add_column_if_missing(db, "movements", "sector", "TEXT NOT NULL DEFAULT 'ticketing'")
        add_column_if_missing(db, "movements", "beverage_product_id", "INTEGER")
        add_column_if_missing(db, "movements", "stock_units", "REAL NOT NULL DEFAULT 0")
        add_column_if_missing(db, "movements", "linked_movement_id", "INTEGER")
        add_column_if_missing(db, "beverage_products", "stock_unit", "TEXT NOT NULL DEFAULT 'unidad'")
        add_column_if_missing(db, "beverage_products", "sale_unit", "TEXT NOT NULL DEFAULT 'unidad'")
        add_column_if_missing(db, "beverage_products", "servings_per_stock_unit", "REAL NOT NULL DEFAULT 1")
        add_column_if_missing(db, "beverage_products", "approx_yield", "REAL NOT NULL DEFAULT 0")
        add_column_if_missing(db, "beverage_products", "beverage_type", "TEXT NOT NULL DEFAULT 'Otro'")
        add_column_if_missing(db, "beverage_products", "brand", "TEXT NOT NULL DEFAULT 'Sin marca'")
        add_column_if_missing(db, "beverage_products", "presentation", "TEXT NOT NULL DEFAULT 'unidad'")
        add_column_if_missing(db, "promoters", "normalized_name", "TEXT")
        add_column_if_missing(db, "promoters", "is_common", "INTEGER NOT NULL DEFAULT 0")
        add_column_if_missing(db, "promoters", "is_promo", "INTEGER NOT NULL DEFAULT 0")
        add_column_if_missing(db, "promoters", "is_birthday", "INTEGER NOT NULL DEFAULT 0")
        add_column_if_missing(db, "promoters", "qr_token", "TEXT")
        add_column_if_missing(db, "promoters", "qr_updated_at", "TEXT")
        add_column_if_missing(db, "list_imports", "promo_count", "INTEGER NOT NULL DEFAULT 0")
        db.execute("CREATE INDEX IF NOT EXISTS idx_movements_promoter ON movements(promoter_id)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_movements_beverage_product ON movements(beverage_product_id)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_movements_linked ON movements(linked_movement_id)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_beverage_stock_adjustments_session ON beverage_stock_adjustments(cash_session_id)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_beverage_stock_adjustments_parent ON beverage_stock_adjustments(parent_movement_id)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_beverage_stock_adjustments_product ON beverage_stock_adjustments(beverage_product_id)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_promoters_normalized ON promoters(normalized_name)")
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_promoters_qr_token ON promoters(qr_token) WHERE qr_token IS NOT NULL")
        db.execute("UPDATE cash_sessions SET event_date=date(opened_at) WHERE event_date IS NULL OR trim(event_date)='' ")
        db.execute("UPDATE users SET sector='all' WHERE role='admin'")
        db.execute("UPDATE users SET sector='ticketing' WHERE role='cashier' AND sector NOT IN ('ticketing','beverages')")
        db.execute("UPDATE movements SET sector='beverages' WHERE category IN ('drink','drink_special','rrpp_benefit','birthday_benefit','birthday_discount','champagne_speed')")
        db.execute("UPDATE movements SET sector='ticketing' WHERE category IN ('general','advance','vip','free')")
        db.execute("UPDATE movements SET sector='admin' WHERE category NOT IN ('general','advance','vip','free','drink','drink_special','rrpp_benefit','birthday_benefit','birthday_discount','champagne_speed') OR movement_type='expense'")
        db.execute("UPDATE beverage_products SET stock_unit='unidad' WHERE stock_unit IS NULL OR trim(stock_unit)=''")
        db.execute("UPDATE beverage_products SET sale_unit='unidad' WHERE sale_unit IS NULL OR trim(sale_unit)=''")
        db.execute("UPDATE beverage_products SET servings_per_stock_unit=1")
        db.execute("UPDATE beverage_products SET beverage_type=name WHERE beverage_type IS NULL OR trim(beverage_type)='' OR beverage_type='Otro'")
        db.execute("UPDATE beverage_products SET brand='Sin marca' WHERE brand IS NULL OR trim(brand)=''")
        db.execute("UPDATE beverage_products SET presentation=sale_unit WHERE presentation IS NULL OR trim(presentation)='' OR presentation='unidad'")
        db.execute("UPDATE beverage_products SET sale_unit='vaso grande 750 ml', presentation='vaso grande 750 ml' WHERE lower(sale_unit)='vaso grande'")
        # VIP, anticipadas y FREE manual quedan fuera de las nuevas ventas.
        db.execute("UPDATE entry_prices SET active=0 WHERE category IN ('advance','vip','free')")
        db.execute("UPDATE price_presets SET active=0 WHERE category IN ('advance','vip','free')")
        db.execute("UPDATE beverage_products SET stock_unit='lata', sale_unit='lata', servings_per_stock_unit=1 WHERE name='Cerveza' AND stock_unit='unidad' AND sale_unit='unidad'")
        db.execute("UPDATE beverage_products SET stock_unit='botella', sale_unit='botella', servings_per_stock_unit=1 WHERE name='Agua' AND stock_unit='unidad' AND sale_unit='unidad'")
        db.execute("UPDATE beverage_products SET stock_unit='lata', sale_unit='lata', servings_per_stock_unit=1 WHERE name='Energizante' AND stock_unit='unidad' AND sale_unit='unidad'")
        db.execute("UPDATE beverage_products SET stock_unit='botella', sale_unit='vaso', servings_per_stock_unit=1 WHERE name='Trago' AND stock_unit='unidad' AND sale_unit='unidad'")
        db.execute("UPDATE movements SET stock_units=quantity WHERE beverage_product_id IS NOT NULL AND (stock_units IS NULL OR stock_units=0) AND category IN ('drink','drink_special','rrpp_benefit','birthday_benefit','birthday_discount')")

        for beverage in db.execute("SELECT * FROM beverage_products ORDER BY id").fetchall():
            sale_unit = beverage["sale_unit"] or "unidad"
            beverage_type = beverage["beverage_type"] or beverage["name"]
            brand = beverage["brand"] or "Sin marca"
            desired_name = build_beverage_name(beverage_type, brand, sale_unit)
            duplicate = db.execute("SELECT id FROM beverage_products WHERE lower(name)=lower(?) AND id<>?", (desired_name, beverage["id"])).fetchone()
            if not duplicate and desired_name != beverage["name"]:
                db.execute("UPDATE beverage_products SET name=? WHERE id=?", (desired_name, beverage["id"]))
                db.execute("UPDATE beverage_stock SET beverage_name=? WHERE beverage_id=?", (desired_name, beverage["id"]))
            automatic_yield = suggested_approx_yield(beverage["stock_unit"], sale_unit, beverage["beverage_type"], beverage["brand"], beverage["name"])
            db.execute("UPDATE beverage_products SET approx_yield=? WHERE id=?", (automatic_yield, beverage["id"]))
            if automatic_yield > 0:
                db.execute(
                    "UPDATE movements SET stock_units=(quantity * 1.0) / ? WHERE beverage_product_id=? AND category IN ('drink','drink_special','rrpp_benefit','birthday_benefit','birthday_discount')",
                    (automatic_yield, beverage["id"]),
                )

        for inactive in db.execute("SELECT id, name FROM beverage_products WHERE active=0 ORDER BY id").fetchall():
            if "archivada #" not in (inactive["name"] or "").casefold():
                archived_name = f"{(inactive['name'] or 'Bebida')[:55]} · archivada #{inactive['id']}"[:80]
                duplicate_name = db.execute("SELECT id FROM beverage_products WHERE lower(name)=lower(?) AND id<>?", (archived_name, inactive["id"])).fetchone()
                if not duplicate_name:
                    db.execute("UPDATE beverage_products SET name=? WHERE id=?", (archived_name, inactive["id"]))

        for promoter in db.execute("SELECT * FROM promoters ORDER BY id").fetchall():
            normalized_key = normalize_text_key(promoter["name"])
            db.execute("UPDATE promoters SET normalized_name=? WHERE id=?", (normalized_key, promoter["id"]))
        ensure_common_promoter(db)
        ensure_promo_promoter(db)
        for promoter in db.execute("SELECT * FROM promoters WHERE is_common=0 AND is_promo=0").fetchall():
            if not promoter["qr_token"]:
                db.execute(
                    "UPDATE promoters SET qr_token=?, qr_updated_at=? WHERE id=?",
                    (new_qr_token(), now_iso(), promoter["id"]),
                )

        existing_users = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if existing_users == 0:
            db.executemany(
                "INSERT INTO users(name, username, password_hash, role, sector, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                [
                    ("Administrador Floki", "admin", generate_password_hash("admin123"), "admin", "all", now_iso()),
                    ("Caja Boletería", "cajero", generate_password_hash("floki123"), "cashier", "ticketing", now_iso()),
                    ("Caja Bebidas", "bebidas", generate_password_hash("floki123"), "cashier", "beverages", now_iso()),
                ],
            )

        preset_defaults = [
            ("general", "Entrada general", 8000),
            ("drink", "Consumición", 4000),
            ("other", "Otro", 0),
        ]
        for category, label, price in preset_defaults:
            db.execute(
                "INSERT OR IGNORE INTO price_presets(category, label, price, active, updated_at) VALUES (?, ?, ?, 1, ?)",
                (category, label, price, now_iso()),
            )

        entry_defaults = [
            ("general", "Entrada general", "03:30", 8000, 10000),
        ]
        for category, label, cutoff, before_price, after_price in entry_defaults:
            db.execute(
                "INSERT OR IGNORE INTO entry_prices(category, label, cutoff_time, before_price, after_price, active, updated_at) VALUES (?, ?, ?, ?, ?, 1, ?)",
                (category, label, cutoff, before_price, after_price, now_iso()),
            )

        beverage_defaults = [
            ("Cerveza · Lata 473 Ml", 4000, "lata", "lata 473 ml", "Cerveza", "Sin marca", "lata 473 ml", 10),
            ("Agua · Botella 500 Ml", 2000, "botella", "botella 500 ml", "Agua", "Sin marca", "botella 500 ml", 20),
            ("Energizante · Lata 250 Ml", 3000, "lata", "lata 250 ml", "Energizante", "Sin marca", "lata 250 ml", 30),
            ("Trago Preparado · Vaso", 6000, "botella", "vaso", "Trago preparado", "Sin marca", "vaso", 40),
        ]
        for name, price, stock_unit, sale_unit, beverage_type, brand, presentation, sort_order in beverage_defaults:
            db.execute(
                "INSERT OR IGNORE INTO beverage_products(name, price, stock_unit, sale_unit, servings_per_stock_unit, beverage_type, brand, presentation, active, sort_order, updated_at) VALUES (?, ?, ?, ?, 1, ?, ?, ?, 1, ?, ?)",
                (name, price, stock_unit, sale_unit, beverage_type, brand, presentation, sort_order, now_iso()),
            )
        db.execute(
            "INSERT OR IGNORE INTO ticketing_products(name, price, active, sort_order, updated_at) VALUES ('Guardarropa', 3000, 1, 10, ?)",
            (now_iso(),),
        )
        db.commit()


def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for("login", next=request.path))
        return view(**kwargs)

    return wrapped_view


def admin_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for("login"))
        if g.user["role"] != "admin":
            abort(403)
        return view(**kwargs)

    return wrapped_view


def ticketing_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for("login"))
        if g.user["role"] != "admin" and g.user["sector"] != "ticketing":
            abort(403)
        return view(**kwargs)

    return wrapped_view


def beverages_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for("login"))
        if g.user["role"] != "admin" and g.user["sector"] != "beverages":
            abort(403)
        return view(**kwargs)

    return wrapped_view


def current_sector():
    if not g.user:
        return None
    return "all" if g.user["role"] == "admin" else (g.user["sector"] or "ticketing")


@app.before_request
def load_logged_in_user_and_csrf():
    user_id = session.get("user_id")
    g.user = get_db().execute("SELECT * FROM users WHERE id = ? AND active = 1", (user_id,)).fetchone() if user_id else None
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(24)
    if request.method == "POST":
        token = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
        if not token or not secrets.compare_digest(token, session["csrf_token"]):
            abort(400, description="Token de seguridad inválido. Recargá la página e intentá nuevamente.")


@app.context_processor
def inject_helpers():
    return {
        "csrf_token": session.get("csrf_token"),
        "payment_labels": PAYMENT_LABELS,
        "category_labels": CATEGORY_LABELS,
        "entry_categories": ENTRY_CATEGORIES,
        "app_version": APP_VERSION,
        "price_options": PRICE_OPTIONS,
        "price_step": PRICE_STEP,
        "beverage_price_options": BEVERAGE_PRICE_OPTIONS,
        "beverage_price_step": BEVERAGE_PRICE_STEP,
        "promoter_public_url": promoter_public_url,
        "sector_labels": SECTOR_LABELS,
        "current_sector": current_sector(),
        "beverage_type_options": BEVERAGE_TYPE_OPTIONS,
        "beverage_category_options": BEVERAGE_CATEGORY_OPTIONS,
        "beverage_brand_options": BEVERAGE_BRAND_OPTIONS,
        "beverage_presentation_options": BEVERAGE_PRESENTATION_OPTIONS,
        "beverage_stock_unit_options": BEVERAGE_STOCK_UNIT_OPTIONS,
        "approx_yield_options": APPROX_YIELD_OPTIONS,
        "common_free_cutoff_label": FREE_ENTRY_CUTOFF_LABEL,
        "common_free_open": free_entry_available(),
    }


@app.template_filter("money")
def money_filter(value):
    value = float(value or 0)
    formatted = f"{value:,.2f}"
    return "$ " + formatted.replace(",", "X").replace(".", ",").replace("X", ".")


@app.template_filter("datetime_ar")
def datetime_filter(value):
    if not value:
        return "—"
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(ARGENTINA_TZ).replace(tzinfo=None)
        return parsed.strftime("%d/%m/%Y %H:%M")
    except (TypeError, ValueError):
        return value


@app.template_filter("date_ar")
def date_filter(value):
    if not value:
        return "—"
    try:
        return date.fromisoformat(str(value)[:10]).strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return value


def active_entry_prices(now_value=None):
    rows = get_db().execute("SELECT * FROM entry_prices WHERE active=1 AND category='general' ORDER BY category").fetchall()
    current = []
    for row in rows:
        price, phase = resolve_entry_price(row, now_value)
        current.append({**dict(row), "current_price": price, "phase": phase})
    return current


def resolve_entry_price(row, now_value=None):
    now_value = now_value or argentina_now()
    try:
        hour, minute = [int(part) for part in row["cutoff_time"].split(":", 1)]
        cutoff = time(hour, minute)
    except (ValueError, AttributeError):
        cutoff = time(3, 30)
    current_time = now_value.time().replace(second=0, microsecond=0)
    is_after_cutoff = cutoff <= current_time < time(12, 0)
    return (float(row["after_price"]), f"Después de {row['cutoff_time']}") if is_after_cutoff else (float(row["before_price"]), f"Antes de {row['cutoff_time']}")


def get_open_cash_session():
    return get_db().execute(
        """
        SELECT cs.*, u.name AS opened_by_name
        FROM cash_sessions cs
        JOIN users u ON u.id = cs.opened_by
        WHERE cs.status = 'open'
        ORDER BY cs.id DESC LIMIT 1
        """
    ).fetchone()


def session_totals(cash_session_id):
    db = get_db()
    totals = db.execute(
        """
        SELECT
            COALESCE(SUM(CASE WHEN movement_type='sale' AND voided=0 THEN total ELSE 0 END), 0) AS sales,
            COALESCE(SUM(CASE WHEN movement_type='expense' AND voided=0 THEN total ELSE 0 END), 0) AS expenses,
            COALESCE(SUM(CASE WHEN movement_type='sale' AND payment_method='cash' AND voided=0 THEN total ELSE 0 END), 0) AS cash_sales,
            COALESCE(SUM(CASE WHEN movement_type='expense' AND payment_method='cash' AND voided=0 THEN total ELSE 0 END), 0) AS cash_expenses,
            COALESCE(SUM(CASE WHEN movement_type='sale' AND category='free' AND voided=0 THEN quantity ELSE 0 END), 0) AS free_count,
            COALESCE(SUM(CASE WHEN movement_type='sale' AND category IN ('general','advance','vip') AND voided=0 THEN quantity ELSE 0 END), 0) AS paid_count,
            COALESCE(SUM(CASE WHEN movement_type='sale' AND category IN ('drink','drink_special','birthday_discount') AND voided=0 THEN quantity ELSE 0 END), 0) AS paid_beverage_count,
            COALESCE(SUM(CASE WHEN movement_type='sale' AND category IN ('general','advance','vip','drink','drink_special','birthday_discount') AND voided=0 THEN quantity ELSE 0 END), 0) AS ticket_count,
            COALESCE(SUM(CASE WHEN movement_type='sale' AND category IN ('general','advance','vip','free') AND voided=0 THEN quantity ELSE 0 END), 0) AS people_count,
            COALESCE(SUM(CASE WHEN movement_type='sale' AND category IN ('drink','drink_special','rrpp_benefit','birthday_benefit','birthday_discount') AND voided=0 THEN quantity ELSE 0 END), 0) AS drink_count,
            COALESCE(SUM(CASE WHEN movement_type='sale' AND category='rrpp_benefit' AND voided=0 THEN quantity ELSE 0 END), 0) AS rrpp_benefit_count,
            COALESCE(SUM(CASE WHEN movement_type='sale' AND category='cloakroom' AND voided=0 THEN quantity ELSE 0 END), 0) AS cloakroom_count,
            COALESCE(COUNT(CASE WHEN voided=0 THEN 1 END), 0) AS movement_count
        FROM movements
        WHERE cash_session_id = ?
        """,
        (cash_session_id,),
    ).fetchone()
    by_payment = db.execute(
        """
        SELECT payment_method,
               COALESCE(SUM(CASE WHEN movement_type='sale' THEN total ELSE -total END), 0) AS net,
               COALESCE(SUM(CASE WHEN movement_type='sale' THEN total ELSE 0 END), 0) AS sales,
               COALESCE(SUM(CASE WHEN movement_type='expense' THEN total ELSE 0 END), 0) AS expenses
        FROM movements
        WHERE cash_session_id=? AND voided=0
        GROUP BY payment_method
        ORDER BY sales DESC
        """,
        (cash_session_id,),
    ).fetchall()
    return totals, by_payment


def promoter_totals(cash_session_id):
    return get_db().execute(
        """
        SELECT p.id, p.name,
               COALESCE(SUM(CASE WHEN m.voided=0 AND m.category IN ('general','advance','vip','free') THEN m.quantity ELSE 0 END), 0) AS people_count,
               COALESCE(SUM(CASE WHEN m.voided=0 AND m.movement_type='sale' THEN m.total ELSE 0 END), 0) AS sales
        FROM promoters p
        JOIN movements m ON m.promoter_id=p.id AND m.cash_session_id=?
        GROUP BY p.id, p.name
        HAVING COALESCE(SUM(CASE WHEN m.voided=0 AND m.category IN ('general','advance','vip','free') THEN m.quantity ELSE 0 END), 0) > 0
            OR COALESCE(SUM(CASE WHEN m.voided=0 AND m.movement_type='sale' THEN m.total ELSE 0 END), 0) > 0
        ORDER BY people_count DESC, p.name COLLATE NOCASE
        """,
        (cash_session_id,),
    ).fetchall()


def ensure_beverage_in_event_stock(db, cash_session_id, product, user_id, initial_quantity=0):
    """Asegura la fila de stock sin arrastrar datos históricos por sorpresa.

    Desde v2.9.4 el stock del evento anterior solo se copia cuando el administrador
    lo marca explícitamente al crear la nueva jornada.
    """
    try:
        suggested = max(0, int(float(initial_quantity or 0)))
    except (TypeError, ValueError):
        suggested = 0
    db.execute(
        """INSERT OR IGNORE INTO beverage_stock(cash_session_id, beverage_id, beverage_name, initial_quantity, final_quantity, updated_at, updated_by)
           VALUES (?, ?, ?, ?, NULL, ?, ?)""",
        (cash_session_id, product["id"], product["name"], suggested, now_iso(), user_id),
    )
    db.execute(
        "UPDATE beverage_stock SET beverage_name=? WHERE cash_session_id=? AND beverage_id=?",
        (product["name"], cash_session_id, product["id"]),
    )


def initialize_event_stock(db, cash_session_id, user_id, initial_quantities=None):
    initial_quantities = initial_quantities or {}
    products = db.execute("SELECT * FROM beverage_products WHERE active=1 ORDER BY name COLLATE NOCASE").fetchall()
    for product in products:
        ensure_beverage_in_event_stock(
            db, cash_session_id, product, user_id,
            initial_quantities.get(int(product["id"]), 0),
        )


def previous_event_import_options(db):
    """Devuelve inventario final y gastos del último evento cerrado para importación selectiva."""
    previous_event = db.execute(
        """SELECT id, event_name, event_date, closed_at
           FROM cash_sessions
           WHERE status='closed'
           ORDER BY COALESCE(closed_at, opened_at) DESC, id DESC
           LIMIT 1"""
    ).fetchone()
    if not previous_event:
        return None, [], []

    stock_rows = db.execute(
        """SELECT bs.beverage_id, bs.beverage_name, bs.final_quantity,
                  bp.stock_unit, bp.active
           FROM beverage_stock bs
           LEFT JOIN beverage_products bp ON bp.id=bs.beverage_id
           WHERE bs.cash_session_id=? AND bs.final_quantity IS NOT NULL AND COALESCE(bp.active, 0)=1
           ORDER BY bs.beverage_name COLLATE NOCASE""",
        (previous_event["id"],),
    ).fetchall()
    expense_rows = db.execute(
        """SELECT id, description, total, payment_method
           FROM movements
           WHERE cash_session_id=? AND movement_type='expense' AND voided=0
           ORDER BY id ASC""",
        (previous_event["id"],),
    ).fetchall()
    return previous_event, stock_rows, expense_rows


def event_stock_rows(cash_session_id):
    """Stock del evento sumando ventas y ajustes automáticos de combos.

    Los movimientos históricos ``champagne_speed`` siguen computando consumo para no
    alterar jornadas anteriores. Desde v2.9.0 los nuevos 2 Speed incluidos se guardan
    en ``beverage_stock_adjustments`` y no aparecen como una segunda venta.
    """
    return get_db().execute(
        """SELECT bs.*, bp.stock_unit, bp.sale_unit, bp.servings_per_stock_unit, bp.approx_yield, bp.beverage_type, bp.brand,
                  COALESCE((SELECT SUM(m.quantity) FROM movements m
                            WHERE m.cash_session_id=bs.cash_session_id AND m.beverage_product_id=bs.beverage_id
                              AND m.voided=0 AND m.movement_type='sale' AND m.category<>'champagne_speed'), 0) AS sold_quantity,
                  COALESCE((SELECT SUM(m.quantity) FROM movements m
                            WHERE m.cash_session_id=bs.cash_session_id AND m.beverage_product_id=bs.beverage_id
                              AND m.voided=0 AND m.category='drink'), 0) AS regular_quantity,
                  COALESCE((SELECT SUM(m.quantity) FROM movements m
                            WHERE m.cash_session_id=bs.cash_session_id AND m.beverage_product_id=bs.beverage_id
                              AND m.voided=0 AND m.category IN ('drink_special','birthday_discount')), 0) AS special_quantity,
                  COALESCE((SELECT SUM(m.quantity) FROM movements m
                            WHERE m.cash_session_id=bs.cash_session_id AND m.beverage_product_id=bs.beverage_id
                              AND m.voided=0 AND m.category IN ('rrpp_benefit','birthday_benefit')), 0) AS benefit_quantity,
                  COALESCE((SELECT SUM(m.stock_units) FROM movements m
                            WHERE m.cash_session_id=bs.cash_session_id AND m.beverage_product_id=bs.beverage_id
                              AND m.voided=0 AND m.movement_type='sale'), 0)
                  + COALESCE((SELECT SUM(a.stock_units) FROM beverage_stock_adjustments a
                              WHERE a.cash_session_id=bs.cash_session_id AND a.beverage_product_id=bs.beverage_id
                                AND a.voided=0), 0) AS consumed_stock,
                  COALESCE((SELECT SUM(m.quantity) FROM movements m
                            WHERE m.cash_session_id=bs.cash_session_id AND m.beverage_product_id=bs.beverage_id
                              AND m.voided=0 AND m.category='champagne_speed'), 0)
                  + COALESCE((SELECT SUM(a.quantity) FROM beverage_stock_adjustments a
                              WHERE a.cash_session_id=bs.cash_session_id AND a.beverage_product_id=bs.beverage_id
                                AND a.voided=0 AND a.reason='champagne_speed'), 0) AS bundle_quantity
           FROM beverage_stock bs
           JOIN beverage_products bp ON bp.id=bs.beverage_id
           WHERE bs.cash_session_id=? AND bp.active=1
           ORDER BY bs.beverage_name COLLATE NOCASE""",
        (cash_session_id,),
    ).fetchall()


def stock_view_rows(cash_session_id):
    rows = []
    for row in event_stock_rows(cash_session_id):
        item = dict(row)
        initial = float(item["initial_quantity"] or 0)
        final = item["final_quantity"]
        item["sold_quantity"] = int(item["sold_quantity"] or 0)
        item["regular_quantity"] = int(item["regular_quantity"] or 0)
        item["special_quantity"] = int(item["special_quantity"] or 0)
        item["benefit_quantity"] = int(item["benefit_quantity"] or 0)
        item["bundle_quantity"] = int(item.get("bundle_quantity") or 0)
        estimated_stock_consumed = float(item.get("consumed_stock") or 0)
        physical_consumed, observed_yield, yield_status = calculate_event_yield(initial, final, item["sold_quantity"])
        item["consumed_stock"] = physical_consumed
        item["estimated_stock_consumed"] = round(estimated_stock_consumed, 4)
        item["observed_yield"] = observed_yield
        item["yield_status"] = yield_status
        approx_yield = suggested_approx_yield(item["stock_unit"], item["sale_unit"], item.get("beverage_type"), item.get("brand"), item.get("beverage_name")) if not float(item.get("approx_yield") or 0) else float(item.get("approx_yield") or 0)
        item["approx_yield"] = approx_yield
        item["category_group"] = infer_beverage_category(item.get("beverage_type"), item.get("brand"), item.get("sale_unit"), item.get("beverage_name"))
        # El consumo estimado sale de los movimientos reales de stock. Así una venta de
        # Champagne descuenta sus 2 Speed aunque esos Speed no sean un ticket adicional.
        item["approx_consumed"] = round(estimated_stock_consumed, 2)
        item["expected_final"] = round(initial - item["approx_consumed"], 2)
        item["difference"] = None
        rows.append(item)
    return rows


def birthday_promoter_statuses(db, cash_session_id):
    rows = db.execute(
        """SELECT p.*, be.birthday_person_name, be.date_of_birth, be.max_people,
                  bb.id AS benefit_redeemed_id
           FROM promoters p
           JOIN birthday_events be ON be.promoter_id=p.id AND be.cash_session_id=?
           LEFT JOIN birthday_benefits bb ON bb.cash_session_id=? AND bb.promoter_id=p.id
           WHERE p.active=1 AND p.is_birthday=1
           ORDER BY p.name COLLATE NOCASE""",
        (cash_session_id, cash_session_id),
    ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        birthday_key = normalize_guest_name(item["birthday_person_name"])[1]
        counts = db.execute(
            """SELECT COUNT(*) AS checked_count,
                      COALESCE(MAX(CASE WHEN normalized_name=? THEN 1 ELSE 0 END), 0) AS birthday_checked
               FROM guest_checkins
               WHERE cash_session_id=? AND promoter_id=?""",
            (birthday_key, cash_session_id, item["id"]),
        ).fetchone()
        listed_count = db.execute(
            "SELECT COUNT(*) FROM promoter_guests WHERE cash_session_id=? AND promoter_id=?",
            (cash_session_id, item["id"]),
        ).fetchone()[0]
        item["checked_count"] = int(counts["checked_count"] or 0)
        item["birthday_checked"] = bool(counts["birthday_checked"])
        item["listed_count"] = int(listed_count or 0)
        item["gift_eligible"] = item["birthday_checked"] and item["checked_count"] >= BIRTHDAY_GIFT_MIN_CHECKINS
        result.append(item)
    return result


def clear_event_promoter_lists(db, cash_session_id):
    counts = db.execute(
        "SELECT (SELECT COUNT(*) FROM promoter_guests WHERE cash_session_id=?) AS guests, (SELECT COUNT(*) FROM guest_checkins WHERE cash_session_id=?) AS checkins",
        (cash_session_id, cash_session_id),
    ).fetchone()
    db.execute("UPDATE movements SET description='Ingreso por lista' WHERE cash_session_id=? AND category='free' AND description LIKE 'Lista:%'", (cash_session_id,))
    db.execute("DELETE FROM guest_checkins WHERE cash_session_id=?", (cash_session_id,))
    db.execute("DELETE FROM promoter_guests WHERE cash_session_id=?", (cash_session_id,))
    db.execute("DELETE FROM list_imports WHERE cash_session_id=?", (cash_session_id,))
    db.execute("DELETE FROM list_workspaces WHERE cash_session_id=?", (cash_session_id,))
    db.execute("DELETE FROM birthday_events WHERE cash_session_id=?", (cash_session_id,))
    return int(counts["guests"] or 0), int(counts["checkins"] or 0)


def session_movements(cash_session_id, limit=None, movement_type=None, payment_method=None, benefits_last=False):
    clauses = ["m.cash_session_id=?"]
    params = [cash_session_id]
    if movement_type in {"sale", "expense"}:
        clauses.append("m.movement_type=?")
        params.append(movement_type)
    if payment_method in PAYMENT_METHODS:
        clauses.append("m.payment_method=?")
        params.append(payment_method)
    sql = f"""
        SELECT m.*, u.name AS user_name, p.name AS promoter_name
        FROM movements m
        JOIN users u ON u.id=m.created_by
        LEFT JOIN promoters p ON p.id=m.promoter_id
        WHERE {' AND '.join(clauses)}
        ORDER BY
          {"CASE WHEN (m.total=0 OR m.category IN ('free','rrpp_benefit','birthday_benefit')) THEN 1 ELSE 0 END ASC," if benefits_last else ""}
          m.id DESC
    """
    if limit:
        sql += " LIMIT ?"
        params.append(limit)
    return get_db().execute(sql, params).fetchall()


@app.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        user = get_db().execute("SELECT * FROM users WHERE username = ? AND active = 1", (username,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session.permanent = True
            session["user_id"] = user["id"]
            session["csrf_token"] = secrets.token_hex(24)
            next_url = request.args.get("next", "")
            return redirect(next_url if next_url.startswith("/") and not next_url.startswith("//") else url_for("dashboard"))
        flash("Usuario o contraseña incorrectos.", "error")
    return render_template("login.html")


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def dashboard():
    cash = get_open_cash_session()
    sector = current_sector()
    show_entries = g.user["role"] == "admin" or sector == "ticketing"
    show_beverages = g.user["role"] == "admin" or sector == "beverages"
    active_promoters = get_db().execute("SELECT * FROM promoters WHERE active=1 AND is_common=0 AND is_promo=0 ORDER BY name COLLATE NOCASE").fetchall() if show_entries else []
    entry_prices = active_entry_prices() if show_entries else []
    beverages = get_db().execute("SELECT * FROM beverage_products WHERE active=1 ORDER BY name COLLATE NOCASE").fetchall() if show_beverages else []
    beverage_groups = []
    if show_beverages:
        current_sold = beverage_paid_sales_by_product(cash["id"]) if cash else {}
        previous_product_sales, previous_category_sales = previous_event_beverage_ranking(cash["id"]) if cash else ({}, {})
        beverage_groups = group_beverages(
            beverages, product_ranking=previous_product_sales,
            category_ranking=previous_category_sales, sold_counts=current_sold,
        )
    ticketing_products = get_db().execute("SELECT * FROM ticketing_products WHERE active=1 ORDER BY sort_order, name COLLATE NOCASE").fetchall() if show_entries else []
    birthday_promoters = []
    if cash and show_beverages:
        birthday_promoters = birthday_promoter_statuses(get_db(), cash["id"])
    if cash:
        totals, all_by_payment = session_totals(cash["id"])
        expected_total = cash["opening_amount"] + totals["sales"] - totals["expenses"] if g.user["role"] == "admin" else None
        all_movements = session_movements(cash["id"], limit=60)
        if g.user["role"] == "admin":
            movements = all_movements[:20]
            by_payment = all_by_payment
            promoter_summary = promoter_totals(cash["id"])
        elif sector == "ticketing":
            movements = [row for row in all_movements if row["category"] in HISTORICAL_ENTRY_CATEGORIES][:20]
            by_payment = []
            promoter_summary = promoter_totals(cash["id"])
        else:
            # Caja de bebidas puede revisar sus últimos movimientos operativos,
            # pero sigue sin acceder a totales acumulados, ganancias ni reportes completos.
            beverage_activity_categories = {
                "drink", "drink_special", "rrpp_benefit",
                "birthday_benefit", "birthday_discount"
            }
            movements = [
                row for row in all_movements
                if row["sector"] == "beverages"
                and row["category"] in beverage_activity_categories
            ][:20]
            by_payment = []
            promoter_summary = []
        occupancy_percent = round((totals["people_count"] / cash["capacity"] * 100), 1) if cash["capacity"] else 0
        stock_pending = get_db().execute(
            """SELECT COUNT(*) FROM beverage_stock bs
               JOIN beverage_products bp ON bp.id=bs.beverage_id
               WHERE bs.cash_session_id=? AND bp.active=1 AND bs.final_quantity IS NULL""",
            (cash["id"],),
        ).fetchone()[0]
        guest_pending = get_db().execute(
            """SELECT COUNT(DISTINCT pg.normalized_name) FROM promoter_guests pg
               LEFT JOIN guest_checkins gc ON gc.cash_session_id=pg.cash_session_id AND gc.normalized_name=pg.normalized_name
               WHERE pg.cash_session_id=? AND gc.id IS NULL""",
            (cash["id"],),
        ).fetchone()[0] if show_entries else 0
        beverage_progress = []  # El control parcial vive únicamente en la pestaña Stock
    else:
        totals = by_payment = movements = promoter_summary = None
        beverage_progress = []
        expected_total = occupancy_percent = guest_pending = stock_pending = 0
    previous_event = previous_stock = previous_expenses = None
    if not cash and g.user["role"] == "admin":
        previous_event, previous_stock, previous_expenses = previous_event_import_options(get_db())
    return render_template(
        "dashboard.html", cash=cash, totals=totals, by_payment=by_payment, movements=movements,
        expected_total=expected_total, promoters=active_promoters, entry_prices=entry_prices, beverages=beverages, beverage_groups=beverage_groups,
        promoter_summary=promoter_summary, occupancy_percent=occupancy_percent, guest_pending=guest_pending,
        show_entries=show_entries, show_beverages=show_beverages, ticketing_products=ticketing_products, sector=sector, today=date.today().isoformat(), stock_pending=stock_pending,
        beverage_progress=beverage_progress, birthday_promoters=birthday_promoters,
        birthday_discount_open=birthday_discount_available(),
        birthday_discount_cutoff_label=BIRTHDAY_DISCOUNT_CUTOFF_LABEL,
        birthday_gift_min_checkins=BIRTHDAY_GIFT_MIN_CHECKINS,
        previous_event=previous_event, previous_stock=previous_stock or [], previous_expenses=previous_expenses or [],
    )


@app.post("/cash/open")
@admin_required
def open_cash():
    if get_open_cash_session():
        flash("Ya existe una caja abierta.", "error")
        return redirect(url_for("dashboard"))
    try:
        opening_raw = request.form.get("opening_amount", "").strip()
        capacity_raw = request.form.get("capacity", "").strip()
        opening_amount = money_to_float(opening_raw) if opening_raw else 0.0
        event_name = request.form.get("event_name", "Noche Floki").strip()[:100] or "Noche Floki"
        capacity = positive_int(capacity_raw or "0", "La capacidad", maximum=10000, allow_zero=True)
        event_date = request.form.get("event_date", "").strip() or date.today().isoformat()
        try:
            date.fromisoformat(event_date)
        except ValueError as exc:
            raise ValueError("Elegí una fecha válida para el evento") from exc
        event_image_data, event_image_mime, event_image_name = validate_event_image(request.files.get("event_image"))
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("dashboard"))
    db = get_db()
    previous_event, previous_stock, previous_expenses = previous_event_import_options(db)
    source_event_id = int(previous_event["id"]) if previous_event else None

    import_stock = request.form.get("import_previous_stock") == "1"
    import_expenses = request.form.get("import_previous_expenses") == "1"
    selected_stock_ids = {
        int(value) for value in request.form.getlist("previous_stock_ids") if str(value).isdigit()
    }
    selected_expense_ids = {
        int(value) for value in request.form.getlist("previous_expense_ids") if str(value).isdigit()
    }

    stock_initials = {}
    if import_stock and source_event_id:
        for row in previous_stock:
            beverage_id = int(row["beverage_id"])
            if beverage_id in selected_stock_ids and row["final_quantity"] is not None:
                stock_initials[beverage_id] = max(0, int(float(row["final_quantity"] or 0)))

    imported_expenses = []
    if import_expenses and source_event_id:
        for row in previous_expenses:
            if int(row["id"]) in selected_expense_ids:
                imported_expenses.append(row)

    try:
        cursor = db.execute(
            """INSERT INTO cash_sessions(
                   opened_at, opened_by, opening_amount, status, event_name, event_date, capacity,
                   event_image_data, event_image_mime, event_image_name
               ) VALUES (?, ?, ?, 'open', ?, ?, ?, ?, ?, ?)""",
            (
                now_iso(), g.user["id"], opening_amount, event_name, event_date, capacity,
                event_image_data, event_image_mime, event_image_name,
            ),
        )
        new_session_id = cursor.lastrowid
        initialize_event_stock(db, new_session_id, g.user["id"], stock_initials)

        for expense in imported_expenses:
            total = float(expense["total"] or 0)
            db.execute(
                """INSERT INTO movements(
                       cash_session_id, movement_type, category, sector, description,
                       quantity, unit_price, total, payment_method, created_at, created_by
                   ) VALUES (?, 'expense', 'expense', 'admin', ?, 1, ?, ?, ?, ?, ?)""",
                (
                    new_session_id,
                    (expense["description"] or "Gasto importado")[:180],
                    total, total,
                    expense["payment_method"] if expense["payment_method"] in PAYMENT_METHODS else "cash",
                    now_iso(), g.user["id"],
                ),
            )
        db.commit()
    except Exception:
        db.rollback()
        app.logger.exception("No se pudo crear el evento con importación selectiva")
        flash("No se pudo crear el evento. No se guardó ningún dato; probá nuevamente.", "error")
        return redirect(url_for("dashboard"))

    parts = []
    if import_stock:
        parts.append(f"{len(stock_initials)} ítems de stock")
    if import_expenses:
        parts.append(f"{len(imported_expenses)} gastos")
    imported_copy = f" Se importaron {', '.join(parts)} del evento anterior." if parts else ""
    flash(f"Evento y caja creados correctamente.{imported_copy}", "success")
    return redirect(url_for("dashboard"))


@app.get("/events/<int:session_id>/banner")
@login_required
def event_banner(session_id):
    cash = get_db().execute(
        "SELECT event_image_data, event_image_mime FROM cash_sessions WHERE id=?",
        (session_id,),
    ).fetchone()
    if not cash:
        abort(404)
    data = cash["event_image_data"]
    if not data:
        return send_from_directory(app.static_folder, "img/floki-club-bg.jpg", mimetype="image/jpeg")
    response = Response(bytes(data), mimetype=cash["event_image_mime"] or "image/jpeg")
    response.headers["Cache-Control"] = "private, max-age=60"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.post("/events/<int:session_id>/banner")
@admin_required
def update_event_banner(session_id):
    db = get_db()
    cash = db.execute("SELECT id, status FROM cash_sessions WHERE id=?", (session_id,)).fetchone()
    if not cash:
        abort(404)
    action = request.form.get("banner_action", "replace")
    try:
        if action == "remove":
            db.execute(
                "UPDATE cash_sessions SET event_image_data=NULL, event_image_mime=NULL, event_image_name=NULL WHERE id=?",
                (session_id,),
            )
            flash("Imagen del evento eliminada. Se usa el banner Floki predeterminado.", "success")
        else:
            data, mimetype, filename = validate_event_image(request.files.get("event_image"))
            if not data:
                raise ValueError("Elegí una imagen para reemplazar el banner")
            db.execute(
                "UPDATE cash_sessions SET event_image_data=?, event_image_mime=?, event_image_name=? WHERE id=?",
                (data, mimetype, filename, session_id),
            )
            flash("Banner del evento actualizado.", "success")
        db.commit()
    except ValueError as exc:
        flash(str(exc), "error")
    return redirect(request.form.get("return_to") or url_for("dashboard"))


@app.post("/movements/sale")
@admin_required
def register_sale():
    cash = get_open_cash_session()
    if not cash:
        flash("Primero tenés que abrir una caja.", "error")
        return redirect(url_for("dashboard"))
    try:
        category = request.form.get("category", "general")
        if category not in SALE_CATEGORIES:
            raise ValueError("Categoría inválida")
        if category in {"free", "advance", "vip"}:
            raise ValueError("La entrada FREE solo se confirma desde una lista y VIP/anticipada ya no están habilitadas")
        quantity = positive_int(request.form.get("quantity", "1"), "La cantidad", maximum=500)
        unit_price = 0.0 if category == "free" else price_from_option(request.form.get("unit_price", "0"))
        payment_method = request.form.get("payment_method", "cash")
        if payment_method not in PAYMENT_METHODS:
            raise ValueError("Medio de pago inválido")
        description = request.form.get("description", "").strip()[:180]
        promoter_id = request.form.get("promoter_id", "").strip()
        promoter_id = int(promoter_id) if promoter_id else None
        if promoter_id:
            promoter = get_db().execute("SELECT id FROM promoters WHERE id=? AND active=1", (promoter_id,)).fetchone()
            if not promoter:
                raise ValueError("Promotor inválido")
        if category not in ENTRY_CATEGORIES:
            promoter_id = None
        total = round(unit_price * quantity, 2)
    except (ValueError, TypeError) as exc:
        flash(f"No se pudo registrar la venta: {exc}", "error")
        return redirect(url_for("dashboard"))

    get_db().execute(
        """
        INSERT INTO movements(cash_session_id, movement_type, category, sector, description, quantity, unit_price, total, payment_method, created_at, created_by, promoter_id)
        VALUES (?, 'sale', ?, 'admin', ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (cash["id"], category, description, quantity, unit_price, total, payment_method, now_iso(), g.user["id"], promoter_id),
    )
    get_db().commit()
    flash("Venta registrada.", "success")
    return redirect(url_for("dashboard"))


def operation_datetime(value=None, epoch_ms=None):
    """Normaliza la hora de la operación usando el reloj de servidor guardado por la PWA."""
    now_value = argentina_now()
    if epoch_ms not in (None, ""):
        try:
            parsed_epoch = datetime.fromtimestamp(float(epoch_ms) / 1000, tz=ARGENTINA_TZ).replace(tzinfo=None, microsecond=0)
            if abs((now_value - parsed_epoch).total_seconds()) <= 7 * 24 * 60 * 60:
                return parsed_epoch
        except (TypeError, ValueError, OSError, OverflowError):
            pass
    if not value:
        return now_value
    text = str(value).strip().replace("T", " ").replace("Z", "")[:19]
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return now_value
    delta_seconds = abs((now_value - parsed).total_seconds())
    return parsed if delta_seconds <= 7 * 24 * 60 * 60 else now_value


def operation_time_iso(value=None, epoch_ms=None):
    return operation_datetime(value, epoch_ms).isoformat(sep=" ")


def perform_quick_sale(db, cash, user, payload, *, created_at=None):
    """Registra una venta desde web u offline usando una única validación de negocio."""
    sale_kind = str(payload.get("sale_kind", "entry"))
    if user["role"] != "admin":
        sector = user["sector"] or "ticketing"
        allowed = {
            "ticketing": {"entry", "ticketing_product"},
            "beverages": {"beverage", "special_beverage", "rrpp_benefit", "birthday_discount"},
        }
        if sale_kind not in allowed.get(sector, set()):
            raise PermissionError("Tu usuario no tiene acceso a esa operación")

    quantity = positive_int(payload.get("quantity", "1"), "La cantidad", maximum=100)
    # El voucher RRPP es siempre una sola consumición y vale $0.
    # Se fuerza en backend para que ni la interfaz ni una petición manual puedan
    # registrar más de una unidad por voucher.
    if sale_kind == "rrpp_benefit":
        quantity = 1
    # Para agilizar Caja de Bebidas, toda venta paga de bebidas se registra
    # operativamente como efectivo. El Mercado Pago real se declara una sola
    # vez al cierre de la noche y no en cada consumición.
    if sale_kind in {"beverage", "special_beverage", "birthday_discount"}:
        payment_method = "cash"
    else:
        payment_method = str(payload.get("payment_method", "cash"))
    if payment_method not in PAYMENT_METHODS:
        raise ValueError("Medio de pago inválido")

    promoter_id = None
    beverage_product_id = None
    stock_units = 0.0
    product = None
    operation_dt = operation_datetime(created_at)

    if sale_kind == "entry":
        category = str(payload.get("category", "general"))
        row = db.execute("SELECT * FROM entry_prices WHERE category=? AND active=1", (category,)).fetchone()
        if not row or category != "general":
            raise ValueError("Solo está habilitada la entrada general. La entrada FREE se confirma desde Listas RRPP")
        unit_price, phase = resolve_entry_price(row, operation_dt)
        description = f"{row['label']} · {phase}"
        promoter_value = str(payload.get("promoter_id", "")).strip()
        promoter_id = int(promoter_value) if promoter_value else None
        if promoter_id and not db.execute("SELECT id FROM promoters WHERE id=? AND active=1", (promoter_id,)).fetchone():
            raise ValueError("Promotor inválido")
    elif sale_kind in {"beverage", "special_beverage", "rrpp_benefit", "birthday_discount"}:
        product_id = positive_int(payload.get("beverage_id"), "La bebida", maximum=100000)
        product = db.execute("SELECT * FROM beverage_products WHERE id=? AND active=1", (product_id,)).fetchone()
        if not product:
            raise ValueError("Bebida inválida")
        beverage_product_id = product["id"]
        stock_units = beverage_stock_consumption(product, quantity)
        sale_unit = product["sale_unit"] or "unidad"
        champagne_bundle = is_champagne_product(product)
        if sale_kind == "beverage":
            category = "drink"
            unit_price = float(product["price"])
            description = f"{product['name']} · {sale_unit}" + (" · incluye 2 Speed" if champagne_bundle else "")
        elif sale_kind == "special_beverage":
            category = "drink_special"
            unit_price = beverage_price_from_option(payload.get("special_price"), allow_zero=False)
            comment = str(payload.get("comment", "")).strip()[:160]
            if len(comment) < 2:
                raise ValueError("Escribí qué se vendió en el comentario")
            description = f"Bebida especial · {product['name']} · {sale_unit} · {comment}" + (" · incluye 2 Speed" if champagne_bundle else "")
        elif sale_kind == "rrpp_benefit":
            category = "rrpp_benefit"
            unit_price = 0.0
            beneficiary_comment = str(payload.get("beneficiary_comment", "")).strip()[:120]
            description = f"VOUCHER RRPP $0 · {product['name']} · 1 {sale_unit}" + (" · incluye 2 Speed" if champagne_bundle else "")
            if beneficiary_comment:
                description += f" · Beneficiario: {beneficiary_comment}"
            payment_method = "other"
        else:
            if not birthday_discount_available(operation_dt):
                raise ValueError(f"El 50% OFF de cumpleaños finalizó a las {BIRTHDAY_DISCOUNT_CUTOFF_LABEL}")
            promoter_id = positive_int(payload.get("birthday_promoter_id"), "El cumpleaños", maximum=100000)
            birthday = db.execute(
                """SELECT p.id, be.birthday_person_name FROM birthday_events be
                   JOIN promoters p ON p.id=be.promoter_id
                   WHERE be.cash_session_id=? AND p.id=? AND p.active=1 AND p.is_birthday=1""",
                (cash["id"], promoter_id),
            ).fetchone()
            if not birthday:
                raise ValueError("Seleccioná un cumpleaños confirmado para este evento")
            birthday_key = normalize_guest_name(birthday["birthday_person_name"])[1]
            birthday_checked = db.execute(
                """SELECT id FROM guest_checkins
                   WHERE cash_session_id=? AND promoter_id=? AND normalized_name=? LIMIT 1""",
                (cash["id"], promoter_id, birthday_key),
            ).fetchone()
            if not birthday_checked:
                raise ValueError("El 50% OFF se habilita cuando ingresa el cumpleañero o cumpleañera")
            category = "birthday_discount"
            unit_price = round(float(product["price"]) * 0.5, 2)
            description = f"50% OFF CUMPLEAÑOS · {birthday['birthday_person_name']} · {product['name']} · {sale_unit}" + (" · incluye 2 Speed" if champagne_bundle else "")
    elif sale_kind == "ticketing_product":
        product_id = positive_int(payload.get("ticketing_product_id"), "El producto", maximum=100000)
        product = db.execute("SELECT * FROM ticketing_products WHERE id=? AND active=1", (product_id,)).fetchone()
        if not product:
            raise ValueError("Producto de boletería inválido")
        category = "cloakroom"
        unit_price = float(product["price"])
        description = product["name"]
    else:
        raise ValueError("Acción rápida inválida")

    movement_sector = "beverages" if sale_kind in {"beverage", "special_beverage", "rrpp_benefit", "birthday_discount"} else "ticketing"
    total = 0 if sale_kind == "rrpp_benefit" else round(unit_price * quantity, 2)
    cursor = db.execute(
        """
        INSERT INTO movements(cash_session_id, movement_type, category, sector, description, quantity, unit_price, total, payment_method, created_at, created_by, promoter_id, beverage_product_id, stock_units)
        VALUES (?, 'sale', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (cash["id"], category, movement_sector, description, quantity, unit_price, total, payment_method, operation_dt.isoformat(sep=" "), user["id"], promoter_id, beverage_product_id, stock_units),
    )
    champagne_bundle = bool(product is not None and is_champagne_product(product))
    champagne_speed_status = None
    if champagne_bundle:
        champagne_speed_status = add_champagne_speed_stock(
            db, cash, user, cursor.lastrowid, product, quantity, promoter_id=promoter_id,
            created_at=operation_dt.isoformat(sep=" "),
        )
    messages = {
        "rrpp_benefit": f"Voucher RRPP registrado: {product['name']} × 1. Valor $0; se descontó una consumición del stock.",
        "special_beverage": f"Bebida especial registrada y asignada al stock de {product['name']}.",
        "birthday_discount": f"50% OFF de cumpleaños aplicado: {product['name']} × {quantity}.",
    }
    default_message = f"Venta rápida registrada: {description} × {quantity}."
    message = messages.get(sale_kind, default_message)
    if champagne_bundle and champagne_speed_status in {"adjustment", "adjustment_existing", "legacy_movement"}:
        message += f" También se descontaron {quantity * 2} Speed ({2} por champagne)."
    elif champagne_bundle and champagne_speed_status == "missing_speed":
        message += " Champagne registrado correctamente. No había una variante Speed activa para descontar el acompañamiento; podés configurarla después en Bebidas."
    elif champagne_bundle and champagne_speed_status == "stock_warning":
        message += " Champagne registrado correctamente. El cobro quedó guardado, pero no se pudo registrar el descuento automático de Speed; revisalo luego desde Stock."
    return {
        "movement_id": cursor.lastrowid,
        "message": message,
        "description": description,
        "category": category,
        "quantity": quantity,
        "total": total,
    }


@app.post("/movements/quick-sale")
@login_required
def register_quick_sale():
    cash = get_open_cash_session()
    if not cash:
        flash("Primero tenés que abrir una caja.", "error")
        return redirect(url_for("dashboard"))
    db = get_db()
    try:
        result = perform_quick_sale(db, cash, g.user, request.form)
        db.commit()
    except PermissionError:
        db.rollback()
        abort(403)
    except (ValueError, TypeError) as exc:
        db.rollback()
        flash(f"No se pudo registrar la venta: {exc}", "error")
        return redirect(url_for("dashboard"))
    except Exception:
        db.rollback()
        app.logger.exception("Error registrando venta rápida; la operación fue revertida")
        flash("No se pudo registrar la venta. No se guardó ningún cobro ni descuento de stock. Probá nuevamente.", "error")
        return redirect(url_for("dashboard"))
    flash(result["message"], "success")
    return redirect(url_for("dashboard"))


@app.post("/movements/expense")
@admin_required
def register_expense():
    cash = get_open_cash_session()
    if not cash:
        flash("Primero tenés que abrir una caja.", "error")
        return redirect(url_for("dashboard") + "#gastos-panel")
    try:
        description = request.form.get("description", "").strip()
        if len(description) < 2:
            raise ValueError("Escribí una descripción")
        total = money_to_float(request.form.get("amount"))
        payment_method = request.form.get("payment_method", "cash")
        if payment_method not in PAYMENT_METHODS:
            raise ValueError("Medio de pago inválido")
    except ValueError as exc:
        flash(f"No se pudo registrar el gasto: {exc}", "error")
        return redirect(url_for("dashboard") + "#gastos-panel")

    get_db().execute(
        """
        INSERT INTO movements(cash_session_id, movement_type, category, sector, description, quantity, unit_price, total, payment_method, created_at, created_by)
        VALUES (?, 'expense', 'expense', 'admin', ?, 1, ?, ?, ?, ?, ?)
        """,
        (cash["id"], description[:180], total, total, payment_method, now_iso(), g.user["id"]),
    )
    get_db().commit()
    flash("Gasto registrado.", "success")
    return redirect(url_for("dashboard") + "#gastos-panel")


@app.post("/movements/<int:movement_id>/void")
@admin_required
def void_movement(movement_id):
    reason = request.form.get("reason", "Anulación administrativa").strip()[:180]
    db = get_db()
    movement = db.execute("SELECT * FROM movements WHERE id=?", (movement_id,)).fetchone()
    if not movement or movement["voided"]:
        abort(404)
    if movement["category"] == "champagne_speed":
        flash("El Speed incluido se anula junto con la venta de Champagne original.", "error")
        return redirect(request.referrer or url_for("dashboard"))
    voided_at = now_iso()
    db.execute(
        "UPDATE movements SET voided=1, voided_at=?, voided_by=?, void_reason=? WHERE id=?",
        (voided_at, g.user["id"], reason, movement_id),
    )
    db.execute(
        """UPDATE movements
           SET voided=1, voided_at=?, voided_by=?, void_reason=?
           WHERE voided=0 AND (
             linked_movement_id=?
             OR (category='champagne_speed' AND description LIKE ?)
           )""",
        (
            voided_at, g.user["id"], f"Anulado junto con movimiento #{movement_id}: {reason}"[:180],
            movement_id, f"%combo #{movement_id}%",
        ),
    )
    # v2.9.0: los componentes automáticos de combos viven fuera de movimientos.
    db.execute(
        """UPDATE beverage_stock_adjustments
           SET voided=1, voided_at=?, voided_by=?
           WHERE parent_movement_id=? AND voided=0""",
        (voided_at, g.user["id"], movement_id),
    )
    # Si era un ingreso por lista, liberar el nombre para que pueda corregirse y volver a registrarse.
    db.execute("DELETE FROM guest_checkins WHERE movement_id=?", (movement_id,))
    db.commit()
    flash("Movimiento anulado. Permanece visible en el historial.", "success")
    return redirect(request.referrer or url_for("dashboard"))


@app.post("/cash/close")
@admin_required
def close_cash():
    cash = get_open_cash_session()
    if not cash:
        flash("No hay una caja abierta.", "error")
        return redirect(url_for("dashboard"))
    try:
        declared_cash = money_to_float(request.form.get("declared_cash"))
        declared_mercadopago = money_to_float(request.form.get("declared_mercadopago", "0"))
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("dashboard"))
    totals, _ = session_totals(cash["id"])
    # expected_cash se conserva para compatibilidad histórica; el control real
    # de esta versión compara el total teórico con efectivo + Mercado Pago declarados.
    expected_cash = round(cash["opening_amount"] + totals["cash_sales"] - totals["cash_expenses"], 2)
    expected_total = round(cash["opening_amount"] + totals["sales"] - totals["expenses"], 2)
    declared_total = round(declared_cash + declared_mercadopago, 2)
    difference = round(declared_total - expected_total, 2)
    notes = request.form.get("notes", "").strip()[:500]
    db = get_db()
    db.execute(
        """
        UPDATE cash_sessions
        SET status='closed', closed_at=?, closed_by=?, declared_cash=?, declared_mercadopago=?, declared_total=?,
            expected_cash=?, expected_total=?, difference=?, notes=?
        WHERE id=?
        """,
        (now_iso(), g.user["id"], declared_cash, declared_mercadopago, declared_total, expected_cash, expected_total, difference, notes, cash["id"]),
    )
    renewed_qrs = rotate_promoter_qr_tokens(db)
    removed_guests, removed_checkins = clear_event_promoter_lists(db, cash["id"])
    db.commit()
    backup = make_backup()
    backup_message = "respaldo local creado" if backup else "datos guardados en la base cloud"
    flash(
        f"Caja cerrada y {backup_message}. Se eliminaron {removed_guests} nombres de listas y {removed_checkins} confirmaciones; {renewed_qrs} códigos QR renovados para la próxima jornada.",
        "success",
    )
    return redirect(url_for("session_detail", session_id=cash["id"]))


def make_backup():
    # En PostgreSQL los respaldos se gestionan en la plataforma cloud.
    if is_postgres_url(app.config.get("DATABASE_URL")):
        return None
    database_path = Path(app.config["DATABASE"])
    if not database_path.exists():
        return None
    BACKUP_DIR.mkdir(exist_ok=True)
    stamp = argentina_now().strftime("%Y%m%d_%H%M%S")
    target = BACKUP_DIR / f"floki_{stamp}.db"
    source = sqlite3.connect(database_path)
    destination = sqlite3.connect(target)
    try:
        with destination:
            source.backup(destination)
    finally:
        source.close()
        destination.close()
    backups = sorted(BACKUP_DIR.glob("floki_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in backups[30:]:
        old.unlink(missing_ok=True)
    return target


@app.post("/backup")
@admin_required
def manual_backup():
    target = make_backup()
    if target:
        flash(f"Respaldo local creado: {target.name}", "success")
    elif is_postgres_url(app.config.get("DATABASE_URL")):
        flash("La aplicación usa PostgreSQL: los respaldos se administran desde el proveedor cloud.", "success")
    else:
        flash("No se encontró la base de datos local.", "error")
    return redirect(url_for("settings"))


@app.route("/promoter-lists")
@ticketing_required
def promoter_lists():
    cash = get_open_cash_session()
    promoters = get_db().execute("SELECT * FROM promoters WHERE active=1 ORDER BY name COLLATE NOCASE").fetchall()
    query = request.args.get("q", "").strip()
    selected_promoter = request.args.get("promoter", "").strip()
    rows = []
    summary = []
    if cash:
        params = [cash["id"]]
        clauses = ["pg.cash_session_id=?"]
        if selected_promoter.isdigit():
            clauses.append("pg.promoter_id=?")
            params.append(int(selected_promoter))
        if query:
            _, normalized = normalize_guest_name(query)
            clauses.append("pg.normalized_name LIKE ?")
            params.append(f"%{normalized}%")
        rows = get_db().execute(
            f"""
            SELECT pg.*, p.name AS promoter_name, p.is_common, p.is_promo, p.is_birthday,
                   be.birthday_person_name, be.date_of_birth AS birthday_date_of_birth, be.max_people AS birthday_max_people,
                   gc.id AS checkin_id, gc.checked_in_at, cu.name AS checked_in_by_name, cp.name AS credited_promoter_name
            FROM promoter_guests pg
            JOIN promoters p ON p.id=pg.promoter_id
            LEFT JOIN birthday_events be ON be.cash_session_id=pg.cash_session_id AND be.promoter_id=p.id
            LEFT JOIN guest_checkins gc ON gc.cash_session_id=pg.cash_session_id AND gc.normalized_name=pg.normalized_name
            LEFT JOIN users cu ON cu.id=gc.checked_in_by
            LEFT JOIN promoters cp ON cp.id=gc.promoter_id
            WHERE {' AND '.join(clauses)}
            ORDER BY gc.id IS NOT NULL, pg.guest_name COLLATE NOCASE, p.name COLLATE NOCASE
            LIMIT 400
            """,
            params,
        ).fetchall()
        summary = get_db().execute(
            """
            SELECT p.id, p.name, p.is_common, p.is_promo, p.is_birthday, p.qr_token, p.qr_updated_at,
                   be.birthday_person_name, be.date_of_birth AS birthday_date_of_birth, be.max_people AS birthday_max_people,
                   COUNT(pg.id) AS listed_count, COUNT(gc.id) AS checked_count
            FROM promoters p
            JOIN promoter_guests pg ON pg.promoter_id=p.id AND pg.cash_session_id=?
            LEFT JOIN birthday_events be ON be.cash_session_id=pg.cash_session_id AND be.promoter_id=p.id
            LEFT JOIN guest_checkins gc ON gc.promoter_guest_id=pg.id
            GROUP BY p.id, p.name, p.is_common, p.is_promo, p.is_birthday, p.qr_token, p.qr_updated_at,
                     be.birthday_person_name, be.date_of_birth, be.max_people
            ORDER BY checked_count DESC, p.name COLLATE NOCASE
            """,
            (cash["id"],),
        ).fetchall()
    last_import = None
    workspace = None
    workspace_preview = []
    workspace_metadata = None
    if cash:
        workspace = get_db().execute("SELECT * FROM list_workspaces WHERE cash_session_id=?", (cash["id"],)).fetchone()
        if workspace and workspace["source_text"].strip():
            try:
                workspace_preview, workspace_metadata = parse_master_lines(workspace["source_text"].splitlines())
            except ValueError:
                workspace_preview, workspace_metadata = [], None
        last_import = get_db().execute(
            "SELECT li.*, u.name AS imported_by_name FROM list_imports li JOIN users u ON u.id=li.imported_by WHERE li.cash_session_id=? ORDER BY li.id DESC LIMIT 1",
            (cash["id"],),
        ).fetchone()
    return render_template(
        "promoter_lists.html",
        cash=cash,
        promoters=promoters,
        guests=rows,
        summary=summary,
        query=query,
        selected_promoter=selected_promoter,
        last_import=last_import,
        workspace=workspace,
        workspace_preview=workspace_preview,
        workspace_metadata=workspace_metadata,
    )


@app.post("/birthdays/create")
@admin_required
def create_birthday_list():
    cash = get_open_cash_session()
    if not cash:
        flash("Abrí un evento antes de crear un cumpleaños.", "error")
        return redirect(url_for("promoter_lists"))
    try:
        birthday_name, birthday_key = require_full_name(
            request.form.get("birthday_name", "").strip()[:120],
            "El nombre del cumpleañero",
        )
        birth_date_raw = request.form.get("birthday_date_of_birth", "").strip()
        if not birth_date_raw:
            raise ValueError("Ingresá la fecha de nacimiento del cumpleañero")
        birth_date = date.fromisoformat(birth_date_raw)
        if birth_date > date.today():
            raise ValueError("La fecha de nacimiento no puede ser futura")
        guest_names = parse_birthday_guest_names(request.form.get("birthday_guests", ""))
        guest_names = [(display, key) for display, key in guest_names if key != birthday_key]
        if len(guest_names) > 9:
            raise ValueError("El cumpleaños permite como máximo 9 amigos además del cumpleañero")
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("promoter_lists"))

    promoter_label = f"CUMPLEAÑOS - {birthday_name}"
    normalized = normalize_text_key(promoter_label)
    db = get_db()
    existing = find_promoter_by_key(db, normalized)
    if existing:
        promoter_id = existing["id"]
        db.execute(
            "UPDATE promoters SET name=?, normalized_name=?, active=1, is_common=0, is_promo=0, is_birthday=1 WHERE id=?",
            (promoter_label, normalized, promoter_id),
        )
        if not existing["qr_token"]:
            db.execute("UPDATE promoters SET qr_token=?, qr_updated_at=? WHERE id=?", (new_qr_token(), now_iso(), promoter_id))
    else:
        cursor = db.execute(
            "INSERT INTO promoters(name, normalized_name, active, is_common, is_promo, is_birthday, qr_token, qr_updated_at, created_at) VALUES (?, ?, 1, 0, 0, 1, ?, ?, ?)",
            (promoter_label, normalized, new_qr_token(), now_iso(), now_iso()),
        )
        promoter_id = cursor.lastrowid

    db.execute(
        """INSERT INTO birthday_events(cash_session_id, promoter_id, birthday_person_name, date_of_birth, max_people, confirmed_at, created_by)
           VALUES (?, ?, ?, ?, 10, ?, ?)
           ON CONFLICT(cash_session_id, promoter_id) DO UPDATE SET
             birthday_person_name=excluded.birthday_person_name,
             date_of_birth=excluded.date_of_birth,
             max_people=10,
             confirmed_at=excluded.confirmed_at,
             created_by=excluded.created_by""",
        (cash["id"], promoter_id, birthday_name, birth_date.isoformat(), now_iso(), g.user["id"]),
    )

    desired = [(birthday_name, birthday_key)] + guest_names
    desired_keys = {key for _display, key in desired}
    checked_keys = {
        row["normalized_name"]
        for row in db.execute(
            "SELECT normalized_name FROM guest_checkins WHERE cash_session_id=? AND promoter_id=?",
            (cash["id"], promoter_id),
        ).fetchall()
    }
    for existing_guest in db.execute(
        "SELECT id, normalized_name FROM promoter_guests WHERE cash_session_id=? AND promoter_id=?",
        (cash["id"], promoter_id),
    ).fetchall():
        if existing_guest["normalized_name"] not in desired_keys and existing_guest["normalized_name"] not in checked_keys:
            db.execute("DELETE FROM promoter_guests WHERE id=?", (existing_guest["id"],))

    for display, normalized_person in desired:
        db.execute(
            """INSERT OR IGNORE INTO promoter_guests(cash_session_id, promoter_id, guest_name, normalized_name, source_filename, imported_at, imported_by)
               VALUES (?, ?, ?, ?, 'Cumpleaños confirmado', ?, ?)""",
            (cash["id"], promoter_id, display, normalized_person, now_iso(), g.user["id"]),
        )
    db.commit()
    flash(
        f"Cumpleaños confirmado para {birthday_name}: FREE para la persona y hasta 9 amigos hasta las 03:30, 50% OFF en bebidas hasta las 03:00 y champagne + 2 Speed si ingresan 5 o más.",
        "success",
    )
    return redirect(url_for("promoter_lists", promoter=str(promoter_id)))


@app.post("/birthdays/<int:promoter_id>/redeem")
@login_required
def redeem_birthday_benefit(promoter_id):
    if g.user["role"] != "admin" and g.user["sector"] != "beverages":
        abort(403)
    cash = get_open_cash_session()
    if not cash:
        flash("No hay un evento abierto.", "error")
        return redirect(url_for("dashboard"))
    db = get_db()
    promoter = db.execute(
        """SELECT p.*, be.birthday_person_name, be.date_of_birth
           FROM promoters p
           JOIN birthday_events be ON be.promoter_id=p.id AND be.cash_session_id=?
           WHERE p.id=? AND p.is_birthday=1 AND p.active=1""",
        (cash["id"], promoter_id),
    ).fetchone()
    if not promoter:
        abort(404)
    if db.execute(
        "SELECT id FROM birthday_benefits WHERE cash_session_id=? AND promoter_id=?",
        (cash["id"], promoter_id),
    ).fetchone():
        flash("El beneficio de este cumpleaños ya fue entregado.", "error")
        return redirect(url_for("dashboard"))

    birthday_key = normalize_guest_name(promoter["birthday_person_name"])[1]
    attendance = db.execute(
        """SELECT COUNT(*) AS arrived,
                  COALESCE(MAX(CASE WHEN normalized_name=? THEN 1 ELSE 0 END), 0) AS birthday_checked
           FROM guest_checkins
           WHERE cash_session_id=? AND promoter_id=?""",
        (birthday_key, cash["id"], promoter_id),
    ).fetchone()
    arrived = int(attendance["arrived"] or 0)
    if not attendance["birthday_checked"]:
        flash("Primero debe registrarse el ingreso del cumpleañero o cumpleañera.", "error")
        return redirect(url_for("dashboard"))
    if arrived < BIRTHDAY_GIFT_MIN_CHECKINS:
        flash(
            f"El champagne + 2 Speed se habilita cuando ingresan {BIRTHDAY_GIFT_MIN_CHECKINS} o más. Por ahora ingresaron {arrived}.",
            "error",
        )
        return redirect(url_for("dashboard"))

    champagne = db.execute(
        """SELECT * FROM beverage_products
           WHERE active=1 AND (lower(beverage_type) LIKE '%espumante%' OR lower(name) LIKE '%champ%' OR lower(brand) LIKE '%chandon%')
           ORDER BY sort_order, id LIMIT 1"""
    ).fetchone()
    speed = db.execute(
        """SELECT * FROM beverage_products
           WHERE active=1 AND (lower(brand)='speed' OR lower(name) LIKE '%speed%')
           ORDER BY sort_order, id LIMIT 1"""
    ).fetchone()
    missing = []
    if not champagne:
        missing.append("Champagne/espumante")
    if not speed:
        missing.append("Speed")
    if missing:
        flash(f"Configurá en Bebidas estos productos antes de entregar la promo: {', '.join(missing)}.", "error")
        return redirect(url_for("dashboard"))

    try:
        stamp = now_iso()
        ensure_beverage_in_event_stock(db, cash["id"], champagne, g.user["id"])
        movement = db.execute(
            """INSERT INTO movements(
                   cash_session_id, movement_type, category, sector, description, quantity,
                   unit_price, total, payment_method, created_at, created_by, promoter_id,
                   beverage_product_id, stock_units
               ) VALUES (?, 'sale', 'birthday_benefit', 'beverages', ?, 1, 0, 0, 'other', ?, ?, ?, ?, ?)""",
            (cash["id"], "Promo cumpleaños · Champagne · incluye 2 Speed", stamp, g.user["id"], promoter_id, champagne["id"], beverage_stock_consumption(champagne, 1)),
        )
        add_champagne_speed_stock(
            db, cash, g.user, movement.lastrowid, champagne, 1,
            promoter_id=promoter_id, created_at=stamp,
        )
        db.execute(
            "INSERT INTO birthday_benefits(cash_session_id, promoter_id, redeemed_at, redeemed_by) VALUES (?, ?, ?, ?)",
            (cash["id"], promoter_id, stamp, g.user["id"]),
        )
        db.commit()
    except Exception:
        db.rollback()
        app.logger.exception("Error entregando combo de cumpleaños Champagne + 2 Speed")
        flash("No se pudo entregar el combo. No se descontó ningún producto; probá nuevamente.", "error")
        return redirect(url_for("dashboard"))
    flash(
        f"Beneficio entregado a {promoter['birthday_person_name']}: 1 champagne + 2 Speed. Ingresaron {arrived} personas de su lista.",
        "success",
    )
    return redirect(url_for("dashboard"))


@app.get("/promoter-lists/export.pdf")
@ticketing_required
def export_promoter_lists_pdf():
    cash = get_open_cash_session()
    if not cash:
        flash("Abrí un evento antes de exportar las listas.", "error")
        return redirect(url_for("promoter_lists"))
    order = "promoter"
    rows = get_db().execute(
        """SELECT pg.guest_name, p.name AS promoter_name, p.is_common, p.is_promo, p.is_birthday,
                  gc.id AS checkin_id, gc.checked_in_at,
                  be.birthday_person_name, be.date_of_birth AS birthday_date_of_birth
           FROM promoter_guests pg
           JOIN promoters p ON p.id=pg.promoter_id
           LEFT JOIN guest_checkins gc ON gc.cash_session_id=pg.cash_session_id AND gc.normalized_name=pg.normalized_name
           LEFT JOIN birthday_events be ON be.cash_session_id=pg.cash_session_id AND be.promoter_id=p.id
           WHERE pg.cash_session_id=?
           ORDER BY pg.guest_name COLLATE NOCASE, p.name COLLATE NOCASE""",
        (cash["id"],),
    ).fetchall()
    logo_path = BASE_DIR / "static" / "img" / "floki-logo-white.png"
    pdf_bytes = build_lists_pdf(dict(cash), [dict(row) for row in rows], order=order, logo_path=logo_path)
    safe_event = re.sub(r"[^A-Za-z0-9_-]+", "_", normalize_text_key(cash["event_name"])) or f"evento_{cash['id']}"
    filename = f"listas_{safe_event}_por_promotor.pdf"
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store, max-age=0",
        },
    )


@app.get("/promoter-lists/export.xlsx")
@ticketing_required
def export_promoter_lists_xlsx():
    cash = get_open_cash_session()
    if not cash:
        flash("Abrí un evento antes de exportar las listas.", "error")
        return redirect(url_for("promoter_lists"))
    rows = get_db().execute(
        """SELECT pg.guest_name, p.name AS promoter_name, p.is_common, p.is_promo, p.is_birthday,
                  gc.id AS checkin_id, gc.checked_in_at,
                  be.birthday_person_name, be.date_of_birth AS birthday_date_of_birth
           FROM promoter_guests pg
           JOIN promoters p ON p.id=pg.promoter_id
           LEFT JOIN guest_checkins gc ON gc.cash_session_id=pg.cash_session_id AND gc.normalized_name=pg.normalized_name
           LEFT JOIN birthday_events be ON be.cash_session_id=pg.cash_session_id AND be.promoter_id=p.id
           WHERE pg.cash_session_id=?
           ORDER BY pg.guest_name COLLATE NOCASE, p.name COLLATE NOCASE""",
        (cash["id"],),
    ).fetchall()
    export_rows = []
    for row in rows:
        item = dict(row)
        birthday_person_key = normalize_guest_name(item.get("birthday_person_name") or "")[1]
        item["is_birthday_person"] = bool(
            item.get("is_birthday")
            and birthday_person_key
            and normalize_guest_name(item.get("guest_name") or "")[1] == birthday_person_key
        )
        export_rows.append(item)
    workbook_bytes = build_lists_workbook(dict(cash), export_rows)
    safe_event = re.sub(r"[^A-Za-z0-9_-]+", "_", normalize_text_key(cash["event_name"])) or f"evento_{cash['id']}"
    filename = f"listas_{safe_event}_buscador_personas.xlsx"
    return Response(
        workbook_bytes,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store, max-age=0",
        },
    )


def save_list_workspace(db, cash_session_id, source_text, user_id):
    db.execute(
        """INSERT INTO list_workspaces(cash_session_id, source_text, updated_at, updated_by)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(cash_session_id) DO UPDATE SET source_text=excluded.source_text, updated_at=excluded.updated_at, updated_by=excluded.updated_by""",
        (cash_session_id, source_text[:100000], now_iso(), user_id),
    )


@app.post("/promoter-lists/workspace/apply")
@admin_required
def apply_list_workspace():
    cash = get_open_cash_session()
    if not cash:
        flash("Abrí un evento antes de convertir las listas.", "error")
        return redirect(url_for("dashboard"))
    source_text = request.form.get("source_text", "")
    mode = request.form.get("import_mode", "sync")
    if mode not in {"sync", "add"}:
        mode = "sync"
    db = get_db()
    try:
        save_list_workspace(db, cash["id"], source_text, g.user["id"])
        groups, metadata = parse_master_lines(source_text.splitlines())
        if not groups or metadata["guest_count"] == 0:
            db.commit()
            flash("El bloc fue guardado, pero todavía no contiene nombres reconocibles.", "error")
            return redirect(url_for("promoter_lists"))
        result = sync_master_list(db, cash["id"], "Panel inteligente", groups, metadata, g.user["id"], mode)
        db.execute("DELETE FROM list_workspaces WHERE cash_session_id=?", (cash["id"],))
        db.commit()
    except (ValueError, *DB_INTEGRITY_ERRORS) as exc:
        db.rollback()
        flash(str(exc) if isinstance(exc, ValueError) else "No se pudo convertir el bloc de listas.", "error")
        return redirect(url_for("promoter_lists"))
    flash(f"Listas convertidas: {result['guest_count']} nombres, {result['promoter_count']} promotores, {result['promo_count']} en PROMOS y {result['common_count']} en Lista común.", "success")
    return redirect(url_for("promoter_lists"))


@app.post("/api/list-workspace")
@admin_required
def autosave_list_workspace():
    cash = get_open_cash_session()
    if not cash:
        return jsonify({"ok": False, "error": "No hay evento abierto"}), 409
    payload = request.get_json(silent=True) or {}
    source_text = str(payload.get("source_text", ""))
    save_list_workspace(get_db(), cash["id"], source_text, g.user["id"])
    get_db().commit()
    return jsonify({"ok": True, "updated_at": now_iso()})


@app.post("/api/list-preview")
@admin_required
def preview_list_workspace():
    payload = request.get_json(silent=True) or {}
    source_text = str(payload.get("source_text", ""))
    groups, metadata = parse_master_lines(source_text.splitlines())
    preview = []
    for group in groups[:20]:
        preview.append({
            "promoter_name": group["promoter_name"] or COMMON_LIST_LABEL,
            "is_common": group["is_common"],
            "is_promo": group.get("is_promo", False),
            "guest_count": len(group["guests"]),
            "guests": [display for display, _ in group["guests"][:8]],
        })
    return jsonify({"ok": True, "metadata": metadata, "groups": preview})


@app.get("/api/guest-suggestions")
@ticketing_required
def guest_suggestions():
    cash = get_open_cash_session()
    query = request.args.get("q", "").strip()
    if not cash or not query:
        return jsonify({"suggestions": []})
    _, normalized = normalize_guest_name(query)
    if not normalized:
        return jsonify({"suggestions": []})
    rows = get_db().execute(
        """SELECT pg.id AS guest_id, pg.guest_name, pg.normalized_name, p.id AS promoter_id, p.name AS promoter_name, p.is_common, p.is_promo,
                  gc.id AS checkin_id, cp.name AS credited_promoter_name, gc.checked_in_at
           FROM promoter_guests pg
           JOIN promoters p ON p.id=pg.promoter_id
           LEFT JOIN guest_checkins gc ON gc.cash_session_id=pg.cash_session_id AND gc.normalized_name=pg.normalized_name
           LEFT JOIN promoters cp ON cp.id=gc.promoter_id
           WHERE pg.cash_session_id=? AND pg.normalized_name LIKE ?
           ORDER BY CASE WHEN pg.normalized_name LIKE ? THEN 0 ELSE 1 END, pg.guest_name COLLATE NOCASE, p.name COLLATE NOCASE
           LIMIT 80""",
        (cash["id"], f"%{normalized}%", f"{normalized}%"),
    ).fetchall()
    grouped = {}
    free_open_now = free_entry_available()
    for row in rows:
        item = grouped.setdefault(row["normalized_name"], {
            "name": row["guest_name"], "normalized_name": row["normalized_name"],
            "checked_in": bool(row["checkin_id"]), "credited_promoter_name": row["credited_promoter_name"],
            "checked_in_at": row["checked_in_at"], "lists": [],
        })
        is_common = bool(row["is_common"])
        is_promo = bool(row["is_promo"])
        free_available = free_open_now
        item["lists"].append({
            "guest_id": row["guest_id"], "promoter_id": row["promoter_id"],
            "promoter_name": row["promoter_name"], "is_common": is_common, "is_promo": is_promo,
            "free_available": free_available,
            "unavailable_reason": "La entrada FREE finalizó a las 03:30" if not free_available else "",
        })
    return jsonify({"suggestions": list(grouped.values())[:12]})

def sync_master_list(db, cash_session_id, filename, groups, metadata, imported_by, mode="sync"):
    common_id = ensure_common_promoter(db)
    promo_id = ensure_promo_promoter(db)
    desired = {}
    created_promoters = 0

    for group in groups:
        if group["is_common"]:
            promoter_id = common_id
        elif group.get("is_promo"):
            promoter_id = promo_id
        else:
            promoter_id, created = get_or_create_promoter(db, group["promoter_name"])
            created_promoters += int(created)
        for display, normalized in group["guests"]:
            desired[(promoter_id, normalized)] = display

    existing_rows = db.execute(
        "SELECT * FROM promoter_guests WHERE cash_session_id=?",
        (cash_session_id,),
    ).fetchall()
    existing = {(row["promoter_id"], row["normalized_name"]): row for row in existing_rows}

    added = updated = removed = retained_checked = 0
    stamp = now_iso()
    for key, display in desired.items():
        promoter_id, normalized = key
        row = existing.get(key)
        if row:
            db.execute(
                "UPDATE promoter_guests SET guest_name=?, source_filename=?, imported_at=?, imported_by=? WHERE id=?",
                (display, filename, stamp, imported_by, row["id"]),
            )
            updated += 1
        else:
            db.execute(
                """
                INSERT INTO promoter_guests(cash_session_id, promoter_id, guest_name, normalized_name, source_filename, imported_at, imported_by)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (cash_session_id, promoter_id, display, normalized, filename, stamp, imported_by),
            )
            added += 1

    if mode in {"sync", "smart"}:
        touched_promoter_ids = {promoter_id for promoter_id, _normalized in desired}
        for key, row in existing.items():
            if key in desired:
                continue
            if mode == "smart" and row["promoter_id"] not in touched_promoter_ids:
                continue
            checked = db.execute(
                "SELECT id FROM guest_checkins WHERE promoter_guest_id=? LIMIT 1",
                (row["id"],),
            ).fetchone()
            if checked:
                retained_checked += 1
            else:
                db.execute("DELETE FROM promoter_guests WHERE id=?", (row["id"],))
                removed += 1

    db.execute(
        """
        INSERT INTO list_imports(
            cash_session_id, source_filename, import_mode, promoter_count, promo_count, common_count, guest_count,
            added_count, removed_count, retained_checked_count, imported_at, imported_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            cash_session_id,
            filename,
            mode,
            metadata["promoter_count"],
            metadata.get("promo_count", 0),
            metadata["common_count"],
            metadata["guest_count"],
            added,
            removed,
            retained_checked,
            stamp,
            imported_by,
        ),
    )
    return {
        "added": added,
        "updated": updated,
        "removed": removed,
        "retained_checked": retained_checked,
        "created_promoters": created_promoters,
        "promoter_count": metadata["promoter_count"],
        "promo_count": metadata.get("promo_count", 0),
        "common_count": metadata["common_count"],
        "guest_count": metadata["guest_count"],
    }


@app.post("/promoter-lists/import-master")
@admin_required
def import_master_promoter_list():
    cash = get_open_cash_session()
    if not cash:
        flash("Abrí una caja antes de actualizar el archivo maestro.", "error")
        return redirect(url_for("promoter_lists"))
    uploaded = request.files.get("master_file")
    mode = request.form.get("import_mode", "sync")
    if mode not in {"sync", "add"}:
        mode = "sync"
    try:
        if not uploaded or not uploaded.filename:
            raise ValueError("Seleccioná el archivo maestro exportado desde WPS")
        filename, groups, metadata = parse_master_file(uploaded)
        db = get_db()
        result = sync_master_list(db, cash["id"], filename, groups, metadata, g.user["id"], mode)
        db.execute("DELETE FROM list_workspaces WHERE cash_session_id=?", (cash["id"],))
        db.commit()
    except (ValueError, *DB_INTEGRITY_ERRORS) as exc:
        get_db().rollback()
        flash(str(exc) if isinstance(exc, ValueError) else "No se pudo actualizar la lista maestra.", "error")
        return redirect(url_for("promoter_lists"))

    mode_text = "sincronizado" if mode == "sync" else "agregado"
    flash(
        f"Archivo {mode_text}: {result['guest_count']} nombres, {result['promoter_count']} promotores, "
        f"{result['promo_count']} en PROMOS y {result['common_count']} en lista común. Nuevos: {result['added']}; retirados: {result['removed']}; "
        f"promotores creados: {result['created_promoters']}.",
        "success",
    )
    return redirect(url_for("promoter_lists"))


@app.post("/promoter-lists/quick-import")
@admin_required
def quick_import_promoter_lists():
    """Carga simplificada desde texto, PDF o DOCX y limpia el panel al terminar."""
    cash = get_open_cash_session()
    return_to = request.form.get("return_to", "dashboard")
    redirect_endpoint = "promoter_lists" if return_to == "promoter_lists" else "dashboard"
    if not cash:
        flash("Abrí un evento antes de cargar las listas.", "error")
        return redirect(url_for(redirect_endpoint))

    source_text = request.form.get("source_text", "").strip()
    uploaded = request.files.get("master_file")
    mode = "smart"
    try:
        if uploaded and uploaded.filename:
            extension = Path(uploaded.filename).suffix.lower()
            if extension not in {".pdf", ".docx"}:
                raise ValueError("En el panel inteligente usá solamente PDF o DOCX")
            filename, groups, metadata = parse_master_file(uploaded)
        elif source_text:
            filename = "Texto pegado en panel inteligente"
            groups, metadata = parse_master_lines(source_text.splitlines())
        else:
            raise ValueError("Pegá el mensaje de listas o seleccioná un archivo PDF/DOCX")
        if not groups or metadata["guest_count"] == 0:
            raise ValueError("No se encontraron nombres reconocibles")
        db = get_db()
        result = sync_master_list(db, cash["id"], filename, groups, metadata, g.user["id"], mode)
        db.execute("DELETE FROM list_workspaces WHERE cash_session_id=?", (cash["id"],))
        db.commit()
    except (ValueError, *DB_INTEGRITY_ERRORS) as exc:
        get_db().rollback()
        flash(str(exc) if isinstance(exc, ValueError) else "No se pudieron cargar las listas.", "error")
        return redirect(url_for(redirect_endpoint))

    flash(
        f"Listas listas: {result['guest_count']} personas, {result['promoter_count']} promotores, "
        f"{result['promo_count']} en PROMOS y {result['common_count']} en Lista común. El panel quedó vacío.",
        "success",
    )
    return redirect(url_for(redirect_endpoint))


@app.route("/promoter-qrs")
@ticketing_required
def promoter_qrs():
    cash = get_open_cash_session()
    cash_id = cash["id"] if cash else 0
    promoters = get_db().execute(
        """
        SELECT p.*, COUNT(pg.id) AS listed_count
        FROM promoters p
        LEFT JOIN promoter_guests pg ON pg.promoter_id=p.id AND pg.cash_session_id=?
        WHERE p.active=1 AND p.is_common=0 AND p.is_promo=0
        GROUP BY p.id
        ORDER BY p.name COLLATE NOCASE
        """,
        (cash_id,),
    ).fetchall()
    return render_template("promoter_qrs.html", promoters=promoters, cash=cash)


@app.route("/qr/<token>.png")
def promoter_qr_image(token):
    promoter = get_db().execute(
        "SELECT * FROM promoters WHERE qr_token=? AND active=1 AND is_common=0 AND is_promo=0",
        (token,),
    ).fetchone()
    if not promoter:
        abort(404)
    destination = promoter_public_url(token)
    image = qrcode.make(destination)
    output = io.BytesIO()
    image.save(output, format="PNG")
    headers = {"Cache-Control": "no-store, max-age=0"}
    if request.args.get("download") == "1":
        safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", normalize_text_key(promoter["name"])) or f"promotor_{promoter['id']}"
        headers["Content-Disposition"] = f'attachment; filename="qr_{safe_name}.png"'
    return Response(output.getvalue(), mimetype="image/png", headers=headers)


@app.route("/p/<token>")
def promoter_qr_landing(token):
    promoter = get_db().execute(
        "SELECT * FROM promoters WHERE qr_token=? AND active=1 AND is_common=0 AND is_promo=0",
        (token,),
    ).fetchone()
    if not promoter:
        return render_template("qr_landing.html", promoter=None, cash=None, listed_count=0), 404
    cash = get_open_cash_session()
    listed_count = 0
    if cash:
        listed_count = get_db().execute(
            "SELECT COUNT(*) FROM promoter_guests WHERE cash_session_id=? AND promoter_id=?",
            (cash["id"], promoter["id"]),
        ).fetchone()[0]
    if g.user and cash and (g.user["role"] == "admin" or g.user["sector"] == "ticketing"):
        flash(f"QR válido: {promoter['name']}. Se abrió su lista para buscar y confirmar el nombre.", "success")
        return redirect(url_for("promoter_lists", promoter=promoter["id"]))
    return render_template("qr_landing.html", promoter=promoter, cash=cash, listed_count=listed_count)


@app.post("/promoter-lists/import")
@admin_required
def import_promoter_list():
    cash = get_open_cash_session()
    if not cash:
        flash("Abrí una caja antes de cargar las listas del evento.", "error")
        return redirect(url_for("promoter_lists"))
    try:
        promoter_id = positive_int(request.form.get("promoter_id"), "El promotor", maximum=100000)
        promoter = get_db().execute("SELECT * FROM promoters WHERE id=? AND active=1", (promoter_id,)).fetchone()
        if not promoter:
            raise ValueError("Promotor inválido")
        uploaded = request.files.get("guest_file")
        if not uploaded or not uploaded.filename:
            raise ValueError("Seleccioná el archivo de la lista")
        filename, parsed = parse_guest_file(uploaded)
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("promoter_lists"))

    db = get_db()
    if promoter["is_birthday"]:
        try:
            birthday_profile = db.execute(
                "SELECT * FROM birthday_events WHERE cash_session_id=? AND promoter_id=?",
                (cash["id"], promoter_id),
            ).fetchone()
            if not birthday_profile:
                raise ValueError("Primero creá y confirmá el cumpleaños con nombre completo y fecha de nacimiento")
            existing_keys = {
                row["normalized_name"]
                for row in db.execute(
                    "SELECT normalized_name FROM promoter_guests WHERE cash_session_id=? AND promoter_id=?",
                    (cash["id"], promoter_id),
                ).fetchall()
            }
            validated = []
            for display, normalized in parsed:
                full_display, full_key = require_full_name(display, "Cada integrante")
                if full_key not in existing_keys and all(full_key != key for _name, key in validated):
                    validated.append((full_display, full_key))
            available = max(0, int(birthday_profile["max_people"] or 10) - len(existing_keys))
            if len(validated) > available:
                raise ValueError(f"La lista de cumpleaños permite 10 personas en total. Quedan {available} lugares disponibles")
            parsed = validated
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("promoter_lists", promoter=promoter_id))

    inserted = duplicates = 0
    for display, normalized in parsed:
        try:
            db.execute(
                """
                INSERT INTO promoter_guests(cash_session_id, promoter_id, guest_name, normalized_name, source_filename, imported_at, imported_by)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (cash["id"], promoter_id, display, normalized, filename, now_iso(), g.user["id"]),
            )
            inserted += 1
        except DB_INTEGRITY_ERRORS:
            duplicates += 1
    db.commit()
    flash(f"Lista de {promoter['name']} cargada: {inserted} nombres nuevos, {duplicates} repetidos dentro de su lista.", "success")
    return redirect(url_for("promoter_lists", promoter=promoter_id))


def perform_guest_checkin(db, cash, user, guest_id, *, created_at=None):
    if user["role"] != "admin" and (user["sector"] or "ticketing") != "ticketing":
        raise PermissionError("Tu usuario no puede confirmar ingresos")
    guest = db.execute(
        """SELECT pg.*, p.name AS promoter_name, p.is_common, p.is_promo FROM promoter_guests pg
           JOIN promoters p ON p.id=pg.promoter_id WHERE pg.id=? AND pg.cash_session_id=?""",
        (guest_id, cash["id"]),
    ).fetchone()
    if not guest:
        raise ValueError("La persona ya no pertenece al evento abierto")
    operation_dt = operation_datetime(created_at)
    if not free_entry_available(operation_dt):
        raise ValueError("La entrada FREE finalizó a las 03:30")
    existing = db.execute(
        """SELECT gc.*, p.name AS promoter_name FROM guest_checkins gc
           JOIN promoters p ON p.id=gc.promoter_id
           WHERE gc.cash_session_id=? AND gc.normalized_name=?""",
        (cash["id"], guest["normalized_name"]),
    ).fetchone()
    if existing:
        raise ValueError(f"{guest['guest_name']} ya ingresó y quedó acreditado a {existing['promoter_name']}")
    try:
        cursor = db.execute(
            """
            INSERT INTO guest_checkins(cash_session_id, promoter_guest_id, promoter_id, guest_name, normalized_name, checked_in_at, checked_in_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (cash["id"], guest["id"], guest["promoter_id"], guest["guest_name"], guest["normalized_name"], operation_dt.isoformat(sep=" "), user["id"]),
        )
        checkin_id = cursor.lastrowid
        movement = db.execute(
            """
            INSERT INTO movements(cash_session_id, movement_type, category, sector, description, quantity, unit_price, total, payment_method, created_at, created_by, promoter_id)
            VALUES (?, 'sale', 'free', 'ticketing', ?, 1, 0, 0, 'other', ?, ?, ?)
            """,
            (cash["id"], f"Lista: {guest['guest_name']}", operation_dt.isoformat(sep=" "), user["id"], guest["promoter_id"]),
        )
        db.execute("UPDATE guest_checkins SET movement_id=? WHERE id=?", (movement.lastrowid, checkin_id))
    except DB_INTEGRITY_ERRORS as exc:
        raise ValueError("Ese nombre ya había sido ingresado en esta jornada") from exc
    return {
        "checkin_id": checkin_id,
        "movement_id": movement.lastrowid,
        "guest_name": guest["guest_name"],
        "promoter_name": guest["promoter_name"],
        "message": f"Ingreso confirmado: {guest['guest_name']} · {guest['promoter_name']}.",
    }


@app.post("/promoter-lists/<int:guest_id>/check-in")
@ticketing_required
def check_in_guest(guest_id):
    cash = get_open_cash_session()
    if not cash:
        flash("No hay una caja abierta.", "error")
        return redirect(url_for("promoter_lists"))
    try:
        result = perform_guest_checkin(get_db(), cash, g.user, guest_id)
        get_db().commit()
        flash(result["message"], "success")
    except PermissionError:
        abort(403)
    except ValueError as exc:
        get_db().rollback()
        flash(str(exc), "error")
    return redirect(request.referrer or url_for("promoter_lists"))


@app.post("/promoter-lists/<int:guest_id>/delete")
@admin_required
def delete_guest(guest_id):
    guest = get_db().execute("SELECT * FROM promoter_guests WHERE id=?", (guest_id,)).fetchone()
    if not guest:
        abort(404)
    checked = get_db().execute("SELECT id FROM guest_checkins WHERE promoter_guest_id=?", (guest_id,)).fetchone()
    if checked:
        flash("No se puede eliminar una persona que ya ingresó.", "error")
    else:
        get_db().execute("DELETE FROM promoter_guests WHERE id=?", (guest_id,))
        get_db().commit()
        flash("Nombre eliminado de la lista.", "success")
    return redirect(request.referrer or url_for("promoter_lists"))




def match_imported_beverage(db, item):
    rows = db.execute("SELECT * FROM beverage_products WHERE active=1 ORDER BY id").fetchall()
    raw_key = normalize_stock_text(item["raw_name"])
    exact = None
    if item["beverage_type"] != "Otro":
        exact_name = build_beverage_name(item["beverage_type"], item["brand"], item["presentation"])
        exact = next((row for row in rows if normalize_stock_text(row["name"]) == normalize_stock_text(exact_name)), None)
    if exact:
        return exact

    best = None
    best_score = 0.0
    raw_tokens = set(raw_key.split())
    for row in rows:
        row_key = normalize_stock_text(row["name"])
        if raw_key == row_key or (raw_key and (raw_key in row_key or row_key in raw_key)):
            return row
        row_tokens = set(row_key.split())
        if not raw_tokens or not row_tokens:
            continue
        score = len(raw_tokens & row_tokens) / len(raw_tokens | row_tokens)
        if item["brand"] != "Sin marca" and normalize_stock_text(item["brand"]) in row_key:
            score += 0.25
        if item["presentation"] != "unidad" and normalize_stock_text(item["presentation"]) in row_key:
            score += 0.15
        if score > best_score:
            best, best_score = row, score
    return best if best_score >= 0.62 else None


def create_imported_beverage(db, item):
    beverage_type = item["beverage_type"]
    brand = item["brand"]
    presentation = item["presentation"]
    if beverage_type == "Otro":
        name = re.sub(r"\s+", " ", item["raw_name"].strip()).title()[:80]
        beverage_type = name[:40]
        brand = "Sin marca"
    else:
        name = build_beverage_name(beverage_type, brand, presentation)

    duplicate = db.execute("SELECT * FROM beverage_products WHERE active=1 AND lower(name)=lower(?)", (name,)).fetchone()
    if duplicate:
        db.execute("UPDATE beverage_products SET active=1, updated_at=? WHERE id=?", (now_iso(), duplicate["id"]))
        return db.execute("SELECT * FROM beverage_products WHERE id=?", (duplicate["id"],)).fetchone()

    similar = db.execute(
        "SELECT price FROM beverage_products WHERE beverage_type=? AND brand=? ORDER BY active DESC, id DESC LIMIT 1",
        (beverage_type, brand),
    ).fetchone()
    price = float(similar["price"]) if similar else 1000.0
    max_order = db.execute("SELECT COALESCE(MAX(sort_order), 0) FROM beverage_products").fetchone()[0]
    approx_yield = suggested_approx_yield(item["stock_unit"], presentation, beverage_type, brand, name)
    cursor = db.execute(
        """INSERT INTO beverage_products(
               name, price, stock_unit, sale_unit, servings_per_stock_unit, approx_yield,
               beverage_type, brand, presentation, active, sort_order, updated_at
           ) VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, 1, ?, ?)""",
        (name, price, item["stock_unit"], presentation, approx_yield, beverage_type, brand, presentation, int(max_order or 0) + 10, now_iso()),
    )
    return db.execute("SELECT * FROM beverage_products WHERE id=?", (cursor.lastrowid,)).fetchone()


@app.post("/stock/import")
@admin_required
def import_stock():
    cash = get_open_cash_session()
    return_to = request.form.get("return_to", "stock")
    redirect_endpoint = "dashboard" if return_to == "dashboard" else "stock"
    if not cash:
        flash("Abrí un evento antes de cargar el stock.", "error")
        return redirect(url_for("dashboard"))
    uploaded = request.files.get("stock_file")
    try:
        if not uploaded or not uploaded.filename:
            raise ValueError("Seleccioná el archivo PDF o Excel con el stock")
        filename, items = parse_stock_file(uploaded, BEVERAGE_BRAND_OPTIONS)
        db = get_db()
        matched = created = 0
        for item in items:
            product = match_imported_beverage(db, item)
            if product:
                matched += 1
                if not product["active"]:
                    db.execute("UPDATE beverage_products SET active=1, updated_at=? WHERE id=?", (now_iso(), product["id"]))
                    product = db.execute("SELECT * FROM beverage_products WHERE id=?", (product["id"],)).fetchone()
            else:
                product = create_imported_beverage(db, item)
                created += 1
            ensure_beverage_in_event_stock(db, cash["id"], product, g.user["id"])
            if item.get("final_quantity") is None:
                db.execute(
                    """UPDATE beverage_stock
                       SET initial_quantity=?, beverage_name=?, updated_at=?, updated_by=?
                       WHERE cash_session_id=? AND beverage_id=?""",
                    (item["initial_quantity"], product["name"], now_iso(), g.user["id"], cash["id"], product["id"]),
                )
            else:
                db.execute(
                    """UPDATE beverage_stock
                       SET initial_quantity=?, final_quantity=?, beverage_name=?, updated_at=?, updated_by=?
                       WHERE cash_session_id=? AND beverage_id=?""",
                    (item["initial_quantity"], item["final_quantity"], product["name"], now_iso(), g.user["id"], cash["id"], product["id"]),
                )
        db.commit()
    except (ValueError, *DB_INTEGRITY_ERRORS) as exc:
        get_db().rollback()
        flash(str(exc) if isinstance(exc, ValueError) else "No se pudo importar el stock.", "error")
        return redirect(url_for(redirect_endpoint))

    flash(
        f"Stock cargado desde {filename}: {len(items)} productos procesados; {matched} vinculados y {created} variantes nuevas. "
        "Revisá las variantes nuevas antes de venderlas.",
        "success",
    )
    return redirect(url_for(redirect_endpoint))


@app.route("/stock")
@login_required
def stock():
    if g.user["role"] != "admin" and current_sector() != "beverages":
        abort(403)
    requested_id = request.args.get("session_id", "").strip()
    cash = None
    if requested_id and g.user["role"] == "admin":
        try:
            session_id = positive_int(requested_id, "El evento", maximum=1000000)
        except ValueError:
            abort(404)
        cash = get_db().execute("SELECT * FROM cash_sessions WHERE id=?", (session_id,)).fetchone()
    else:
        cash = get_open_cash_session()
    if not cash:
        flash("No hay un evento disponible para controlar stock.", "error")
        return redirect(url_for("dashboard"))
    db = get_db()
    if cash["status"] == "open":
        initialize_event_stock(db, cash["id"], g.user["id"])
        db.commit()
    rows = stock_view_rows(cash["id"])
    stock_groups = [{"label": label, "items": [row for row in rows if row.get("category_group") == label]} for label in BEVERAGE_CATEGORY_OPTIONS]
    stock_groups = [group for group in stock_groups if group["items"]]
    return render_template("stock.html", cash=cash, stock_rows=rows, stock_groups=stock_groups, stock_admin_view=g.user["role"] == "admin")


@app.post("/stock/update")
@login_required
def update_stock():
    if g.user["role"] != "admin" and current_sector() != "beverages":
        abort(403)
    cash = get_open_cash_session()
    requested_id = request.form.get("session_id", "").strip()
    if requested_id and g.user["role"] == "admin":
        try:
            requested_session_id = positive_int(requested_id, "El evento", maximum=1000000)
        except ValueError:
            abort(404)
        cash = get_db().execute("SELECT * FROM cash_sessions WHERE id=?", (requested_session_id,)).fetchone()
    if not cash:
        flash("No se encontró el evento.", "error")
        return redirect(url_for("dashboard"))
    db = get_db()
    rows = db.execute(
        """SELECT bs.* FROM beverage_stock bs
           JOIN beverage_products bp ON bp.id=bs.beverage_id
           WHERE bs.cash_session_id=? AND bp.active=1""",
        (cash["id"],),
    ).fetchall()
    try:
        for row in rows:
            initial = non_negative_number(request.form.get(f"initial_{row['id']}", "0") or "0", "La cantidad inicial", maximum=100000)
            final_raw = request.form.get(f"final_{row['id']}", "").strip()
            final = None if final_raw == "" else non_negative_number(final_raw, "La cantidad final", maximum=100000)
            db.execute(
                "UPDATE beverage_stock SET initial_quantity=?, final_quantity=?, updated_at=?, updated_by=? WHERE id=?",
                (initial, final, now_iso(), g.user["id"], row["id"]),
            )
        db.commit()
        flash("Planilla de stock actualizada.", "success")
    except ValueError as exc:
        db.rollback()
        flash(str(exc), "error")
    return redirect(url_for("stock", session_id=cash["id"] if cash["status"] == "closed" else None))


@app.route("/stock/template.xlsx")
@admin_required
def download_stock_template_xlsx():
    cash = get_open_cash_session()
    if not cash:
        flash("Abrí un evento antes de descargar la planilla de conteo.", "error")
        return redirect(url_for("dashboard"))
    db = get_db()
    initialize_event_stock(db, cash["id"], g.user["id"])
    db.commit()
    rows = stock_view_rows(cash["id"])
    payload = build_stock_template_workbook(cash["event_name"], cash["event_date"], rows)
    filename = f"planilla_stock_floki_{cash['event_date']}_evento_{cash['id']}.xlsx"
    return Response(payload, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f"attachment; filename={filename}"})


@app.route("/stock/export.xlsx")
@admin_required
def export_stock_xlsx():
    requested_id = request.args.get("session_id", "").strip()
    if requested_id:
        try:
            requested_session_id = positive_int(requested_id, "El evento", maximum=1000000)
        except ValueError:
            abort(404)
        cash = get_db().execute("SELECT * FROM cash_sessions WHERE id=?", (requested_session_id,)).fetchone()
    else:
        cash = get_open_cash_session()
    if not cash:
        abort(404)
    db = get_db()
    initialize_event_stock(db, cash["id"], g.user["id"])
    db.commit()
    rows = stock_view_rows(cash["id"])
    payload = build_stock_workbook(cash["event_name"], cash["event_date"], rows)
    filename = f"stock_floki_{cash['event_date']}_evento_{cash['id']}.xlsx"
    return Response(payload, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f"attachment; filename={filename}"})


@app.route("/beverages/history")
@beverages_required
def beverage_history():
    """Historial completo del sector Bebidas sin exponer ganancias acumuladas."""
    db = get_db()
    event_value = request.args.get("event", "").strip()
    kind = request.args.get("kind", "all").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    try:
        page = max(1, int(request.args.get("page", "1") or 1))
    except (TypeError, ValueError):
        page = 1
    page_size = 100

    clauses = ["m.sector='beverages'", "m.movement_type='sale'", "m.category<>'champagne_speed'"]
    params = []
    selected_event = None
    if event_value:
        try:
            selected_event = int(event_value)
        except ValueError:
            selected_event = None
        if selected_event:
            clauses.append("m.cash_session_id=?")
            params.append(selected_event)
    if date_from:
        clauses.append("date(cs.event_date) >= date(?)")
        params.append(date_from)
    if date_to:
        clauses.append("date(cs.event_date) <= date(?)")
        params.append(date_to)
    if kind == "paid":
        clauses.append("m.total>0")
    elif kind == "benefit":
        clauses.append("m.total=0")
        clauses.append("m.category IN ('rrpp_benefit','birthday_benefit')")
    elif kind == "voided":
        clauses.append("m.voided=1")
    else:
        kind = "all"

    where_sql = " AND ".join(clauses)
    total_row = db.execute(
        f"""SELECT COUNT(*) AS total
            FROM movements m
            JOIN cash_sessions cs ON cs.id=m.cash_session_id
            WHERE {where_sql}""",
        params,
    ).fetchone()
    total_records = int(total_row["total"] or 0)
    total_pages = max(1, (total_records + page_size - 1) // page_size)
    page = min(page, total_pages)
    offset = (page - 1) * page_size

    movements = db.execute(
        f"""SELECT m.*, cs.event_name, cs.event_date, cs.status AS event_status,
                   u.name AS user_name, bp.name AS beverage_name
            FROM movements m
            JOIN cash_sessions cs ON cs.id=m.cash_session_id
            JOIN users u ON u.id=m.created_by
            LEFT JOIN beverage_products bp ON bp.id=m.beverage_product_id
            WHERE {where_sql}
            ORDER BY m.id DESC
            LIMIT ? OFFSET ?""",
        [*params, page_size, offset],
    ).fetchall()

    events = db.execute(
        """SELECT DISTINCT cs.id, cs.event_name, cs.event_date, cs.status
           FROM cash_sessions cs
           JOIN movements m ON m.cash_session_id=cs.id
           WHERE m.sector='beverages' AND m.movement_type='sale' AND m.category<>'champagne_speed'
           ORDER BY cs.id DESC
           LIMIT 250"""
    ).fetchall()

    return render_template(
        "beverage_history.html",
        movements=movements, events=events, total_records=total_records, page=page, total_pages=total_pages,
        filters={"event": str(selected_event or ""), "kind": kind, "date_from": date_from, "date_to": date_to},
    )


@app.route("/history")
@admin_required
def history():
    date_from = request.args.get("from", "").strip()
    date_to = request.args.get("to", "").strip()
    status = request.args.get("status", "").strip()
    clauses = ["1=1"]
    params = []
    if date_from:
        clauses.append("date(cs.event_date) >= date(?)")
        params.append(date_from)
    if date_to:
        clauses.append("date(cs.event_date) <= date(?)")
        params.append(date_to)
    if status in {"open", "closed"}:
        clauses.append("cs.status=?")
        params.append(status)
    sessions = get_db().execute(
        f"""
        SELECT cs.*, u.name AS opened_by_name,
               COALESCE(SUM(CASE WHEN m.movement_type='sale' AND m.voided=0 THEN m.total ELSE 0 END), 0) AS sales,
               COALESCE(SUM(CASE WHEN m.movement_type='expense' AND m.voided=0 THEN m.total ELSE 0 END), 0) AS expenses,
               COALESCE(SUM(CASE WHEN m.movement_type='sale' AND m.category IN ('general','advance','vip','free') AND m.voided=0 THEN m.quantity ELSE 0 END), 0) AS people_count
        FROM cash_sessions cs
        JOIN users u ON u.id=cs.opened_by
        LEFT JOIN movements m ON m.cash_session_id=cs.id
        WHERE {' AND '.join(clauses)}
        GROUP BY cs.id, u.name
        ORDER BY cs.id DESC
        LIMIT 200
        """,
        params,
    ).fetchall()
    return render_template("history.html", sessions=sessions, filters={"from": date_from, "to": date_to, "status": status})


@app.post("/history/<int:session_id>/delete")
@admin_required
def delete_cash_session(session_id):
    db = get_db()
    cash = db.execute("SELECT * FROM cash_sessions WHERE id=?", (session_id,)).fetchone()
    if not cash:
        abort(404)
    if cash["status"] == "open":
        flash("No se puede borrar un evento que todavía está abierto. Cerralo primero.", "error")
        return redirect(url_for("history"))
    backup = make_backup()
    try:
        db.execute("BEGIN")
        db.execute("DELETE FROM guest_checkins WHERE cash_session_id=?", (session_id,))
        db.execute("DELETE FROM promoter_guests WHERE cash_session_id=?", (session_id,))
        db.execute("DELETE FROM list_imports WHERE cash_session_id=?", (session_id,))
        db.execute("DELETE FROM list_workspaces WHERE cash_session_id=?", (session_id,))
        db.execute("DELETE FROM birthday_benefits WHERE cash_session_id=?", (session_id,))
        db.execute("DELETE FROM birthday_events WHERE cash_session_id=?", (session_id,))
        db.execute("DELETE FROM beverage_stock_adjustments WHERE cash_session_id=?", (session_id,))
        db.execute("DELETE FROM beverage_stock WHERE cash_session_id=?", (session_id,))
        db.execute("DELETE FROM movements WHERE cash_session_id=?", (session_id,))
        db.execute("DELETE FROM cash_sessions WHERE id=?", (session_id,))
        db.commit()
    except Exception:
        db.rollback()
        raise
    backup_note = "Se creó un respaldo local previo." if backup else "La eliminación quedó registrada en la base cloud."
    flash(f"Evento {cash['event_name']} eliminado del historial. {backup_note}", "success")
    return redirect(url_for("history"))


@app.route("/history/<int:session_id>")
@admin_required
def session_detail(session_id):
    cash = get_db().execute(
        """
        SELECT cs.*, u.name AS opened_by_name, c.name AS closed_by_name
        FROM cash_sessions cs
        JOIN users u ON u.id=cs.opened_by
        LEFT JOIN users c ON c.id=cs.closed_by
        WHERE cs.id=?
        """,
        (session_id,),
    ).fetchone()
    if not cash:
        abort(404)
    movement_type = request.args.get("type", "")
    payment_method = request.args.get("payment", "")
    totals, by_payment = session_totals(session_id)
    movements = session_movements(session_id, movement_type=movement_type, payment_method=payment_method, benefits_last=True)
    calculated_total = cash["opening_amount"] + totals["sales"] - totals["expenses"]
    if cash["status"] == "closed" and cash["expected_total"] is not None:
        expected_total = float(cash["expected_total"])
    elif cash["status"] == "closed" and cash["expected_cash"] is not None:
        # Eventos cerrados con versiones anteriores conservan su criterio histórico.
        expected_total = float(cash["expected_cash"])
    else:
        expected_total = calculated_total
    promoters = promoter_totals(session_id)
    inventory = stock_view_rows(session_id)
    return render_template(
        "session_detail.html",
        cash=cash,
        totals=totals,
        by_payment=by_payment,
        movements=movements,
        expected_total=expected_total,
        promoters=promoters,
        inventory=inventory,
        filters={"type": movement_type, "payment": payment_method},
    )


@app.route("/history/<int:session_id>/print")
@admin_required
def session_print(session_id):
    cash = get_db().execute(
        """
        SELECT cs.*, u.name AS opened_by_name, c.name AS closed_by_name
        FROM cash_sessions cs
        JOIN users u ON u.id=cs.opened_by
        LEFT JOIN users c ON c.id=cs.closed_by
        WHERE cs.id=?
        """,
        (session_id,),
    ).fetchone()
    if not cash:
        abort(404)
    totals, by_payment = session_totals(session_id)
    movements = session_movements(session_id, benefits_last=True)
    promoters = promoter_totals(session_id)
    inventory = stock_view_rows(session_id)
    return render_template("print_report.html", cash=cash, totals=totals, by_payment=by_payment, movements=movements, promoters=promoters, inventory=inventory)


@app.route("/history/<int:session_id>/export.csv")
@admin_required
def export_session_csv(session_id):
    cash = get_db().execute("SELECT * FROM cash_sessions WHERE id=?", (session_id,)).fetchone()
    if not cash:
        abort(404)
    movements = session_movements(session_id, benefits_last=True)
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(["Floki Manager", f"Caja #{session_id}", cash["event_name"]])
    writer.writerow(["Fecha", "Sector", "Tipo", "Categoría", "Descripción", "Cantidad", "Precio unitario", "Total", "Medio de pago", "Promotor", "Usuario", "Anulado"])
    for row in movements:
        writer.writerow(
            [
                row["created_at"],
                SECTOR_LABELS.get(row["sector"], row["sector"]),
                "Venta" if row["movement_type"] == "sale" else "Gasto",
                CATEGORY_LABELS.get(row["category"], row["category"]),
                row["description"] or "",
                row["quantity"],
                f"{row['unit_price']:.2f}",
                f"{row['total']:.2f}",
                PAYMENT_LABELS.get(row["payment_method"], row["payment_method"]),
                row["promoter_name"] or "",
                row["user_name"],
                "Sí" if row["voided"] else "No",
            ]
        )
    filename = f"floki_caja_{session_id}.csv"
    return Response("\ufeff" + buffer.getvalue(), mimetype="text/csv; charset=utf-8", headers={"Content-Disposition": f"attachment; filename={filename}"})


@app.route("/settings")
@login_required
def settings():
    if g.user["role"] == "admin":
        users = get_db().execute("SELECT * FROM users ORDER BY active DESC, name COLLATE NOCASE").fetchall()
        promoters = get_db().execute("SELECT * FROM promoters WHERE is_common=0 AND is_promo=0 ORDER BY active DESC, name COLLATE NOCASE").fetchall()
        entry_prices = get_db().execute("SELECT * FROM entry_prices WHERE active=1 AND category='general' ORDER BY category").fetchall()
        beverages = get_db().execute("SELECT * FROM beverage_products WHERE active=1 ORDER BY name COLLATE NOCASE").fetchall()
        beverage_groups = group_beverages(beverages)
        ticketing_products = get_db().execute("SELECT * FROM ticketing_products ORDER BY active DESC, sort_order, name COLLATE NOCASE").fetchall()
        backup_files = [] if is_postgres_url(app.config.get("DATABASE_URL")) else sorted(BACKUP_DIR.glob("floki_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)[:5]
    else:
        users = promoters = entry_prices = beverages = ticketing_products = backup_files = []
        beverage_groups = []
    return render_template("settings.html", users=users, promoters=promoters, entry_prices=entry_prices, beverages=beverages, beverage_groups=beverage_groups, ticketing_products=ticketing_products, backups=backup_files)


@app.post("/settings/users")
@admin_required
def create_user():
    name = request.form.get("name", "").strip()[:80]
    username = request.form.get("username", "").strip().lower()[:40]
    password = request.form.get("password", "")
    role = request.form.get("role", "cashier")
    sector = request.form.get("sector", "ticketing")
    if role == "admin":
        sector = "all"
    if len(name) < 2 or len(username) < 3 or len(password) < 6 or role not in {"admin", "cashier"} or sector not in {"all", *CASHIER_SECTORS}:
        flash("Revisá los datos. La contraseña debe tener al menos 6 caracteres.", "error")
        return redirect(url_for("settings"))
    try:
        get_db().execute(
            "INSERT INTO users(name, username, password_hash, role, sector, active, created_at) VALUES (?, ?, ?, ?, ?, 1, ?)",
            (name, username, generate_password_hash(password), role, sector, now_iso()),
        )
        get_db().commit()
        flash("Usuario creado.", "success")
    except DB_INTEGRITY_ERRORS:
        flash("Ese nombre de usuario ya existe.", "error")
    return redirect(url_for("settings"))


@app.post("/settings/users/<int:user_id>/name")
@admin_required
def update_user_name(user_id):
    name = request.form.get("name", "").strip()[:80]
    if len(name) < 2:
        flash("El nombre visible debe tener al menos 2 caracteres.", "error")
        return redirect(url_for("settings"))
    user = get_db().execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not user:
        abort(404)
    get_db().execute("UPDATE users SET name=? WHERE id=?", (name, user_id))
    get_db().commit()
    flash("Nombre visible actualizado.", "success")
    return redirect(url_for("settings"))


@app.post("/settings/users/<int:user_id>/toggle")
@admin_required
def toggle_user(user_id):
    if user_id == g.user["id"]:
        flash("No podés desactivar tu propio usuario.", "error")
        return redirect(url_for("settings"))
    user = get_db().execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not user:
        abort(404)
    get_db().execute("UPDATE users SET active=? WHERE id=?", (0 if user["active"] else 1, user_id))
    get_db().commit()
    flash("Estado del usuario actualizado.", "success")
    return redirect(url_for("settings"))


@app.post("/settings/password")
@login_required
def change_password():
    current = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    if not check_password_hash(g.user["password_hash"], current):
        flash("La contraseña actual no es correcta.", "error")
    elif len(new_password) < 6:
        flash("La nueva contraseña debe tener al menos 6 caracteres.", "error")
    else:
        get_db().execute("UPDATE users SET password_hash=? WHERE id=?", (generate_password_hash(new_password), g.user["id"]))
        get_db().commit()
        flash("Contraseña actualizada.", "success")
    return redirect(url_for("settings") if g.user["role"] == "admin" else url_for("dashboard"))


@app.post("/settings/promoters")
@admin_required
def create_promoter():
    name = request.form.get("name", "").strip()[:80]
    if len(name) < 2:
        flash("Ingresá el nombre del promotor.", "error")
        return redirect(url_for("settings"))
    db = get_db()
    try:
        promoter_id, created = get_or_create_promoter(db, name)
        db.commit()
        flash("Promotor agregado con su QR único." if created else "Ese promotor ya existía y quedó activo.", "success")
    except (*DB_INTEGRITY_ERRORS, ValueError) as exc:
        db.rollback()
        flash(str(exc) if isinstance(exc, ValueError) else "No se pudo crear el promotor.", "error")
    return redirect(url_for("settings"))


@app.post("/settings/promoters/<int:promoter_id>/toggle")
@admin_required
def toggle_promoter(promoter_id):
    promoter = get_db().execute("SELECT * FROM promoters WHERE id=?", (promoter_id,)).fetchone()
    if not promoter:
        abort(404)
    if promoter["is_common"] or promoter["is_promo"]:
        flash("Lista común y PROMOS son listas automáticas y no pueden desactivarse.", "error")
        return redirect(url_for("settings"))
    get_db().execute("UPDATE promoters SET active=? WHERE id=?", (0 if promoter["active"] else 1, promoter_id))
    get_db().commit()
    flash("Estado del promotor actualizado.", "success")
    return redirect(url_for("settings"))


@app.post("/settings/prices")
@admin_required
def update_prices():
    db = get_db()
    try:
        rows = db.execute("SELECT category FROM entry_prices WHERE active=1 AND category='general'").fetchall()
        for row in rows:
            category = row["category"]
            cutoff = request.form.get(f"cutoff_{category}", "03:30")
            if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", cutoff):
                raise ValueError("El horario de cambio no es válido")
            before_price = 0 if category == "free" else price_from_option(request.form.get(f"before_{category}"))
            after_price = 0 if category == "free" else price_from_option(request.form.get(f"after_{category}"))
            db.execute(
                "UPDATE entry_prices SET cutoff_time=?, before_price=?, after_price=?, updated_at=? WHERE category=?",
                (cutoff, before_price, after_price, now_iso(), category),
            )
        for product in db.execute("SELECT id FROM ticketing_products").fetchall():
            field = f"ticketing_{product['id']}"
            if field in request.form:
                price = price_from_option(request.form.get(field), allow_zero=False)
                db.execute("UPDATE ticketing_products SET price=?, updated_at=? WHERE id=?", (price, now_iso(), product["id"]))
        for beverage in db.execute("SELECT * FROM beverage_products").fetchall():
            field = f"beverage_{beverage['id']}"
            if field in request.form:
                price = beverage_price_from_option(request.form.get(field), allow_zero=False)
                stock_unit = beverage_option(request.form.get(f"stock_unit_{beverage['id']}", "unidad"), BEVERAGE_STOCK_UNIT_OPTIONS, "la unidad de stock")
                sale_unit = beverage_option(request.form.get(f"sale_unit_{beverage['id']}", "unidad"), BEVERAGE_PRESENTATION_OPTIONS, "la presentación")
                beverage_type = beverage["beverage_type"] or beverage["name"]
                brand = beverage["brand"] or "Sin marca"
                updated_name = build_beverage_name(beverage_type, brand, sale_unit)
                duplicate = db.execute("SELECT id FROM beverage_products WHERE lower(name)=lower(?) AND id<>?", (updated_name, beverage["id"])).fetchone()
                if duplicate:
                    raise ValueError(f"Ya existe la variante {updated_name}")
                approx_yield = suggested_approx_yield(stock_unit, sale_unit, beverage_type, brand, updated_name)
                db.execute("UPDATE beverage_products SET name=?, price=?, stock_unit=?, sale_unit=?, presentation=?, servings_per_stock_unit=1, approx_yield=?, updated_at=? WHERE id=?", (updated_name, price, stock_unit, sale_unit, sale_unit, approx_yield, now_iso(), beverage["id"]))
                db.execute("UPDATE beverage_stock SET beverage_name=? WHERE beverage_id=?", (updated_name, beverage["id"]))
        db.commit()
        message = "Precio de entrada general, guardarropa y variantes de bebidas actualizados."
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"ok": True, "message": message, "version": APP_VERSION})
        flash(message, "success")
    except ValueError as exc:
        db.rollback()
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"ok": False, "message": str(exc)}), 400
        flash(str(exc), "error")
    target = url_for("settings")
    if request.form.get("return_section") == "beverages":
        target += "#bebidas"
    return redirect(target)


@app.post("/settings/beverages")
@admin_required
def create_beverage():
    try:
        beverage_type = beverage_option(request.form.get("beverage_type"), BEVERAGE_TYPE_OPTIONS, "el tipo de bebida")
        brand_choice = request.form.get("brand_choice", "Sin marca").strip()
        if brand_choice == "__custom__":
            brand = re.sub(r"\s+", " ", request.form.get("custom_brand", "").strip())[:40]
            if len(brand) < 2:
                raise ValueError("Escribí la marca personalizada")
        else:
            brand = beverage_option(brand_choice, BEVERAGE_BRAND_OPTIONS, "la marca")
        presentation = beverage_option(request.form.get("presentation"), BEVERAGE_PRESENTATION_OPTIONS, "la presentación")
        stock_unit = beverage_option(request.form.get("stock_unit"), BEVERAGE_STOCK_UNIT_OPTIONS, "la unidad de stock")
        price = beverage_price_from_option(request.form.get("price"), allow_zero=False)
        approx_yield = suggested_approx_yield(stock_unit, presentation, beverage_type, brand)
        # El orden ya no se carga manualmente: categoría fija + nombre alfabético.
        sort_order = 0
        name = build_beverage_name(beverage_type, brand, presentation)
        db = get_db()
        if db.execute("SELECT id FROM beverage_products WHERE active=1 AND lower(name)=lower(?)", (name,)).fetchone():
            raise ValueError("Ya existe esa combinación de bebida, marca y presentación")
        cursor = db.execute(
            """INSERT INTO beverage_products(
                   name, price, stock_unit, sale_unit, servings_per_stock_unit, approx_yield,
                   beverage_type, brand, presentation, active, sort_order, updated_at
               ) VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, 1, ?, ?)""",
            (name, price, stock_unit, presentation, approx_yield, beverage_type, brand, presentation, sort_order, now_iso()),
        )
        product = db.execute("SELECT * FROM beverage_products WHERE id=?", (cursor.lastrowid,)).fetchone()
        cash = get_open_cash_session()
        if cash:
            ensure_beverage_in_event_stock(db, cash["id"], product, g.user["id"])
        db.commit()
        flash(
            f"Variante agregada: {name}. Ya aparece en venta rápida, stock y Excel." if cash
            else f"Variante agregada: {name}. Aparecerá en el próximo evento.",
            "success",
        )
    except DB_INTEGRITY_ERRORS:
        get_db().rollback()
        flash("Ya existe esa combinación de bebida, marca y presentación.", "error")
    except ValueError as exc:
        get_db().rollback()
        flash(str(exc), "error")
    return redirect(url_for("settings"))


@app.post("/settings/beverages/<int:beverage_id>/toggle")
@admin_required
def toggle_beverage(beverage_id):
    product = get_db().execute("SELECT * FROM beverage_products WHERE id=?", (beverage_id,)).fetchone()
    if not product:
        abort(404)
    db = get_db()
    if not product["active"]:
        flash("La bebida ya está fuera del catálogo.", "success")
        return redirect(url_for("settings") + "#bebidas")
    archived_name = f"{(product['name'] or 'Bebida')[:55]} · archivada #{beverage_id}"[:80]
    db.execute("UPDATE beverage_products SET name=?, active=0, updated_at=? WHERE id=?", (archived_name, now_iso(), beverage_id))
    db.commit()
    flash("Bebida eliminada del catálogo activo. El historial de eventos anteriores se conserva.", "success")
    return redirect(url_for("settings") + "#bebidas")




def offline_bootstrap_payload():
    cash = get_open_cash_session()
    user = g.user
    payload = {
        "version": APP_VERSION,
        "server_time": now_iso(),
        "server_epoch_ms": int(datetime.now(timezone.utc).timestamp() * 1000),
        "csrf_token": session.get("csrf_token"),
        "user": {
            "id": user["id"],
            "name": user["name"],
            "username": user["username"],
            "role": user["role"],
            "sector": current_sector(),
        },
        "cash_session": None,
        "entry_prices": [],
        "promoters": [],
        "ticketing_products": [],
        "beverages": [],
        "guests": [],
        "birthdays": [],
    }
    if not cash:
        return payload
    payload["cash_session"] = {
        "id": cash["id"],
        "event_name": cash["event_name"],
        "event_date": cash["event_date"],
        "capacity": cash["capacity"],
        "opened_at": cash["opened_at"],
    }
    sector = current_sector()
    show_ticketing = user["role"] == "admin" or sector == "ticketing"
    show_beverages = user["role"] == "admin" or sector == "beverages"
    if show_ticketing:
        payload["entry_prices"] = [
            {
                "category": row["category"],
                "label": row["label"],
                "cutoff_time": row["cutoff_time"],
                "before_price": float(row["before_price"]),
                "after_price": float(row["after_price"]),
            }
            for row in get_db().execute(
                "SELECT * FROM entry_prices WHERE active=1 AND category='general' ORDER BY category"
            ).fetchall()
        ]
        payload["promoters"] = [
            {"id": row["id"], "name": row["name"]}
            for row in get_db().execute(
                "SELECT id, name FROM promoters WHERE active=1 AND is_common=0 AND is_promo=0 ORDER BY name COLLATE NOCASE"
            ).fetchall()
        ]
        payload["ticketing_products"] = [
            {"id": row["id"], "name": row["name"], "price": float(row["price"])}
            for row in get_db().execute(
                "SELECT * FROM ticketing_products WHERE active=1 ORDER BY sort_order, name COLLATE NOCASE"
            ).fetchall()
        ]
        payload["guests"] = [
            {
                "guest_id": row["guest_id"],
                "guest_name": row["guest_name"],
                "normalized_name": row["normalized_name"],
                "promoter_id": row["promoter_id"],
                "promoter_name": row["promoter_name"],
                "is_common": bool(row["is_common"]),
                "is_promo": bool(row["is_promo"]),
                "is_birthday": bool(row["is_birthday"]),
                "checked_in": bool(row["checkin_id"]),
                "checked_in_at": row["checked_in_at"],
            }
            for row in get_db().execute(
                """SELECT pg.id AS guest_id, pg.guest_name, pg.normalized_name, pg.promoter_id,
                          p.name AS promoter_name, p.is_common, p.is_promo, p.is_birthday,
                          gc.id AS checkin_id, gc.checked_in_at
                   FROM promoter_guests pg
                   JOIN promoters p ON p.id=pg.promoter_id
                   LEFT JOIN guest_checkins gc
                     ON gc.cash_session_id=pg.cash_session_id AND gc.normalized_name=pg.normalized_name
                   WHERE pg.cash_session_id=?
                   ORDER BY pg.guest_name COLLATE NOCASE, p.name COLLATE NOCASE""",
                (cash["id"],),
            ).fetchall()
        ]
    if show_beverages:
        payload["beverages"] = [
            {
                "id": row["id"],
                "name": row["name"],
                "price": float(row["price"]),
                "sale_unit": row["sale_unit"],
                "stock_unit": row["stock_unit"],
                "beverage_type": row["beverage_type"],
                "brand": row["brand"],
                "presentation": row["presentation"],
            }
            for row in get_db().execute(
                "SELECT * FROM beverage_products WHERE active=1 ORDER BY name COLLATE NOCASE"
            ).fetchall()
        ]
        payload["birthdays"] = [
            {
                "promoter_id": row["id"],
                "birthday_person_name": row["birthday_person_name"],
                "checked_count": row["checked_count"],
                "birthday_checked_in": bool(row["birthday_checked"]),
            }
            for row in birthday_promoter_statuses(get_db(), cash["id"])
        ]
    return payload


@app.get("/api/offline/bootstrap")
@login_required
def offline_bootstrap():
    response = jsonify(offline_bootstrap_payload())
    response.headers["Cache-Control"] = "no-store, private"
    return response


def offline_result_from_row(row):
    result = {}
    if row and row["result_json"]:
        try:
            result = json.loads(row["result_json"])
        except (TypeError, json.JSONDecodeError):
            result = {"message": str(row["result_json"])}
    return {
        "operation_id": row["operation_id"],
        "status": row["status"],
        "result": result,
    }


@app.post("/api/offline/sync")
@login_required
def offline_sync():
    body = request.get_json(silent=True) or {}
    operations = body.get("operations") or []
    device_id = str(body.get("device_id") or "").strip()[:100]
    if not device_id or not isinstance(operations, list):
        return jsonify({"ok": False, "error": "Solicitud offline inválida"}), 400
    if len(operations) > 100:
        return jsonify({"ok": False, "error": "Sincronizá como máximo 100 operaciones por vez"}), 400

    results = []
    db = get_db()
    for item in operations:
        operation_id = str((item or {}).get("operation_id") or "").strip()[:80]
        operation_type = str((item or {}).get("operation_type") or "").strip()[:40]
        payload = (item or {}).get("payload") or {}
        cash_session_id = (item or {}).get("cash_session_id")
        client_created_at = operation_time_iso((item or {}).get("created_at"), (item or {}).get("created_at_epoch_ms"))
        original_user_id = (item or {}).get("user_id")
        if not operation_id or not re.fullmatch(r"[A-Za-z0-9._:-]{12,80}", operation_id):
            results.append({"operation_id": operation_id, "status": "conflict", "result": {"message": "Identificador offline inválido"}})
            continue

        existing = db.execute("SELECT * FROM offline_operations WHERE operation_id=?", (operation_id,)).fetchone()
        if existing and existing["status"] in {"applied", "conflict"}:
            results.append(offline_result_from_row(existing))
            continue
        if existing:
            db.execute("DELETE FROM offline_operations WHERE operation_id=?", (operation_id,))
            db.commit()

        status = "applied"
        result = {}
        try:
            if int(original_user_id or 0) != int(g.user["id"]):
                raise ValueError("Esta operación fue creada por otro usuario. Iniciá sesión con ese usuario para sincronizarla")
            cash = get_open_cash_session()
            if not cash or int(cash["id"]) != int(cash_session_id or 0):
                raise ValueError("El evento original ya no está abierto. La operación quedó en conflicto para revisión")
            db.execute(
                """INSERT INTO offline_operations(
                       operation_id, cash_session_id, operation_type, payload_json, status,
                       result_json, client_created_at, synced_at, created_by, device_id
                   ) VALUES (?, ?, ?, ?, 'processing', NULL, ?, ?, ?, ?)""",
                (operation_id, cash["id"], operation_type, json.dumps(payload, ensure_ascii=False), client_created_at, now_iso(), g.user["id"], device_id),
            )
            if operation_type == "quick_sale":
                result = perform_quick_sale(db, cash, g.user, payload, created_at=client_created_at)
            elif operation_type == "guest_checkin":
                guest_id = positive_int(payload.get("guest_id"), "La persona", maximum=1000000)
                result = perform_guest_checkin(db, cash, g.user, guest_id, created_at=client_created_at)
            else:
                raise ValueError("Tipo de operación offline no compatible")
            db.execute(
                "UPDATE offline_operations SET status='applied', result_json=?, synced_at=? WHERE operation_id=?",
                (json.dumps(result, ensure_ascii=False), now_iso(), operation_id),
            )
            db.commit()
        except PermissionError as exc:
            db.rollback()
            status = "conflict"
            result = {"message": str(exc)}
        except (ValueError, TypeError, *DB_INTEGRITY_ERRORS) as exc:
            db.rollback()
            status = "conflict"
            result = {"message": str(exc)}
        except Exception:
            db.rollback()
            app.logger.exception("Error temporal sincronizando la operación offline %s", operation_id)
            status = "retry"
            result = {"message": "Error temporal al sincronizar. Se volverá a intentar"}

        if status != "applied":
            try:
                db.execute(
                    """INSERT INTO offline_operations(
                           operation_id, cash_session_id, operation_type, payload_json, status,
                           result_json, client_created_at, synced_at, created_by, device_id
                       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        operation_id, int(cash_session_id or 0), operation_type,
                        json.dumps(payload, ensure_ascii=False), status,
                        json.dumps(result, ensure_ascii=False), client_created_at,
                        now_iso(), g.user["id"], device_id,
                    ),
                )
                db.commit()
            except DB_INTEGRITY_ERRORS:
                db.rollback()
                existing = db.execute("SELECT * FROM offline_operations WHERE operation_id=?", (operation_id,)).fetchone()
                if existing:
                    results.append(offline_result_from_row(existing))
                    continue
            except Exception:
                db.rollback()
        results.append({"operation_id": operation_id, "status": status, "result": result})

    summary = {
        "applied": sum(1 for row in results if row["status"] == "applied"),
        "conflicts": sum(1 for row in results if row["status"] == "conflict"),
        "retry": sum(1 for row in results if row["status"] == "retry"),
    }
    return jsonify({"ok": True, "results": results, "summary": summary, "bootstrap": offline_bootstrap_payload()})


@app.get("/offline-operations")
def offline_operations_page():
    response = render_template("offline_operations.html")
    return Response(response, mimetype="text/html")


@app.route("/api/status")
@login_required
def api_status():
    cash = get_open_cash_session()
    if not cash:
        return jsonify({"cash_open": False})
    totals, _ = session_totals(cash["id"])
    payload = {
        "cash_open": True, "session_id": cash["id"], "event_name": cash["event_name"],
        "event_date": cash["event_date"], "capacity": cash["capacity"], "sector": current_sector(),
    }
    if g.user["role"] == "admin":
        payload.update({
            "people_count": totals["people_count"], "drink_count": totals["drink_count"],
            "rrpp_benefit_count": totals["rrpp_benefit_count"],
            "sales": totals["sales"], "expenses": totals["expenses"],
        })
    elif current_sector() == "ticketing":
        payload.update({"people_count": totals["people_count"]})
    return jsonify(payload)


@app.route("/diagnostic")
@login_required
def diagnostic():
    """Diagnóstico mínimo que no depende del dashboard ni del JavaScript/PWA."""
    db = get_db()
    checks = {}
    probes = {
        "user": ("SELECT id, name, username, role, sector, active FROM users WHERE id=?", (g.user["id"],)),
        "open_cash": ("SELECT id, event_name, event_date, status FROM cash_sessions WHERE status='open' ORDER BY id DESC LIMIT 1", ()),
        "promoters": ("SELECT COUNT(*) AS total FROM promoters WHERE active=1", ()),
        "beverages": ("SELECT COUNT(*) AS total FROM beverage_products WHERE active=1", ()),
        "ticketing_products": ("SELECT COUNT(*) AS total FROM ticketing_products WHERE active=1", ()),
        "speed_active": ("SELECT COUNT(*) AS total FROM beverage_products WHERE active=1 AND (lower(brand)='speed' OR lower(name) LIKE '%speed%')", ()),
        "movement_bundle_columns": ("SELECT COUNT(*) AS total FROM movements WHERE category='champagne_speed'", ()),
        "stock_adjustments": ("SELECT COUNT(*) AS total FROM beverage_stock_adjustments", ()),
    }
    ok = True
    for name, (sql, params) in probes.items():
        try:
            row = db.execute(sql, params).fetchone()
            checks[name] = dict(row) if row is not None else None
        except Exception as exc:
            ok = False
            checks[name] = {"error": type(exc).__name__, "message": str(exc)[:240]}
    return jsonify({
        "status": "ok" if ok else "error",
        "version": APP_VERSION,
        "database": "postgresql" if db.is_postgres else "sqlite",
        "user": {"id": g.user["id"], "username": g.user["username"], "role": g.user["role"], "sector": g.user["sector"]},
        "checks": checks,
        "offline_safe_stage": 0,
        "offline_temporarily_disabled": True,
    }), (200 if ok else 500)


@app.route("/health")
def health():
    try:
        db = get_db()
        db.execute("SELECT 1").fetchone()
        return jsonify({
            "status": "ok",
            "version": APP_VERSION,
            "database": "postgresql" if db.is_postgres else "sqlite",
        }), 200
    except Exception as exc:
        app.logger.exception("Health check failed")
        return jsonify({"status": "error", "message": str(exc)[:160]}), 503


@app.route("/manifest.webmanifest")
def manifest():
    return send_from_directory(app.static_folder, "manifest.webmanifest", mimetype="application/manifest+json")


@app.route("/service-worker.js")
def service_worker():
    response = send_from_directory(app.static_folder, "service-worker.js", mimetype="application/javascript")
    response.headers["Service-Worker-Allowed"] = "/"
    response.headers["Cache-Control"] = "no-cache"
    return response


@app.route("/offline")
def offline():
    return render_template("offline.html")


@app.errorhandler(500)
def internal_error(error):
    app.logger.exception("Unhandled Floki request error", exc_info=getattr(error, "original_exception", error))
    # Respuesta deliberadamente independiente de base.html/CSS/JS para que un error real nunca se vea como pantalla blanca.
    html = f"""<!doctype html><html lang='es'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Floki · Error</title></head><body style='margin:0;padding:32px;background:#09070d;color:#fff;font-family:system-ui,sans-serif'><main style='max-width:720px;margin:auto'><h1 style='color:#c66cff'>Floki Manager</h1><h2>No se pudo cargar esta pantalla</h2><p>La aplicación está en línea, pero ocurrió un error interno. Versión {APP_VERSION}.</p><p>Probá <a style='color:#d9a0ff' href='/diagnostic'>/diagnostic</a> con tu sesión iniciada para identificar qué consulta falló.</p></main></body></html>"""
    return Response(html, status=500, mimetype="text/html")


@app.errorhandler(403)
def forbidden(_error):
    return render_template("error.html", title="Acceso denegado", message="No tenés permiso para realizar esta acción."), 403


@app.errorhandler(404)
def not_found(_error):
    return render_template("error.html", title="No encontrado", message="La página o registro solicitado no existe."), 404


@app.errorhandler(400)
def bad_request(error):
    return render_template("error.html", title="Solicitud inválida", message=str(getattr(error, "description", error))), 400


@app.cli.command("init-db")
def init_db_command():
    init_db()
    print("Base de datos inicializada.")


if os.getenv("FLOKI_SKIP_AUTO_INIT") != "1":
    init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=os.getenv("FLASK_DEBUG") == "1")
