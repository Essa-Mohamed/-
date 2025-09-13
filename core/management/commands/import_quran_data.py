from django.core.management.base import BaseCommand
from quran_structure.models import Juz, Quarter, Ayah
from core.models import Phrase, PhraseOccurrence
import json
from pathlib import Path
import re
import unicodedata
from collections import defaultdict

# -------- إعدادات النطاق --------
FIRST_JUZ = 1
LAST_JUZ  = 4

# -------- أدوات التطبيع --------
DIAC = re.compile(r'[\u064B-\u0652\u0670\u06DF-\u06ED]')

def normalize(txt: str) -> str:
    """تطبيع نص عربي: إزالة التشكيل وتوحيد الهمزات والتاء المربوطة… إلخ."""
    txt = unicodedata.normalize('NFKD', txt)
    txt = DIAC.sub('', txt)
    txt = (txt
           .replace('إ', 'ا')
           .replace('أ', 'ا')
           .replace('آ', 'ا')
           .replace('ة', 'ه')
           .replace('ى', 'ي'))
    txt = re.sub(r'[^\w\s]', ' ', txt)
    txt = re.sub(r'\s+', ' ', txt).strip()
    return txt

def find_span(words_norm, phrase_norm_words):
    """
    ابحث عن span لأول تطابق كامل للعبارة (مطبّعة) داخل كلمات آية مطبّعة.
    يرجع مؤشرين 1-based شاملين (start_word, end_word) أو None.
    """
    L = len(phrase_norm_words)
    if L == 0:
        return None
    for i in range(0, len(words_norm) - L + 1):
        if words_norm[i:i+L] == phrase_norm_words:
            return (i + 1, i + L)  # 1-based inclusive
    return None

def _sanitize_span(span, words_len):
    """توحيد/تصحيح span ليكون 1-based inclusive وداخل حدود عدد كلمات الآية."""
    if not span or len(span) < 2:
        return None
    try:
        s = int(span[0]); e = int(span[1])
    except Exception:
        return None
    # لو المؤشرات 0-based حوّلها لـ 1-based
    if s == 0 or e == 0:
        s += 1; e += 1
    if s > e:
        s, e = e, s
    # قصّ على حدود الكلمات
    s = max(1, min(s, words_len))
    e = max(1, min(e, words_len))
    return (s, e)

def _parse_match_words(match_words):
    """
    يحاول استخراج (src_span, tgt_span) من صيغ متعددة لـ match_words:
    أمثلة مدعومة:
    - [[src_start, src_end], [tgt_start, tgt_end], ...]
    - [[src_start, src_end]]
    - [ [ [src_start,src_end], [tgt_start,tgt_end] ], ... ]  (متشعب)
    - [{'source':[s,e], 'target':[s,e]}, ...]
    - [list of word indices]  -> يتحول لـ (min,max) كمصدر فقط
    يرجع (src_span, tgt_span) أو (None, None) إن فشل.
    """
    src_span = None
    tgt_span = None
    mw = match_words

    if not isinstance(mw, list) or not mw:
        return (None, None)

    x = mw[0]

    # dict بشكل واضح
    if isinstance(x, dict):
        if isinstance(x.get('source'), list) and len(x['source']) >= 2:
            src_span = (x['source'][0], x['source'][1])
        if isinstance(x.get('target'), list) and len(x['target']) >= 2:
            tgt_span = (x['target'][0], x['target'][1])
        return (src_span, tgt_span)

    # زوج أزواج: [ [s1,e1], [s2,e2] ]
    if isinstance(x, list) and len(x) == 2 and all(isinstance(v, list) for v in x):
        if len(x[0]) >= 2:
            src_span = (x[0][0], x[0][1])
        if len(x[1]) >= 2:
            tgt_span = (x[1][0], x[1][1])
        return (src_span, tgt_span)

    # [s,e] مصدر فقط
    if isinstance(x, list) and len(x) >= 2 and all(isinstance(v, (int, float, str)) for v in x[:2]):
        src_span = (x[0], x[1])
        return (src_span, tgt_span)

    # لستة مؤشرات [5,6,7] -> (5,7)
    if isinstance(x, list) and all(isinstance(v, (int, float, str)) for v in x):
        xs = [int(v) for v in x]
        src_span = (min(xs), max(xs))
        return (src_span, tgt_span)

    return (None, None)

class Command(BaseCommand):
    help = "Import Quran metadata + build Phrase & PhraseOccurrence from matching-ayah.json"

    def handle(self, *args, **opts):
        base_dir = Path(__file__).resolve().parent.parent.parent.parent
        data_dir = base_dir / "data"

        ayah_path   = data_dir / "quran-metadata-ayah.json"
        juz_path    = data_dir / "quran-metadata-juz.json"
        rub_path    = data_dir / "quran-metadata-rub.json"
        match_path  = data_dir / "matching-ayah.json"

        for p in (ayah_path, juz_path, rub_path, match_path):
            if not p.exists():
                self.stderr.write(f"❌ Missing {p}")
                return

        ayah_data = json.loads(ayah_path.read_text(encoding="utf-8"))
        juz_data  = json.loads(juz_path.read_text(encoding="utf-8"))
        rub_data  = json.loads(rub_path.read_text(encoding="utf-8"))
        matches   = json.loads(match_path.read_text(encoding="utf-8"))

        # -------- أجزاء Juz --------
        juz_map = {}   # verse_key -> juz_no
        created_juz = []
        for j_no_str, info in juz_data.items():
            j_no = int(j_no_str)
            if not (FIRST_JUZ <= j_no <= LAST_JUZ):
                continue
            Juz.objects.get_or_create(number=j_no)
            created_juz.append(j_no)
            for s_str, rng in info.get("verse_mapping", {}).items():
                s = int(s_str)
                a1, a2 = map(int, rng.split('-'))
                for a in range(a1, a2 + 1):
                    juz_map[f"{s}:{a}"] = j_no
        self.stdout.write(f"✔️ Juz done: {created_juz}")

        # -------- أرباع (Rubʿ) -> Quarter --------
        rub_quarter = {}
        idx_in_juz = defaultdict(int)
        # رتب بالأرقام
        for rub_no_str, info in sorted(rub_data.items(), key=lambda x: int(x[0])):
            verses = []
            for s_str, rng in info.get("verse_mapping", {}).items():
                s = int(s_str); a1, a2 = map(int, rng.split('-'))
                verses += [f"{s}:{a}" for a in range(a1, a2 + 1)]
            if not verses:
                continue
            vk0 = verses[0]
            j_no = juz_map.get(vk0)
            if not j_no or j_no > LAST_JUZ:
                continue
            idx_in_juz[j_no] += 1
            juz_obj = Juz.objects.get(number=j_no)

            # أول 3 كلمات من أول آية كـ label للربع
            first_text = next((v["text"] for v in ayah_data.values() if v["verse_key"] == vk0), "")
            label = " ".join(first_text.split()[:3]) if first_text else f"Quarter {idx_in_juz[j_no]}"
            q_obj, _ = Quarter.objects.get_or_create(
                juz=juz_obj,
                index_in_juz=idx_in_juz[j_no],
                defaults={"label": label}
            )
            rub_quarter[int(rub_no_str)] = q_obj
        self.stdout.write("✔️ Quarters done")

        # -------- إنشاء/تحديث آيات --------
        for v in ayah_data.values():
            vk = v["verse_key"]
            j_no = juz_map.get(vk)
            if not j_no or j_no > LAST_JUZ:
                continue
            Ayah.objects.update_or_create(
                surah=v["surah_number"],
                number=v["ayah_number"],
                defaults={"text": v["text"]}
            )

        # -------- ربط الآيات بالأرباع --------
        for rub_no_str, info in sorted(rub_data.items(), key=lambda x: int(x[0])):
            rub_no = int(rub_no_str)
            q_obj = rub_quarter.get(rub_no)
            if not q_obj:
                continue
            for s_str, rng in info.get("verse_mapping", {}).items():
                s = int(s_str); a1, a2 = map(int, rng.split('-'))
                for a in range(a1, a2 + 1):
                    Ayah.objects.filter(surah=s, number=a).update(quarter=q_obj)
        self.stdout.write("✔️ Ayah objects assigned to quarters")

        # -------- بناء Phrase & PhraseOccurrence --------
        # تنظيف القديم لبناء نظيف
        PhraseOccurrence.objects.all().delete()
        Phrase.objects.all().delete()

        # كاش الكلمات المطبّعة لكل آية
        words_cache = {}   # verse_key -> (words_raw, words_norm)
        ayah_by_key = {}   # "s:a" -> Ayah instance
        for v in ayah_data.values():
            vk = v["verse_key"]
            j_no = juz_map.get(vk)
            if not j_no or j_no > LAST_JUZ:
                continue
            words_raw = v["text"].split()
            words_norm = [normalize(w) for w in words_raw]
            words_cache[vk] = (words_raw, words_norm)
            try:
                ayah_by_key[vk] = Ayah.objects.get(surah=v["surah_number"], number=v["ayah_number"])
            except Ayah.DoesNotExist:
                pass

        phrase_map = {}   # normalized -> Phrase
        total_occ = 0
        total_phrases = 0

        # مرّن التعامل مع match_words
        for src_vk, lst in matches.items():
            if src_vk not in words_cache:
                continue
            for m in lst:
                pairs = m.get("match_words") or []
                words_raw, words_norm = words_cache[src_vk]
                src_span, tgt_span = _parse_match_words(pairs)

                # سدّد وصحّح span المصدر
                src_span = _sanitize_span(src_span, len(words_raw)) if src_span else None
                if not src_span:
                    # لا نعلم حدود المصدر بدقة؛ نترك هذا التطابق
                    continue

                s1, e1 = src_span
                phrase_words_raw = words_raw[s1 - 1:e1]
                phrase_text = " ".join(phrase_words_raw).strip()
                phrase_norm = normalize(phrase_text)
                phrase_norm_words = phrase_norm.split()
                if len(phrase_norm_words) < 2:
                    # تجاهل العبارات القصيرة جداً
                    continue

                # أنشئ/أحضر Phrase
                ph = phrase_map.get(phrase_norm)
                if ph is None:
                    ph = Phrase.objects.create(
                        text=phrase_text,
                        normalized=phrase_norm,
                        length_words=len(phrase_norm_words),
                        global_freq=0
                    )
                    phrase_map[phrase_norm] = ph
                    total_phrases += 1

                # occurrence في آية المصدر
                src_ayah = ayah_by_key.get(src_vk)
                if src_ayah:
                    PhraseOccurrence.objects.get_or_create(
                        phrase=ph, ayah=src_ayah,
                        start_word=s1, end_word=e1
                    )
                    total_occ += 1

                # occurrence في آية الهدف
                tgt_vk = m.get("matched_ayah_key")
                if tgt_vk and tgt_vk in words_cache:
                    t_words_raw, t_words_norm = words_cache[tgt_vk]
                    tgt_ayah = ayah_by_key.get(tgt_vk)

                    span = None
                    if tgt_span:
                        span = _sanitize_span(tgt_span, len(t_words_raw))
                    if not span:
                        span = find_span(t_words_norm, phrase_norm_words)

                    if tgt_ayah and span:
                        s2, e2 = span
                        PhraseOccurrence.objects.get_or_create(
                            phrase=ph, ayah=tgt_ayah,
                            start_word=s2, end_word=e2
                        )
                        total_occ += 1

        # حدّث global_freq لكل Phrase
        for ph in Phrase.objects.all():
            cnt = PhraseOccurrence.objects.filter(phrase=ph).count()
            ph.global_freq = cnt
            # confusability ممكن نحسبها لاحقًا (مثال: cnt / length_words)
            ph.save(update_fields=['global_freq'])

        self.stdout.write(f"✔️ Phrases: {total_phrases}, Occurrences: {total_occ}")
        self.stdout.write(self.style.SUCCESS("تم الاستيراد وبناء العبارات بنجاح 🎉"))
