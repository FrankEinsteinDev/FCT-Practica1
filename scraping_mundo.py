"""scraping_mundo.py

Aplicación Flask que:
- Raspa titulares de El Mundo usando requests + BeautifulSoup
- Detecta fechas con regex ( dd/mm/aaaa o de 4 cifras) y palabra clave "Ayuntamiento"
- Guarda resultados en SQLite
- Muestr tabla con Bootstrap en plantilla externa (/templates/index.html)
- Permite búsqueda por texto y filtrado por autor/sección)
"""
import re
import html
import sqlite3
import requests
from flask import Flask, request, g, redirect, url_for, render_template
from bs4 import BeautifulSoup

DB_PATH = 'noticias.db'
MAX_NEWS = 10

app = Flask(__name__)  # Cambiar nombre

# --------------------
# Database helpers
# --------------------


def get_db():
    """Devuelve la conexión a la base de datos SQLite."""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(_):
    """Cierra la conexión a la base de datos al finalizar la solicitud."""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def init_db():
    """Inicializa la tabla de noticias si no existe."""
    db = get_db()
    db.execute('''
        CREATE TABLE IF NOT EXISTS noticias (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               title TEXT NOT NULL,
               link TEXT UNIQUE NOT NULL,
               date TEXT,
               author_section TEXT,
               detected_keyword TEXT
        )
    ''')
    db.commit()


# --------------------
# Scraper específico para El Mundo
# --------------------

DATE_DDMMYYYY = re.compile(r'\b(\d{2}/\d{2}/\d{4})\b')
DATE_YEAR = re.compile(r'\b(19\d{2}|20\d{2})\b')
KEYWORDS = [r'\bAyuntamiento\b']


def clean_title(t):
    """Limpia y trunca títulos largos."""
    t = html.unescape(t).strip()
    if len(t) > 150:
        return t[:147].rstrip() + '...'
    return t


def detect_date_and_author(soup, page_text):
    """Detecta la fecha y autor/sección a partir de meta tags o regex."""
    date = None
    author_section = None

    meta_date = soup.find('meta', attrs={'name': re.compile('date', re.I)}) or \
        soup.find('meta', attrs={'property': re.compile('published', re.I)})
    if meta_date and meta_date.get('content'):
        date = meta_date['content']

    if not date:
        m = DATE_DDMMYYYY.search(page_text)
        if m:
            date = m.group(1)
    if not date:
        m2 = DATE_YEAR.search(page_text)
        if m2:
            date = m2.group(1)

    meta_author = soup.find('meta', attrs={'name': re.compile('author', re.I)})
    if meta_author and meta_author.get('content'):
        author_section = meta_author['content']
    return date, author_section


def scrape_elmundo_rss(max_items=MAX_NEWS):
    """Raspa titulares de El Mundo desde el RSS y los guarda en SQLite."""
    init_db()
    db = get_db()
    collected = 0

    rss_url = "https://www.elmundo.es/rss/portada.xml"

    try:
        r = requests.get(rss_url, timeout=10)
        r.raise_for_status()
    except requests.exceptions.RequestException:
        return 0

    soup = BeautifulSoup(r.content, "xml")
    noticias = soup.find_all("item")[:max_items]

    for item in noticias:
        titulo = clean_title(item.title.text)
        enlace = item.link.text
        fecha = item.pubDate.text if item.pubDate else None
        autor_tag = item.find("dc:creator")
        author_section = autor_tag.text if autor_tag else None

        detected_keyword = None
        page_text = f"{titulo} {author_section or ''}"
        for kw in KEYWORDS:
            if re.search(kw, page_text, re.I):
                detected_keyword = re.search(kw, page_text, re.I).group(0)
                break

        try:
            db.execute('''
                INSERT INTO noticias (title, link, date, author_section, detected_keyword)
                VALUES (?, ?, ?, ?, ?)
            ''', (titulo, enlace, fecha, author_section, detected_keyword))
            db.commit()
            collected += 1
        except sqlite3.IntegrityError:
            continue

    return collected

# --------------------
# Flask routes
# --------------------


@app.route('/')
def index():
    """Muestra la tabla de noticias, con búsqueda y filtro por autor."""
    init_db()
    q = request.args.get('q', '').strip()
    author = request.args.get('author', '').strip()

    db = get_db()
    params = []
    where = []
    sql = 'SELECT * FROM noticias'

    if q:
        where.append(
            "(title LIKE ? OR link LIKE ? OR date LIKE ? OR author_section LIKE ?)"
        )
        likeq = f'%{q}%'
        params.extend([likeq, likeq, likeq, likeq])
    if author:
        where.append('author_section = ?')
        params.append(author)
    if where:
        sql += ' WHERE ' + ' AND '.join(where)
    sql += ' ORDER BY id DESC LIMIT ?'
    params.append(MAX_NEWS)

    cur = db.execute(sql, params)
    rows = cur.fetchall()

    cur2 = db.execute(
        'SELECT DISTINCT author_section FROM noticias WHERE author_section'
        ' IS NOT NULL')
    authors = [r[0] for r in cur2.fetchall() if r[0]]

    return render_template('index.html', rows=rows, q=q, author=author,
                           authors=authors)


@app.route('/scrape')
def do_scrape():
    """Ejecuta el scraper y redirige a la página principal."""
    init_db()
    scrape_elmundo_rss(MAX_NEWS)
    return redirect(url_for('index'))


if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=True)
