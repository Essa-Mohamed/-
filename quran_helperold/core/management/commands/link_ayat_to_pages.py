import sqlite3
from pathlib import Path
from django.core.management.base import BaseCommand
from core.models import Ayah, Page

# هنحاول نكتشف أسماء الأعمدة الشائعة في جدول words تلقائيًا
WORDS_COL_SETS = [
    # (word_index, surah, ayah)
    ("word_index", "surah", "ayah"),
    ("word_index", "sura", "aya"),
    ("word_index", "surah_number", "ayah_number"),
    ("id", "surah", "ayah"),
    ("id", "surah_number", "ayah_number"),
]

class Command(BaseCommand):
    help = "Link Ayah.page using mushaf layout (pages table) + words DB (words table)."

    def add_arguments(self, parser):
        parser.add_argument('--layout-sqlite', required=True,
                            help='Path to mushaf-madinah-v1.db (has pages/info)')
        parser.add_argument('--words-sqlite', required=True,
                            help='Path to QPC V1 Glyphs – Word by Word.db (has words)')
        parser.add_argument('--pages', type=int, default=604,
                            help='Total pages in mushaf (default 604)')
        parser.add_argument('--limit-pages', type=int, default=0,
                            help='If >0, only process up to this page number')

    def _detect_words_schema(self, conn):
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(words)")
        cols = [r[1].lower() for r in cur.fetchall()]
        for wi, su, ay in WORDS_COL_SETS:
            if wi.lower() in cols and su.lower() in cols and ay.lower() in cols:
                return wi, su, ay
        raise RuntimeError(f"Could not detect columns in 'words'. Found: {cols}")

    def handle(self, *args, **options):
        layout_path = Path(options['layout_sqlite'])
        words_path  = Path(options['words_sqlite'])
        limit_pages = int(options['limit_pages']) or None

        if not layout_path.exists():
            self.stderr.write(f"Layout DB not found: {layout_path}")
            return
        if not words_path.exists():
            self.stderr.write(f"Words DB not found:  {words_path}")
            return

        # افتح قاعدة الكلمات واكتشف أسماء الأعمدة
        con_words  = sqlite3.connect(str(words_path))
        wi, su, ay = self._detect_words_schema(con_words)
        curw = con_words.cursor()
        self.stdout.write(f"Detected words schema: ({wi}, {su}, {ay})")

        # ابنِ خريطة word_index -> (surah, ayah)
        curw.execute(f"SELECT {wi}, {su}, {ay} FROM words")
        wmap = {}
        for wid, s, a in curw.fetchall():
            try:
                wid_i = int(wid); s_i = int(s); a_i = int(a)
            except Exception:
                continue
            wmap[wid_i] = (s_i, a_i)
        self.stdout.write(f"Loaded {len(wmap):,} words.")

        # افتح قاعدة الـlayout
        con_layout = sqlite3.connect(str(layout_path))
        curl = con_layout.cursor()

        # هات سطور الآيات مع نطاق الكلمات
        curl.execute("""
            SELECT page_number, line_number, line_type, first_word_id, last_word_id
            FROM pages
            WHERE line_type='ayah'
        """)
        lines = curl.fetchall()

        total_lines = 0
        linked = 0
        for page_number, line_number, line_type, first_w, last_w in lines:
            if not first_w or not last_w:
                continue
            try:
                pno = int(page_number)
            except Exception:
                continue
            if limit_pages and pno > limit_pages:
                continue

            # كل سطر قد يحتوي على جزء من آية أو أكثر — ناخد كل (سورة، آية) ظهرت في نطاق الكلمات
            seen_pairs = set()
            try:
                fw = int(first_w); lw = int(last_w)
            except Exception:
                continue
            if fw > lw:
                fw, lw = lw, fw

            for wid in range(fw, lw + 1):
                sa = wmap.get(wid)
                if sa:
                    seen_pairs.add(sa)

            if not seen_pairs:
                total_lines += 1
                continue

            # اربط كل آية بأول صفحة تظهر فيها
            page_obj, _ = Page.objects.get_or_create(number=pno)
            for (s, a) in seen_pairs:
                try:
                    ayah = Ayah.objects.get(surah=s, number=a)
                except Ayah.DoesNotExist:
                    continue
                if ayah.page_id is None or (ayah.page and pno < ayah.page.number):
                    ayah.page = page_obj
                    ayah.save(update_fields=['page'])
                    linked += 1

            total_lines += 1

        self.stdout.write(self.style.SUCCESS(
            f"Processed {total_lines:,} ayah-lines. Linked/updated {linked:,} ayat to pages."
        ))
