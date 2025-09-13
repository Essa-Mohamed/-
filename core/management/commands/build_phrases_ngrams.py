from django.core.management.base import BaseCommand
from django.db import transaction
from quran_structure.models import Ayah
from core.models import Phrase, PhraseOccurrence
import re, unicodedata
from collections import defaultdict

DIAC = re.compile(r'[\u064B-\u0652\u0670\u06DF-\u06ED]')
def normalize(txt: str) -> str:
    txt = unicodedata.normalize('NFKD', txt)
    txt = DIAC.sub('', txt)
    txt = (txt.replace('إ','ا').replace('أ','ا').replace('آ','ا')
               .replace('ة','ه').replace('ى','ي'))
    txt = re.sub(r'[^\w\s]', ' ', txt)
    txt = re.sub(r'\s+', ' ', txt).strip()
    return txt

class Command(BaseCommand):
    help = "Build Tarateel-like phrase index from Ayah.text using n-grams"

    def add_arguments(self, p):
        p.add_argument('--juz-from', type=int, default=1)
        p.add_argument('--juz-to', type=int, default=4)
        p.add_argument('--min-n', type=int, default=3)
        p.add_argument('--max-n', type=int, default=7)
        p.add_argument('--min-freq', type=int, default=2)
        p.add_argument('--max-freq', type=int, default=60)

    @transaction.atomic
    def handle(self, *a, **o):
        jf, jt = o['juz_from'], o['juz_to']
        min_n, max_n = o['min_n'], o['max_n']
        min_f, max_f = o['min_freq'], o['max_freq']

        # اجمع آيات النطاق
        ayat = (Ayah.objects
                .filter(quarter__juz__number__gte=jf, quarter__juz__number__lte=jt)
                .select_related('quarter__juz')
                .order_by('surah','number'))

        # ابنِ n-grams
        occs = defaultdict(list)   # norm_phrase -> list of (ayah_id, s, e, raw_text)
        for a in ayat:
            words = a.text.split()
            words_norm = [normalize(w) for w in words]
            L = len(words)
            for n in range(min_n, max_n+1):
                if n > L: break
                for i in range(0, L-n+1):
                    raw = " ".join(words[i:i+n]).strip()
                    norm = normalize(raw)
                    if len(norm.split()) < min_n:  # أمان إضافي
                        continue
                    occs[norm].append((a.id, i+1, i+n, raw))

        # فلترة بالتكرار
        kept = {k:v for k,v in occs.items() if min_f <= len(v) <= max_f}

        # تجميع حسب مجموعة الآيات المتطابقة ثم اختيار "الأطول"
        groups = defaultdict(list)  # frozenset(ayah_ids) -> [ (norm, occ_list) ]
        for norm, v in kept.items():
            ayids = frozenset(o[0] for o in v)
            groups[ayids].append((norm, v))

        PhraseOccurrence.objects.all().delete()
        Phrase.objects.all().delete()

        total_phrases = 0
        total_occ = 0
        for ayids, items in groups.items():
            # اختَر الأطول (بعدد الكلمات) ثم الأكثر وضوحاً كبديل
            items.sort(key=lambda x: (-len(x[0].split()), -len(x[1])))
            norm, v = items[0]
            # استخدم أول raw كعرض
            display_text = v[0][3]
            ph = Phrase.objects.create(
                text=display_text,
                normalized=norm,
                length_words=len(norm.split()),
                global_freq=len(v)
            )
            total_phrases += 1
            for ay_id, s, e, _ in v:
                PhraseOccurrence.objects.create(
                    phrase=ph, ayah_id=ay_id, start_word=s, end_word=e
                )
                total_occ += 1

        self.stdout.write(self.style.SUCCESS(
            f"Built phrases: {total_phrases}, occurrences: {total_occ}"
        ))
