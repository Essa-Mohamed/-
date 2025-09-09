# Aggregated on 2025-08-14T19:06:48.086682 UTC


# ===== FILE: core/__init__.py =====
"""Core application for Quran memorization assistant."""

# ===== FILE: core/admin.py =====
from django.contrib import admin
from django.contrib.auth.models import User, Group
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import (
    Complaint, Student, Juz, Quarter, SimilarityGroup, Ayah,
    TestSession, TestQuestion, Phrase, PhraseOccurrence
)

# --------- تخصيص عرض الـUsers في الأدمن ---------
# أخفي Groups (اختياري)
try:
    admin.site.unregister(Group)
except admin.sites.NotRegistered:
    pass

# لازم نفك تسجيل User الافتراضي قبل ما نعيد تسجيله
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass

@admin.register(User)
class StaffOnlyUserAdmin(BaseUserAdmin):
    """اعرض في الأدمن المستخدمين الـstaff فقط."""
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(is_staff=True)

    # (اختياري) لما تضيف User من الأدمن خلّيه staff تلقائيًا
    def save_model(self, request, obj, form, change):
        if not obj.is_staff:
            obj.is_staff = True
        super().save_model(request, obj, form, change)

# --------- بقية الموديلات ---------
@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = ('student', 'short_text', 'created_at', 'resolved')
    list_filter = ('resolved', 'created_at', 'student')
    search_fields = ('text', 'student__display_name', 'student__user__username')
    raw_id_fields = ('student',)
    actions = ['mark_resolved']

    def short_text(self, obj):
        return obj.text[:50] + ('…' if len(obj.text) > 50 else '')
    short_text.short_description = 'نص مختصر'

    def mark_resolved(self, request, queryset):
        updated = queryset.update(resolved=True)
        self.message_user(request, f'{updated} شكوى تم تعليمها كمُحلّة.')
    mark_resolved.short_description = 'وضع كمُحلّل'

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'user')
    search_fields = ('display_name', 'user__username')

@admin.register(Phrase)
class PhraseAdmin(admin.ModelAdmin):
    list_display = ('text', 'length_words', 'global_freq', 'confusability')
    search_fields = ('text', 'normalized')

@admin.register(PhraseOccurrence)
class PhraseOccurrenceAdmin(admin.ModelAdmin):
    list_display = ('phrase', 'ayah', 'start_word', 'end_word')
    search_fields = ('phrase__text', 'ayah__surah', 'ayah__number')
    list_filter = ('phrase',)

# (لو حابب تضيف تسجيل لباقي الموديلات)
# admin.site.register(Juz)
# admin.site.register(Quarter)
# admin.site.register(SimilarityGroup)
# admin.site.register(Ayah)
# admin.site.register(TestSession)
# admin.site.register(TestQuestion)


# ===== FILE: core/context_processors.py =====
from .models import Student
from django.conf import settings


def inject_student(request):
    if request.user.is_authenticated:
        student, _ = Student.objects.get_or_create(
            user=request.user, defaults={'display_name': request.user.username}
        )
        return {'student': student}
    return {}


def inject_version(request):
    label = getattr(settings, "VERSION_LABEL", "")
    return {
        "APP_NAME": "Mutawatir",
        "APP_VERSION": label,
        "IS_ALPHA": "alpha" in (label or "").lower(),
    }

# ===== FILE: core/forms.py =====
"""
Forms for the Quran memorization assistant.

These forms provide simple interfaces for capturing the student’s
display name and complaints. Additional forms for selecting tests
and answering questions can be implemented similarly.
"""
from django import forms  # type: ignore
from django.contrib.auth.models import User  # type: ignore
from .models import Complaint
from django.contrib.auth.forms import PasswordChangeForm


class StudentNameForm(forms.Form):
    """Capture a student’s display name to create a user account on the fly."""

    display_name = forms.CharField(label='اسم الطالب', max_length=100)


class ComplaintForm(forms.ModelForm):
    """Form for submitting a complaint."""

    class Meta:
        model = Complaint
        fields = ['text']
        widgets = {
            'text': forms.Textarea(attrs={'rows': 4, 'cols': 40, 'placeholder': 'اكتب شكواك هنا...'}),
        }

class AccountForm(forms.Form):
    display_name = forms.CharField(label='اسم العرض', max_length=100)
    email = forms.EmailField(label='البريد الإلكتروني (اختياري)', required=False)
    avatar = forms.ImageField(label='الصورة الشخصية (اختياري)', required=False)

class PasswordChangeTightForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['old_password'].label = 'كلمة المرور الحالية'
        self.fields['new_password1'].label = 'كلمة المرور الجديدة'
        self.fields['new_password2'].label = 'تأكيد كلمة المرور الجديدة'

# ===== FILE: core/management/__init__.py =====


# ===== FILE: core/management/commands/__init__.py =====


# ===== FILE: core/management/commands/aggregatecodes.py =====
import os
from pathlib import Path
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

class Command(BaseCommand):
    help = 'Aggregate source files into a single file with headers (like all_code.py)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output', '-o',
            type=str,
            default='all_code.py',
            help='Output file path (relative to project root or absolute).'
        )
        parser.add_argument(
            '--exclude', '-e',
            nargs='*',
            default=['venv', '.venv', '.git', '__pycache__', 'migrations', 'node_modules'],
            help='Directory names to exclude from aggregation.'
        )
        parser.add_argument(
            '--ext', '-x',
            nargs='*',
            default=['py', 'html'],
            help='File extensions to include (without dot). Example: -x py html js css'
        )
        parser.add_argument(
            '--include-dirs', '-d',
            nargs='*',
            default=[],
            help='Limit search to these directories (relative to project root). If empty, scan whole project.'
        )

    def handle(self, *args, **options):
        # ✅ احصل على جذر المشروع من إعدادات Django (أدق من Path.cwd())
        try:
            base_dir = getattr(settings, 'BASE_DIR', None)
            if base_dir is None:
                # fallback لو BASE_DIR مش موجودة لأي سبب
                raise AttributeError
            project_root = Path(base_dir).resolve()
        except Exception:
            # fallback أخير على مكان هذا الملف
            project_root = Path(__file__).resolve().parents[4]  # commands/aggregatecodes.py -> management -> ... -> project root (عدّل لو لزم)
            project_root = project_root.resolve()

        output_arg = options['output']
        exclude_dirs = set(options['exclude'])
        include_exts = {ext.lower().lstrip('.') for ext in options['ext']}
        include_dirs = options['include_dirs']

        output_path = Path(output_arg)
        if not output_path.is_absolute():
            output_path = project_root / output_path
        output_path = output_path.resolve()

        # حدد جذور البحث
        search_roots = [project_root]
        if include_dirs:
            search_roots = [(project_root / d).resolve() for d in include_dirs if (project_root / d).exists()]

        try:
            header = f"# Aggregated on {datetime.utcnow().isoformat()} UTC\n"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(header, encoding='utf-8')

            files_to_write = []

            for root in search_roots:
                for path in sorted(root.rglob('*')):
                    # تخطّي الأدلة المستثناة بسرعة
                    if any(part in exclude_dirs for part in path.parts):
                        continue
                    if path.is_file():
                        # امتداد الملف
                        ext = path.suffix.lower().lstrip('.')
                        if ext in include_exts:
                            # تخطّي ملف الإخراج نفسه
                            try:
                                if path.resolve() == output_path:
                                    continue
                            except Exception:
                                pass
                            files_to_write.append(path)

            # كتابة المحتوى
            for fpath in files_to_write:
                try:
                    content = fpath.read_text(encoding='utf-8', errors='replace')
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"Could not read {fpath}: {e}"))
                    continue

                rel = fpath.relative_to(project_root)
                with output_path.open('a', encoding='utf-8') as out:
                    out.write(f"\n\n# ===== FILE: {rel} =====\n")
                    out.write(content)

            self.stdout.write(self.style.SUCCESS(
                f"Aggregated {len(files_to_write)} file(s) into {output_path}"
            ))

        except Exception as e:
            raise CommandError(f"Failed to aggregate: {e}")


# ===== FILE: core/management/commands/build_phrases_ngrams.py =====
from django.core.management.base import BaseCommand
from django.db import transaction
from core.models import Ayah, Phrase, PhraseOccurrence
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


# ===== FILE: core/management/commands/import_page_images.py =====
# core/management/commands/import_page_images.py

import os
from pathlib import Path
from django.core.files import File
from django.core.management.base import BaseCommand
from core.models import Page

class Command(BaseCommand):
    help = "Attach Mushaf page images into Page.image (by page number)."

    def add_arguments(self, p):
        p.add_argument('--images-dir', required=True, help='Folder with page SVG/PNG files')
        p.add_argument('--img-pattern', default='{:03d}.svg', help="Filename pattern, e.g. '{:03d}.svg' or 'page_{:03d}.svg'")
        p.add_argument('--pages', type=int, default=80, help='How many pages to process (start from 1)')

    def handle(self, *args, **options):
        img_dir = Path(options['images_dir'])       # <-- بدل images-dir
        patt    = options['img_pattern']            # <-- بدل img-pattern
        pages   = int(options['pages'])

        total = 0
        for i in range(1, pages+1):
            p, _ = Page.objects.get_or_create(number=i)
            if p.image and p.image.name:
                continue
            img_path = img_dir / patt.format(i)
            if not img_path.exists():
                self.stdout.write(self.style.WARNING(f"Missing file: {img_path}"))
                continue
            with img_path.open('rb') as f:
                p.image.save(img_path.name, File(f), save=True)
                total += 1
        self.stdout.write(self.style.SUCCESS(f"Attached images to {total} pages."))


# ===== FILE: core/management/commands/import_quran_data.py =====
from django.core.management.base import BaseCommand
from core.models import Juz, Quarter, Ayah, Phrase, PhraseOccurrence
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


# ===== FILE: core/management/commands/link_ayat_to_pages.py =====
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


# ===== FILE: core/models.py =====
"""
Database models for the Quran memorization assistant.

These models define the fundamental data structures required
to support users (students), complaints, Quranic metadata, and
test sessions. They are simplified placeholders; relationships
can be expanded to cover more advanced features.
"""
from django.db import models  # type: ignore
from django.contrib.auth.models import User  # type: ignore


class Student(models.Model):
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    def avatar_url(self):
        try:
            if self.avatar and hasattr(self.avatar, "url"):
                return self.avatar.url
        except Exception:
            pass
        return ""  # هنستخدم شكل افتراضي بالـCSS لو فاضي
    """A simple student profile linked to the built-in User model."""

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    display_name = models.CharField(max_length=100)

    def __str__(self) -> str:
        return self.display_name


class Complaint(models.Model):
    """A complaint or suggestion submitted by a student."""

    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    resolved = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f"Complaint by {self.student}: {self.text[:30]}"


class Juz(models.Model):
    """Represents one of the 30 parts of the Qur’an."""

    number = models.PositiveSmallIntegerField(unique=True)
    name = models.CharField(max_length=50, blank=True)

    def __str__(self) -> str:
        return f"Juz {self.number}"


class Quarter(models.Model):
    """Represents a quarter of a Juz (Rubʿ)."""

    juz = models.ForeignKey(Juz, on_delete=models.CASCADE)
    index_in_juz = models.PositiveSmallIntegerField(help_text="1–8 for each Juz")
    label = models.CharField(max_length=100, help_text="Name of the quarter from the opening words of its first verse")

    class Meta:
        unique_together = ('juz', 'index_in_juz')

    def __str__(self) -> str:
        return f"{self.juz} - Quarter {self.index_in_juz}"


class Page(models.Model):
    """Represents a page of the Mushaf with its image."""

    number = models.PositiveSmallIntegerField(unique=True)
    image = models.ImageField(upload_to='pages/')

    def __str__(self) -> str:
        return f"Page {self.number}"


class Ayah(models.Model):
    """Represents a single ayah with its metadata."""

    surah = models.PositiveSmallIntegerField()
    number = models.PositiveSmallIntegerField()
    text = models.TextField()
    page = models.ForeignKey(Page, on_delete=models.SET_NULL, null=True, blank=True)
    quarter = models.ForeignKey(Quarter, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        unique_together = ('surah', 'number')

    def __str__(self) -> str:
        return f"{self.surah}:{self.number}"


class SimilarityGroup(models.Model):
    """Group of similar verses (mutashabehat)."""

    name = models.CharField(max_length=200, help_text="Key phrase that identifies the group")
    ayat = models.ManyToManyField(Ayah, related_name='similarity_groups')

    def __str__(self) -> str:
        return self.name


class Phrase(models.Model):
    text = models.CharField(max_length=200)
    normalized = models.CharField(max_length=200, db_index=True)
    length_words = models.PositiveSmallIntegerField()
    global_freq = models.PositiveIntegerField(default=0)
    confusability = models.FloatField(default=0.0)

    def __str__(self):
        return self.text


class PhraseOccurrence(models.Model):
    phrase = models.ForeignKey(Phrase, related_name='occurrences', on_delete=models.CASCADE)
    ayah = models.ForeignKey(Ayah, on_delete=models.CASCADE)
    start_word = models.PositiveSmallIntegerField()
    end_word = models.PositiveSmallIntegerField()

    class Meta:
        unique_together = ('phrase', 'ayah', 'start_word', 'end_word')
        indexes = [
            models.Index(fields=['ayah']),
            models.Index(fields=['phrase']),
        ]


class TestSession(models.Model):
    """Represents one attempt of a test by a student."""

    # NEW: أنواع الاختبارات (الجديدة + القديمة حفاظًا على التوافق)
    TEST_TYPE_CHOICES = [
        ('similar_count', 'عدد مواضع المتشابهات'),                 # المتاح حاليًا
        ('similar_on_pages', 'مواضع المتشابهات في الصفحات'),        # قريبًا
        ('page_edges_quarters', 'بداية/نهاية الصفحات مع الأرباع'),   # قريبًا
        ('order_juz_quarters', 'ترتيب الأجزاء والأرباع'),            # قريبًا
        ('semantic_similarities', 'متشابهات معاني الآيات'),          # قريبًا

        # القيم القديمة إن كانت موجودة في بيانات سابقة:
        ('similar_only', 'Similar verses only'),
        ('similar_quarters', 'Similar verses & quarters'),
        ('similar_quarters_location', 'Similar verses & quarters with location'),
        ('mixed', 'Mixed'),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    test_type = models.CharField(
        max_length=50,
        choices=TEST_TYPE_CHOICES,
        default='similar_count',
    )
    num_questions = models.PositiveSmallIntegerField(default=10)
    difficulty = models.CharField(
        max_length=10,
        choices=[('easy', 'Easy'), ('medium', 'Medium'), ('hard', 'Hard')],
        default='easy',
    )
    completed = models.BooleanField(default=False)

    # ManyToMany to Juz and Quarter representing scope
    juzs = models.ManyToManyField(Juz, blank=True)
    quarters = models.ManyToManyField(Quarter, blank=True)

    def __str__(self) -> str:
        return f"TestSession {self.id} for {self.student}"


class TestQuestion(models.Model):
    """Single question within a test session."""

    session = models.ForeignKey(TestSession, on_delete=models.CASCADE, related_name='questions')
    similarity_group = models.ForeignKey(SimilarityGroup, on_delete=models.SET_NULL, null=True)
    # store JSON or text representing the student's answer. In a complete implementation
    # this could be structured data (quarter ID, page number, half, etc.).
    student_response = models.TextField(blank=True)
    is_correct = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f"Question {self.id} in {self.session}"


# ===== FILE: core/templates/core/account_settings.html =====
{% extends "core/base.html" %}
{% load static i18n %}

{% block title %}إعدادات الحساب — متواتر{% endblock %}

{% block content %}
<style>
  .acc-wrap{max-width: 880px; margin: 18px auto; padding: 14px; display:grid; gap:14px}
  .acc-card{
    background: linear-gradient(180deg, rgba(255,255,255,.03), rgba(255,255,255,.015));
    border:1px solid rgba(255,255,255,.10);
    border-radius:16px; box-shadow:0 14px 36px rgba(0,0,0,.22);
    padding: 14px;
  }
  .acc-title{ margin:0 0 8px; color:#fff; font-weight:900 }
  .acc-grid{ display:grid; gap:10px }
  .row{ display:grid; gap:8px; align-items:center }
  .two{ grid-template-columns: 160px 1fr }
  @media (max-width:720px){ .two{ grid-template-columns: 1fr } }

  .avatar-lg{ width:84px; height:84px; border-radius:50%; overflow:hidden; background:#0f1118; border:1px solid rgba(255,255,255,.1); display:grid; place-items:center }
  .avatar-lg img{ width:100%; height:100%; object-fit:cover }
  .hint{ color:var(--muted); font-size:.92rem }
  .form-actions{ display:flex; gap:.6rem; flex-wrap:wrap; margin-top:6px }
  .btn-lg{ padding:.7rem 1rem; border-radius:12px; font-weight:900 }
  .input, input[type="file"]{ background:#0f1118; color:#fff; border:1px solid rgba(255,255,255,.12); border-radius:10px; padding:.55rem .65rem; width:100% }
  label{ color:#fff; font-weight:800 }
</style>

<div class="acc-wrap" dir="rtl">

  <!-- بيانات عامة + صورة -->
  <section class="acc-card">
    <h2 class="acc-title">بيانات الحساب</h2>
    <form method="post" enctype="multipart/form-data">
      {% csrf_token %}
      <input type="hidden" name="action" value="update_profile">
      <div class="acc-grid">
        <div class="row two">
          <label>الصورة الشخصية</label>
          <div style="display:flex; gap:10px; align-items:center">
            <span class="avatar-lg">
              {% if student.avatar %}
                <img src="{{ student.avatar.url }}" alt="">
              {% else %}
                <span style="color:#fff; font-weight:900; font-size:24px">{{ request.user.username|slice:":1"|upper }}</span>
              {% endif %}
            </span>
            <input type="file" name="avatar" accept="image/*">
            {% if student.avatar %}
              <label style="display:inline-flex; gap:.35rem; align-items:center">
                <input type="checkbox" name="remove_avatar" value="1">
                <span class="hint">حذف الصورة الحالية</span>
              </label>
            {% endif %}
          </div>
        </div>

        <div class="row two">
          <label for="id_display_name">اسم المستخدم:</label>
          <input type="text" id="id_display_name" name="display_name" class="input" value="{{ profile_form.display_name.value|default:student.display_name }}">
        </div>

        <div class="row two">
          <label for="id_email">البريد الإلكتروني:</label>
          <input type="email" id="id_email" name="email" class="input" placeholder="اختياري" value="{{ profile_form.email.value|default:request.user.email }}">
          <div class="hint">بعد حفظه، يمكنك تسجيل الدخول باسم المستخدم أو البريد الإلكتروني.</div>
        </div>

        <div class="form-actions">
          <button type="submit" class="btn btn-primary btn-lg">حفظ التغييرات</button>
          <a href="{% url 'core:main_menu' %}" class="btn btn-outline btn-lg">الرجوع للرئيسية</a>
        </div>
      </div>
    </form>
  </section>

  <!-- تغيير كلمة المرور -->
  <section class="acc-card">
    <h2 class="acc-title">تغيير كلمة المرور</h2>
    <form method="post">
      {% csrf_token %}
      <input type="hidden" name="action" value="change_password">
      <div class="acc-grid">
        <div class="row two">
          <label for="{{ password_form.old_password.id_for_label }}">كلمة المرور الحالية</label>
          {{ password_form.old_password }}
        </div>
        <div class="row two">
          <label for="{{ password_form.new_password1.id_for_label }}">كلمة المرور الجديدة</label>
          {{ password_form.new_password1 }}
        </div>
        <div class="row two">
          <label for="{{ password_form.new_password2.id_for_label }}">تأكيد كلمة المرور الجديدة</label>
          {{ password_form.new_password2 }}
        </div>
        <div class="hint">
          يجب ألا تقل عن 8 أحرف وتحتوي على أحرف وأرقام (وفقًا لمتطلبات الأمان).
        </div>
        <div class="form-actions">
          <button type="submit" class="btn btn-primary btn-lg">تحديث كلمة المرور</button>
        </div>
      </div>
    </form>
  </section>

</div>
{% endblock %}


# ===== FILE: core/templates/core/base.html =====
{% load i18n static %}
<!doctype html>
<html lang="{{ LANGUAGE_CODE|default:'ar' }}" dir="rtl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{% block title %}متواتر{% endblock %}</title>
  <link rel="stylesheet" href="{% static 'css/mutawatir.css' %}">

  <style>
    .btn { display:inline-flex; align-items:center; contain:layout paint; }

    .badge-alpha{
      display:inline-block; margin-inline-start:.5rem; padding:.15rem .5rem;
      font-size:.75rem; border-radius:.5rem; border:1px solid #d9b44a;
      background:#fffbea; color:#8a6d1d; vertical-align:middle; white-space:nowrap;
    }

    .topbar .container.row{ display:flex; align-items:center; justify-content:space-between; }
    .brand, .actions{ display:flex; align-items:center; }
    .actions{ gap:.6rem; margin-inline-start:auto; }
    .brand-link{ display:flex; align-items:center; gap:.6rem; text-decoration:none }
    .brand-logo{ width:42px; height:42px; }
    .brand-text .brand-name-ar{ font-size:1.18rem; font-weight:900; color:#fff }
    .brand-text .brand-name-en{ font-size:.9rem; opacity:.9; color:#f1cf6b }

    .nav-welcome{
      display:inline-flex; align-items:center; gap:.45rem; direction: rtl;
      font-weight:800; color:#1b1b1b;
      background:linear-gradient(135deg, var(--accent, #f1cf6b), var(--accent-2, #f3e4a8));
      padding:.32rem .6rem; border-radius:999px; border:1px solid rgba(212,175,55,.55);
      box-shadow:0 6px 18px rgba(0,0,0,.12); font-size:.92rem;
    }
    .nav-welcome .dot{
      width:10px; height:10px; border-radius:50%; background:#16a34a;
      box-shadow:0 0 0 6px rgba(22,163,74,.15); animation:pulse 1.8s ease-in-out infinite;
    }
    @keyframes pulse{
      0%,100%{ box-shadow:0 0 0 6px rgba(22,163,74,.15) }
      50%{ box-shadow:0 0 0 9px rgba(22,163,74,.30) }
    }

    .user-cluster{ position:relative; display:flex; align-items:center; gap:.6rem }
    .user-trigger{ display:flex; align-items:center; gap:.5rem; background:transparent; border:0; cursor:pointer;
      padding:.25rem .4rem; border-radius:12px; }
    .user-trigger:focus-visible{ outline:none; box-shadow:0 0 0 3px rgba(241,207,107,.35) }
    .avatar{ width:40px; height:40px; border-radius:50%; overflow:hidden; background:#0f1118; border:1px solid rgba(255,255,255,.10);
      display:inline-grid; place-items:center; }
    .avatar img{ width:100%; height:100%; object-fit:cover; display:block }
    .avatar-fallback{ width:100%; height:100%; display:grid; place-items:center }
    .avatar-fallback svg{ width:72%; height:72%; }

    .btn{ position:relative; overflow:hidden; transition: transform .12s ease, box-shadow .22s ease, background-color .22s ease, border-color .22s ease; will-change: transform; }
    .btn:hover{ transform: translateY(-1px); box-shadow:0 10px 24px rgba(0,0,0,.18) }
    .btn:active{ transform: translateY(0); box-shadow:0 6px 16px rgba(0,0,0,.16) }
    .btn:focus-visible{ outline:none; box-shadow:0 0 0 3px rgba(241,207,107,.45), 0 10px 24px rgba(0,0,0,.18); }
    .btn.btn-primary{ background: linear-gradient(135deg, var(--accent, #f1cf6b), var(--accent-2, #f3e4a8)); color:#0e1a14; border-color: rgba(212,175,55,.65); font-weight:900; }
    .btn.btn-outline{ background: transparent; color: var(--accent, #f1cf6b); border:1px solid var(--accent, #f1cf6b); font-weight:800; }

    /* === Score HUD (ثابت أعلى الصفحة) === */
    .score-hud{
      position: fixed; top: 8px; inset-inline: 0; display: grid; justify-content: center; z-index: 9998;
      pointer-events: none;
    }
    .score-hud__chip{
      pointer-events: auto; display:inline-flex; align-items:center; gap:.6rem;
      background: rgba(2,6,23,.78); color:#fff; border:1px solid rgba(255,255,255,.14);
      padding:.35rem .65rem; border-radius:999px; backdrop-filter: blur(6px);
      box-shadow:0 10px 24px rgba(0,0,0,.25);
    }
    .score-hud__label{ opacity:.85; font-weight:700 }
    .score-hud__value{ font-weight:900; font-variant-numeric: tabular-nums; }
    .score-hud__delta{
      font-weight:900; font-variant-numeric: tabular-nums;
      padding:.05rem .5rem; border-radius:999px; border:1px solid transparent;
      transform: translateY(-4px); opacity:0; transition: all .28s ease;
      white-space:nowrap;
    }
    .score-hud__delta.show{ transform: translateY(0); opacity:1 }
    .score-hud__delta.pos{ background:#052e16; border-color:#166534; color:#22c55e }
    .score-hud__delta.neg{ background:#3f0610; border-color:#7f1d1d; color:#f87171 }

    /* Feedback شريط داخلي */
    .feedback{
      margin:.5rem auto 0; padding:.6rem .8rem; border-radius:12px; border:1px solid transparent;
      font-weight:800; text-align:center; max-width:900px;
    }
    .feedback--success{ background:#052e16; border-color:#166534; color:#22c55e }
    .feedback--warning{ background:#3b2905; border-color:#a16207; color:#fbbf24 }
    .feedback--error  { background:#3f0610; border-color:#7f1d1d; color:#f87171 }
    .feedback--info   { background:#0b1220; border-color:#1f2a44; color:#93c5fd }

    /* Splash */
    .splash-overlay.hide { opacity: 0; pointer-events: none; }
  </style>
</head>
<body>

<header class="topbar">
  <div class="container row">
    <div class="brand">
      <a href="{% if request.user.is_authenticated %}{% url 'core:main_menu' %}{% else %}{% url 'core:landing' %}{% endif %}"
         class="brand-link" aria-label="Mutawatir Home">
        <img
          src="{% static 'img/logo.png' %}"
          srcset="{% static 'img/logo.png' %} 1x, {% static 'img/logo@2x.png' %} 2x"
          class="brand-logo"
          alt="Mutawatir Logo">
        <span class="brand-text">
          <span class="brand-name-ar">متواتر</span>
          <span class="brand-name-en">Mutawatir</span>
        </span>
        {% if IS_ALPHA %}
          <span class="badge-alpha" title="نسخة أولية قيد التطوير">{{ APP_VERSION }}</span>
        {% endif %}
      </a>
    </div>

    <nav class="actions">
      {% if request.user.is_authenticated %}
        <div class="user-cluster">
          <button type="button" class="user-trigger" id="userMenuBtn" aria-expanded="false">
            <span class="avatar" aria-hidden="true">
              {% if student and student.avatar %}
                <img src="{{ student.avatar.url }}" alt="">
              {% else %}
                <span class="avatar-fallback" aria-hidden="true">
                  <svg viewBox="0 0 24 24" role="img" aria-label="user">
                    <path d="M12 12c2.761 0 5-2.686 5-6s-2.239-6-5-6-5 2.686-5 6 2.239 6 5 6zm0 2c-4.418 0-8 2.239-8 5v1h16v-1c0-2.761-3.582-5-8-5z" fill="#9aa3b2"/>
                  </svg>
                </span>
              {% endif %}
            </span>
            <span class="nav-welcome" dir="rtl">
              <span class="dot" aria-hidden="true"></span>
              مرحبًا، {{ student.display_name|default:request.user.username }}
            </span>
            <span class="caret" aria-hidden="true">▾</span>
          </button>
          {% url 'core:account_settings' as account_url %}
          <div class="user-menu" id="userMenu" hidden>
            <a href="{% url 'core:main_menu' %}" class="menu-item">الصفحة الرئيسية</a>
            <a href="{% url 'core:complaint' %}" class="menu-item">الإبلاغ / اقتراح</a>
            {% if account_url %}<a href="{{ account_url }}" class="menu-item">إعدادات الحساب</a>{% endif %}
            <a href="{% url 'core:stats' %}" class="menu-item">إحصائياتك</a>
            <a href="{% url 'core:logout' %}" class="menu-item">تسجيل الخروج</a>
          </div>
        </div>
      {% else %}
        <a class="btn btn-outline" href="{% url 'core:login' %}">{% trans "تسجيل الدخول" %}</a>
        <a class="btn btn-primary" href="{% url 'core:signup' %}">{% trans "إنشاء حساب" %}</a>
      {% endif %}

      <form method="post" action="{% url 'set_language' %}" class="lang-form">
        {% csrf_token %}
        <select name="language" onchange="this.form.submit()" class="input small">
          <option value="ar" {% if LANGUAGE_CODE == 'ar' %}selected{% endif %}>العربية</option>
          <option value="en" {% if LANGUAGE_CODE == 'en' %}selected{% endif %}>English</option>
        </select>
        <input type="hidden" name="next" value="{{ request.get_full_path }}">
      </form>
    </nav>
  </div>
</header>

<!-- Score HUD -->
<div id="score-hud" class="score-hud"
     data-score="{{ score|default:0 }}"
     {% if score_delta is not None %} data-delta="{{ score_delta }}"{% endif %}>
  <div class="score-hud__chip">
    <span class="score-hud__label">نتيجتك</span>
    <span class="score-hud__value" id="scoreValue">{{ score|default:0 }}</span>
    <span class="score-hud__delta" id="scoreDelta" hidden></span>
  </div>
</div>

{% if not suppress_toasts %}
  <!-- Toast root (enabled فقط لو مش معطّل) -->
  <div id="toast-root" class="toast-root" aria-live="polite" aria-atomic="true"></div>
  {% if messages %}
    <div id="server-messages" class="sr-only">
      {% for message in messages %}
        <div data-level="{{ message.tags|default:'info' }}">{{ message }}</div>
      {% endfor %}
    </div>
  {% endif %}
{% endif %}

<main class="container">
  {% block content %}{% endblock %}
</main>

{% if not hide_footer %}
<footer class="footer">
  <div class="container">
    <div class="muted">
      © متواتر — All rights reserved.
      {% if IS_ALPHA %}
        <span class="sep"> • </span>
        <small>
          {{ APP_VERSION }} — نسخة أولية قيد التطوير.
          <a href="{% url 'core:complaint' %}">أبلغ عن مشكلة</a>
        </small>
      {% endif %}
    </div>
  </div>
</footer>
{% endif %}

{% if show_splash %}
<section id="splash" class="splash-overlay" role="status" aria-live="polite">
  <div class="splash-card">
    <div class="splash-logo-wrap">
      <img
        src="{% static 'img/logo.png' %}"
        srcset="{% static 'img/logo.png' %} 1x, {% static 'img/logo@2x.png' %} 2x"
        alt="Mutawatir" class="splash-logo">
    </div>
    <div class="splash-text">
      <blockquote class="hadith">
        <span class="qmark">«</span>
        خيرُكم من تعلَّم القرآن وعلَّمه
        <span class="qmark">»</span>
      </blockquote>
      <div class="hadith-src">— رواه البخاري</div>
    </div>
  </div>
</section>
<script>
  document.addEventListener('DOMContentLoaded', function () {
    const s = document.getElementById('splash');
    if (!s) return;
    requestAnimationFrame(() => s.classList.add('show'));
    setTimeout(() => {
      s.classList.add('hide');
      s.style.pointerEvents = 'none';
      setTimeout(() => s.remove(), 420);
    }, 1600);
  });
</script>
{% endif %}

<script>
  // Ripple (disabled for <a> unless data-ripple present)
  document.addEventListener('click', function(e){
    const btn = e.target.closest('.btn');
    if (!btn) return;
    if (btn.tagName === 'A' && !btn.hasAttribute('data-ripple')) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const rect = btn.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height);
    const r = document.createElement('span');
    r.className = 'ripple';
    r.style.position = 'absolute';
    r.style.width = r.style.height = size + 'px';
    r.style.left = (e.clientX - rect.left - size / 2) + 'px';
    r.style.top  = (e.clientY - rect.top  - size / 2) + 'px';
    btn.appendChild(r);
    setTimeout(() => r.remove(), 500);
  }, false);

  // === Score HUD animation ===
  (function(){
    const hud  = document.getElementById('score-hud');
    if(!hud) return;
    const valueEl = document.getElementById('scoreValue');
    const deltaEl = document.getElementById('scoreDelta');
    const score = parseInt(hud.getAttribute('data-score') || '0', 10);
    const delta = hud.hasAttribute('data-delta') ? parseInt(hud.getAttribute('data-delta') || '0', 10) : 0;
    valueEl.textContent = isNaN(score) ? '0' : String(score);
    if (!isNaN(delta) && delta !== 0){
      deltaEl.textContent = (delta > 0 ? '+' : '') + delta;
      deltaEl.classList.toggle('pos', delta > 0);
      deltaEl.classList.toggle('neg', delta < 0);
      deltaEl.hidden = false;
      requestAnimationFrame(()=> deltaEl.classList.add('show'));
      setTimeout(()=>{
        deltaEl.classList.remove('show');
        setTimeout(()=>{ deltaEl.hidden = true; }, 280);
      }, 1500);
    }
  })();

  {% if not suppress_toasts %}
  // Toasts from Django messages (disabled لو suppress_toasts=True)
  (function(){
    const wrap = document.getElementById('toast-root');
    const src  = document.getElementById('server-messages');
    if(!wrap || !src) return;
    const levelClass = (lvl)=>{
      if(!lvl) return 'toast--info';
      if(lvl.includes('success')) return 'toast--success';
      if(lvl.includes('error'))   return 'toast--error';
      if(lvl.includes('warning')) return 'toast--warning';
      return 'toast--info';
    };
    const show = (text, lvl='info', timeout=3600)=>{
      const t = document.createElement('div');
      t.className = 'toast ' + levelClass(lvl);
      t.innerHTML = '<span>'+ text +'</span><button class="toast__close" aria-label="إغلاق" title="إغلاق">&times;</button>';
      wrap.appendChild(t);
      const close = ()=>{ t.style.animation = 'toast-out .18s ease-in forwards'; setTimeout(()=>t.remove(), 180); };
      t.querySelector('.toast__close').addEventListener('click', close);
      setTimeout(close, timeout);
    };
    src.querySelectorAll('div[data-level]').forEach(function(el, i){
      const lvl = el.getAttribute('data-level') || 'info';
      const text = (el.textContent || '').trim();
      setTimeout(()=>show(text, lvl), i * 350);
    });
  })();
  {% endif %}

  // Toggle user menu
  (function(){
    const btn = document.getElementById('userMenuBtn');
    const menu = document.getElementById('userMenu');
    if(!btn || !menu) return;
    btn.addEventListener('click', ()=>{
      const open = !menu.hasAttribute('hidden');
      if(open){ menu.setAttribute('hidden',''); btn.setAttribute('aria-expanded','false'); }
      else { menu.removeAttribute('hidden'); btn.setAttribute('aria-expanded','true'); }
    });
    document.addEventListener('click', (e)=>{
      if(!menu || menu.hasAttribute('hidden')) return;
      if(!e.target.closest('.user-cluster')){ menu.setAttribute('hidden',''); btn.setAttribute('aria-expanded','false'); }
    });
  })();
</script>

</body>
</html>


# ===== FILE: core/templates/core/complaint.html =====
{% extends "core/base.html" %}
{% load static i18n %}

{% block title %}إبلاغ / اقتراح — متواتر{% endblock %}

{% block content %}
<style>
  .page-shell{min-height:70vh; display:grid; gap:1rem; align-content:start}
  .header-card{
    text-align:center; padding:1.2rem 1rem 1rem;
    border-radius:16px;
    border:1px solid rgba(212,175,55,.22);
    background: linear-gradient(180deg, rgba(255,255,255,.03), rgba(255,255,255,.015));
    box-shadow: 0 18px 44px rgba(0,0,0,.22);
  }
  .pill{
    display:inline-flex; align-items:center; gap:.5rem;
    direction: rtl; /* الدوت في اليمين */
    font-weight:800; color:#1b1b1b;
    background:linear-gradient(135deg,var(--accent, #f1cf6b), var(--accent-2, #f3e4a8));
    padding:.36rem .7rem; border-radius:999px; border:1px solid rgba(212,175,55,.55);
    margin-bottom:.6rem;
  }
  .pill .dot{
    width:10px;height:10px;border-radius:50%;
    background:#16a34a; box-shadow:0 0 0 6px rgba(22,163,74,.15);
    animation:pulse 1.8s ease-in-out infinite;
  }
  @keyframes pulse{
    0%,100%{ box-shadow:0 0 0 6px rgba(22,163,74,.15) }
    50%{ box-shadow:0 0 0 9px rgba(22,163,74,.30) }
  }
  .title{margin:.1rem 0 .35rem; color:#fff; font-weight:900; font-size:clamp(20px,3.2vw,26px)}
  .subtitle{color:var(--muted); max-width:820px; margin:.1rem auto 0}

  /* Form Card */
  .form-card{
    background:linear-gradient(180deg, rgba(255,255,255,.03), rgba(255,255,255,.015));
    border:1px solid rgba(255,255,255,.10);
    border-radius:16px; padding:1rem 1.1rem;
    box-shadow:0 14px 36px rgba(0,0,0,.22);
    display:grid; gap:1rem;
  }
  .group-title{margin:0; color:#fff; font-weight:800; font-size:1.05rem}
  .cats{display:flex; flex-wrap:wrap; gap:.5rem; margin-top:.4rem}
  .cat {
    position:relative;
  }
  .cat input{
    position:absolute; inset:0; opacity:0; pointer-events:none;
  }
  .cat label{
    display:inline-flex; align-items:center; gap:.4rem;
    padding:.45rem .7rem; border-radius:999px; cursor:pointer;
    border:1px solid rgba(212,175,55,.35);
    color:#fefefe; background:rgba(255,255,255,.04);
    transition:.15s ease;
    user-select:none;
  }
  .cat label:hover{ filter:brightness(1.06) }
  .cat input:checked + label{
    background:linear-gradient(135deg,var(--accent, #f1cf6b), var(--accent-2, #f3e4a8));
    color:#1b1b1b; border-color:rgba(212,175,55,.65); font-weight:800;
  }

  .field{display:grid; gap:.4rem}
  .field textarea{
    width:100%; min-height:160px; resize:vertical;
    background:rgba(0,0,0,.25); color:#fff; border:1px solid rgba(255,255,255,.12);
    border-radius:12px; padding:.75rem .9rem; line-height:1.7;
  }
  .counter{color:var(--muted); font-size:.9rem; text-align: start;}
  .form-actions{display:flex; gap:.6rem; flex-wrap:wrap; justify-content:flex-start}
  .btn-lg{padding:.8rem 1.15rem; border-radius:12px; font-weight:900}
</style>

<div class="page-shell">

  <!-- Header -->
  <section class="header-card" dir="rtl">
    <div class="pill">
      <span class="dot" aria-hidden="true"></span>
      إبلاغ / اقتراح
    </div>
    <h1 class="title">ساعدنا نحسّن متواتر</h1>
    <p class="subtitle">
        اختر تصنيفًا أو أكثر، ثم اكتب التفاصيل. سنراجع بلاغك بسرعة ونطوّر التجربة باستمرار.
    </p>
  </section>

  <!-- Messages (لو فيه رسائل Django) -->
  {% if messages %}
    <div style="display:grid; gap:.5rem">
      {% for message in messages %}
        <div class="alert {{ message.tags }}">{{ message }}</div>
      {% endfor %}
    </div>
  {% endif %}

  <!-- Form -->
  <section class="form-card" aria-labelledby="form-title">
    <h2 id="form-title" class="group-title">تفاصيل البلاغ / الاقتراح</h2>

    <form method="post" action="{% url 'core:complaint' %}" novalidate>
      {% csrf_token %}

      <!-- Categories -->
      <div class="field">
        <label class="group-title" style="font-size:1rem">التصنيف</label>
        <div class="cats">
          {% for t in types %}
            <div class="cat">
              <input type="checkbox" id="cat{{ forloop.counter }}" name="category" value="{{ t }}">
              <label for="cat{{ forloop.counter }}">{{ t }}</label>
            </div>
          {% endfor %}
        </div>
      </div>

      <!-- Text -->
      <div class="field">
        <label for="complaint-text" class="group-title" style="font-size:1rem">الوصف</label>
        <textarea id="complaint-text" name="text" placeholder="اكتب المشكلة أو الاقتراح بتفاصيل واضحة…"></textarea>
        <div class="counter"><span id="charCount">0</span> حرف</div>
      </div>

      <!-- Actions -->
      <div class="form-actions">
        <button type="submit" class="btn btn-primary btn-lg">إرسال</button>
        <a href="{% url 'core:main_menu' %}" class="btn btn-outline btn-lg">العودة للرئيسية</a>
      </div>
    </form>
  </section>

</div>

<script>
  // عدّاد الحروف البسيط
  (function(){
    var ta = document.getElementById('complaint-text');
    var out = document.getElementById('charCount');
    if (!ta || !out) return;
    var update = function(){ out.textContent = (ta.value || '').length; };
    ta.addEventListener('input', update);
    update();
  })();
</script>
{% endblock %}


# ===== FILE: core/templates/core/complaint_admin.html =====
{% extends 'core/base.html' %}

{% block title %}الشكاوى (للإدارة){% endblock %}

{% block content %}
  <style>
    .admin-card {
      background:#fff;
      border:2px solid var(--primary);
      border-radius:12px;
      padding:1.25rem 1.5rem;
      box-shadow:0 14px 50px rgba(15,95,59,0.1);
      margin-bottom:1.5rem;
    }
    table {
      width:100%;
      border-collapse: collapse;
      margin-top:0.5rem;
    }
    th, td {
      padding:12px 10px;
      text-align: right;
      border-bottom:1px solid #e6e6e6;
      font-size:0.9rem;
    }
    th {
      background: rgba(15,95,59,0.07);
      font-weight:600;
    }
    .status-badge {
      padding:4px 10px;
      border-radius:999px;
      font-size:0.7rem;
      display:inline-block;
    }
    .resolved { background: #d1f0d8; color:#0f5f3b; }
    .unresolved { background: #ffe7d9; color:#a64400; }
    .btn-small {
      padding:6px 12px;
      border-radius:6px;
      border:none;
      cursor:pointer;
      font-size:0.75rem;
      font-weight:600;
      transition: filter .2s;
    }
    .toggle-btn {
      background: var(--primary-light);
      color:#fff;
    }
    .toggle-btn:hover { filter: brightness(1.1); }
  </style>

  <div class="admin-card">
    <h1 style="margin-top:0;">الشكاوى الواردة</h1>
    <p>هنا كل الشكاوى مع اسم الحساب وتفاصيلها. تقدر تغيّر الحالة لتعليم أنها مُعالجة.</p>

    <table>
      <thead>
        <tr>
          <th>#</th>
          <th>اسم العرض</th>
          <th>اسم المستخدم</th>
          <th>نص الشكوى / الاقتراح</th>
          <th>تاريخ الإرسال</th>
          <th>الحالة</th>
          <th>تحكم</th>
        </tr>
      </thead>
      <tbody>
        {% for c in complaints %}
          <tr>
            <td>{{ forloop.counter }}</td>
            <td>{{ c.student.display_name }}</td>
            <td>{{ c.student.user.username }}</td>
            <td style="white-space: pre-wrap;">{{ c.text }}</td>
            <td>{{ c.created_at }}</td>
            <td>
              {% if c.resolved %}
                <span class="status-badge resolved">محلولة</span>
              {% else %}
                <span class="status-badge unresolved">غير محلولة</span>
              {% endif %}
            </td>
            <td>
              <form method="post" style="display:inline;">
                {% csrf_token %}
                <input type="hidden" name="complaint_id" value="{{ c.id }}">
                <input type="hidden" name="action" value="toggle">
                <button type="submit" class="btn-small toggle-btn">
                  {% if c.resolved %}إلغاء الحل{% else %}وضع كمحلولة{% endif %}
                </button>
              </form>
            </td>
          </tr>
        {% empty %}
          <tr><td colspan="7" style="text-align:center;">ما فيش شكاوى واردة حالياً.</td></tr>
        {% endfor %}
      </tbody>
    </table>
    <div style="margin-top:1rem;">
      <a href="{% url 'core:main_menu' %}" class="btn-small" style="background:#f0f0f0; color: #0f5f3b; border:1px solid var(--primary);">العودة إلى القائمة الرئيسية</a>
    </div>
  </div>
{% endblock %}


# ===== FILE: core/templates/core/context_processors.py =====
from .models import Student, TestSession, TestQuestion

def _score_formula(exams, correct, wrong, unanswered):
    base = correct - 0.6*wrong - 0.2*unanswered
    acc  = (correct/(correct+wrong)) if (correct+wrong) else 0.0
    volume_bonus = min(exams, 30)*2
    return max(0, base + 40*acc + volume_bonus)

def inject_student(request):
    ctx = {}
    if request.user.is_authenticated:
        student, _ = Student.objects.get_or_create(
            user=request.user, defaults={'display_name': request.user.username}
        )
        ctx['student'] = student

        # احسب ترتيب بسيط (نحتاجه للبادج فقط)
        sess_qs = TestSession.objects.filter(student=student)
        exams = sess_qs.count()
        if exams >= 1:
            ans_qs = TestQuestion.objects.filter(session__in=sess_qs)
            correct = ans_qs.filter(is_correct=True).count()
            wrong   = ans_qs.filter(is_correct=False).count()
            unanswered = 0
            for s in sess_qs.only('id','num_questions'):
                answered = TestQuestion.objects.filter(session=s).count()
                unanswered += max(0, (s.num_questions or 0) - answered)
            my_score = _score_formula(exams, correct, wrong, unanswered)

            # رُتبة تقريبية: احسب كم واحد أعلى مني
            higher = 0
            for st in Student.objects.exclude(id=student.id):
                qs = TestSession.objects.filter(student=st)
                ex = qs.count()
                if ex < 1: 
                    continue
                ans = TestQuestion.objects.filter(session__in=qs)
                c = ans.filter(is_correct=True).count()
                w = ans.filter(is_correct=False).count()
                un = 0
                for s in qs.only('id','num_questions'):
                    a = TestQuestion.objects.filter(session=s).count()
                    un += max(0, (s.num_questions or 0) - a)
                sc = _score_formula(ex, c, w, un)
                if sc > my_score:
                    higher += 1
                    if higher >= 3:  # نحتاج فقط نعرف هل ضمن الثلاثة الأوائل
                        break
            ctx['my_rank'] = higher + 1  # 1..N (تقريبي لكنه كافي للبادج)
    return ctx


# ===== FILE: core/templates/core/index.html =====
{% extends 'core/base.html' %}
{% block title %}إدخال الاسم{% endblock %}
{% block content %}
  <h1>مرحباً بك في تطبيق متشابهات القرآن</h1>
  <p>فضلاً أدخل اسمك للمتابعة:</p>
  <form method="post">
    {% csrf_token %}
    <input type="text" name="display_name" placeholder="اسمك"
           required style="padding:0.5rem; margin-bottom:0.5rem; width:100%;">
    <button type="submit">دخول</button>
  </form>
{% endblock %}


# ===== FILE: core/templates/core/landing.html =====
{% extends 'core/base.html' %}
{% load i18n %}

{% block title %}Mutawatir — متواتر{% endblock %}

{% block content %}
<section class="hero home">
  <div class="hero-inner">
    <img src="/static/img/logo.png" alt="Mutawatir" class="logo">
    <h1 class="hero-title">متواتر — Mutawatir</h1>
    <p class="hero-subtitle">منصة متطورة لاختبار وتثبيت حفظ القرآن، وترسيخ صورة المصحف في الذاكرة.</p>
    <div class="cta">
      <a class="btn btn-primary" href="{% url 'core:login' %}">تسجيل الدخول</a>
      <a class="btn btn-outline" href="{% url 'core:signup' %}">إنشاء حساب</a>
    </div>
  </div>
</section>

<section class="card" style="margin-top:1rem">
  <h3>عن متواتر</h3>
  <p>
    "متواتر" هو موقع تفاعلي مبتكر يهدف إلى مساعدة حفظة القرآن الكريم على اختبار وتقوية حفظهم، مع التركيز على الآيات المتشابهة.
    يوفر للمستخدمين اختبارات دقيقة تُبنى على اختيارهم للأجزاء أو الأرباع أو السور، مع عرض النتائج والتقييمات التفصيلية،
    مما يساعدهم على اكتشاف نقاط القوة ومواطن النسيان، وتحسين أدائهم بأسلوب عملي وفعّال.
    كما يساهم في ترسيخ صورة صفحات المصحف في الذاكرة، ليحفظ القارئ القرآن وكأنه يراه أمامه صفحةً صفحة.
  </p>
</section>
{% endblock %}


# ===== FILE: core/templates/core/leaderboard.html =====
{% extends "core/base.html" %}
{% load static i18n %}

{% block title %}لوحة المنافسة — متواتر{% endblock %}

{% block content %}
<style>
  .board-shell{min-height:72vh; display:grid; gap:1rem; align-content:start}
  .head{
    display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:.6rem;
    padding:.9rem 1rem; border-radius:16px;
    background:linear-gradient(180deg, rgba(255,255,255,.03), rgba(255,255,255,.015));
    border:1px solid rgba(255,255,255,.10); box-shadow:0 14px 36px rgba(0,0,0,.22);
  }
  .head h1{margin:0; color:#fff; font-weight:900}
  .table-wrap{
    overflow:auto;
    background:linear-gradient(180deg, rgba(255,255,255,.03), rgba(255,255,255,.015));
    border:1px solid rgba(255,255,255,.10); border-radius:16px; box-shadow:0 14px 36px rgba(0,0,0,.22);
  }
  table{width:100%; border-collapse:separate; border-spacing:0}
  thead th{
    text-align:center; color:#e7efe9; font-weight:900; padding:.75rem .6rem; position:sticky; top:0; background:#071510;
  }
  tbody td{padding:.65rem .6rem; border-top:1px solid rgba(255,255,255,.07); text-align:center; color:#e9f5ef}
  tbody tr:nth-child(odd){background:rgba(255,255,255,.02)}
  .player{
    display:flex; gap:.55rem; align-items:center; justify-content:flex-start; color:#fff; font-weight:800;
  }
  .avatar{width:30px; height:30px; border-radius:50%; overflow:hidden; background:#0b1713; display:inline-grid; place-items:center; border:1px solid rgba(255,255,255,.12)}
  .avatar img{width:100%; height:100%; object-fit:cover}
  .rank{
    font-weight:900; width:2.8rem; text-align:center; border-radius:999px; padding:.25rem .45rem; margin-inline:auto;
    background:#0b1713; border:1px solid rgba(255,255,255,.12); color:#fff;
  }
  .r1{background:linear-gradient(135deg,#ffe08a,#e7b200); color:#1b1b1b}
  .r2{background:linear-gradient(135deg,#e6e9ef,#9aa3b2); color:#1b1b1b}
  .r3{background:linear-gradient(135deg,#ffd2a6,#b66a28); color:#1b1b1b}
  .badge{margin-inline-start:.35rem}
  .t-center{text-align:center}
</style>

<div class="board-shell">
  <div class="head">
    <h1>لوحة المنافسة</h1>
    <div class="actions">
      <a href="{% url 'core:main_menu' %}" class="btn btn-outline">الرجوع للرئيسية</a>
    </div>
  </div>

  <div class="table-wrap">
    <table dir="rtl">
      <thead>
        <tr>
          <th>#</th>
          <th>الطالب</th>
          <th>النقاط</th>
          <th>الامتحانات</th>
          <th>صحيح</th>
          <th>خطأ</th>
          <th>غير مُجاب</th>
          <th>الدقة</th>
        </tr>
      </thead>
      <tbody>
        {% for r in rows %}
        <tr>
          <td>
            <span class="rank {% if r.rank == 1 %}r1{% elif r.rank == 2 %}r2{% elif r.rank == 3 %}r3{% endif %}">
              {{ r.rank }}
            </span>
          </td>
          <td>
            <span class="player">
              <span class="avatar">
                {% if r.avatar %}<img src="{{ r.avatar }}" alt="">{% else %}<span class="fallback">👤</span>{% endif %}
              </span>
              {{ r.display_name }}
              {% if r.rank <= 3 %}
                <span class="badge">{% if r.rank == 1 %}🥇{% elif r.rank == 2 %}🥈{% else %}🥉{% endif %}</span>
              {% endif %}
            </span>
          </td>
          <td><b>{{ r.score }}</b></td>
          <td>{{ r.exams }}</td>
          <td>{{ r.correct }}</td>
          <td>{{ r.wrong }}</td>
          <td>{{ r.unanswered }}</td>
          <td class="t-center">
            {% if r.acc_percent is not None %}{{ r.acc_percent|floatformat:2 }}%{% else %}—{% endif %}
          </td>
        </tr>
        {% empty %}
        <tr><td colspan="8" class="t-center">لا توجد بيانات بعد.</td></tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>
{% endblock %}


# ===== FILE: core/templates/core/login.html =====
{% extends "core/base.html" %}
{% load static i18n %}

{% block title %}تسجيل الدخول — متواتر{% endblock %}

{% block content %}
<style>
  .auth-shell{
    min-height: 72vh;
    display: grid;
    place-items: center;
  }
  .auth-card{
    width: 100%;
    max-width: 420px;
    background: linear-gradient(180deg, rgba(255,255,255,.03), rgba(255,255,255,.015));
    border: 1px solid rgba(255,255,255,.10);
    border-radius: 16px;
    box-shadow: 0 18px 48px rgba(0,0,0,.28);
    padding: 1.1rem 1.15rem;
  }
  .auth-title{margin: .25rem 0 .9rem; color: #fff; font-weight: 900; letter-spacing: .2px; text-align:center}
  .auth-lead{margin: -.35rem 0 1rem; color: var(--muted); text-align:center}

  .form-control{display:grid; gap:.35rem; margin:.55rem 0}
  .form-control label{font-weight:800; color:#f1f6f3}
  .input{width:100%; background:#09130f; border:1px solid rgba(255,255,255,.16); color:var(--text); border-radius:12px; padding:.7rem .85rem}
  .input::placeholder{color:#dbe7e1; opacity:.9}

  .pwd-wrap{position:relative}
  .input.has-eye{padding-left: 2.3rem;}
  .eye-toggle{
    position:absolute; left:.45rem; top:50%; transform: translateY(-50%);
    display:grid; place-items:center;
    width: 28px; height: 28px;
    border: 1px solid rgba(255,255,255,.16);
    background:#0a1713; color: var(--text);
    border-radius: 8px; cursor: pointer;
  }
  .eye-toggle svg{width:18px; height:18px; display:block}
  .eye-toggle .icon-off{display:none}
  .eye-toggle[aria-pressed="true"] .icon-on{display:none}
  .eye-toggle[aria-pressed="true"] .icon-off{display:block}

  .auth-actions{display:flex; gap:.6rem; align-items:center; justify-content:center; margin-top: .9rem}
  .auth-links{display:flex; gap:.5rem; flex-wrap:wrap}
  .auth-links a{color:var(--accent); font-weight:800}
  .hint{ color:var(--muted); font-size:.92rem }
</style>

<div class="auth-shell">
  <div class="auth-card">
    <h1 class="auth-title">تسجيل الدخول</h1>
    <p class="auth-lead">ادخل بياناتك للمتابعة.</p>

    <form method="post" action="{% url 'core:login' %}">
      {% csrf_token %}
      <div class="form-control">
        <label for="id_username">اسم المستخدم / البريد الإلكتروني</label>
        <input id="id_username" name="username" class="input" placeholder="username أو email" required autofocus>
        <div class="hint">يمكنك إدخال اسم المستخدم أو بريدك الإلكتروني.</div>
      </div>

      <div class="form-control">
        <label for="id_password">كلمة المرور</label>
        <div class="pwd-wrap">
          <input id="id_password" name="password" type="password" class="input has-eye" placeholder="••••••••" required>
          <button type="button" id="togglePwd" class="eye-toggle" aria-label="إظهار كلمة المرور" aria-pressed="false">
            <!-- عين -->
            <svg class="icon-on" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Z" stroke="currentColor" stroke-width="2"/>
              <circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="2"/>
            </svg>
            <!-- عين متشطّبة -->
            <svg class="icon-off" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M3 3l18 18" stroke="currentColor" stroke-width="2"/>
              <path d="M2 12s3.5-6 10-6c-2.3 0-4.2.7-5.7 1.7M22 12s-3.5 6-10 6c-2.3 0-4.2-.7-5.7-1.7" stroke="currentColor" stroke-width="2"/>
              <circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="2"/>
            </svg>
          </button>
        </div>
      </div>

      <div class="auth-actions">
        <button class="btn btn-primary" type="submit">تسجيل الدخول</button>
      </div>

      <div class="auth-actions">
        <div class="auth-links">
          <a href="{% url 'core:signup' %}">ليس لديك حساب؟ أنشئ حسابًا</a>
        </div>
      </div>
    </form>
  </div>
</div>

<script>
  (function(){
    const btn = document.getElementById('togglePwd');
    const input = document.getElementById('id_password');
    if(btn && input){
      btn.addEventListener('click', ()=>{
        const show = input.getAttribute('type') === 'password';
        input.setAttribute('type', show ? 'text' : 'password');
        btn.setAttribute('aria-pressed', show ? 'true' : 'false');
        btn.setAttribute('aria-label', show ? 'إخفاء كلمة المرور' : 'إظهار كلمة المرور');
      });
    }
  })();
</script>
{% endblock %}


# ===== FILE: core/templates/core/main_menu.html =====
{% extends "core/base.html" %}
{% load static i18n %}

{% block title %}الرئيسية — متواتر{% endblock %}

{% if IS_ALPHA %}
<div id="alpha-banner" class="alpha-banner" role="status">
  هذه نسخة <strong>{{ APP_VERSION }}</strong> — ما زلنا نُحسّن التجربة. لو قابلتك مشكلة
  <a href="{% url 'core:complaint' %}">بلغّنا من هنا</a>.
  <button id="alpha-dismiss" type="button" aria-label="إغلاق">×</button>
</div>
{% endif %}

{% block content %}
<style>
  /* إخفاء تحية النافبار في صفحة الهوم فقط */
  .nav-welcome, #nav-welcome, .top-welcome { display:none !important; }

  .home-shell{min-height:72vh; display:grid; align-content:start; gap:1.2rem}
  .welcome{
    text-align:center;
    padding:1.4rem 1rem 1rem;
    border-radius:16px;
    border:1px solid rgba(212,175,55,.22);
    background: linear-gradient(180deg, rgba(255,255,255,.03), rgba(255,255,255,.015));
    box-shadow: 0 18px 44px rgba(0,0,0,.22);
  }
  .welcome h1{
    margin:.2rem 0 .5rem; color:#fff; font-weight:900; letter-spacing:.2px; font-size:clamp(20px,3.2vw,26px)
  }
  .welcome .lead{ color:var(--muted); max-width:820px; margin:.2rem auto 0; }

  .chip{
    display:inline-flex;align-items:center;gap:.45rem;
    direction: rtl; /* الدوت في اليمين */
    font-weight:800; color:#1b1b1b;
    background:linear-gradient(135deg,var(--accent),var(--accent-2));
    padding:.38rem .7rem; border-radius:999px; border:1px solid rgba(212,175,55,.55);
  }
  .chip .dot{
    width:10px;height:10px;border-radius:50%;
    background:#16a34a; /* أخضر */
    box-shadow:0 0 0 6px rgba(22,163,74,.15);
    animation:pulse 1.8s ease-in-out infinite;
  }
  @keyframes pulse{
    0%,100%{ box-shadow:0 0 0 6px rgba(22,163,74,.15) }
    50%{ box-shadow:0 0 0 9px rgba(22,163,74,.30) }
  }
  .badge-medal{margin-inline-start:.4rem; font-weight:900}

  .home-cta{display:flex; gap:.6rem; justify-content:center; flex-wrap:wrap; margin-top:1rem}
  .btn-lg{padding:.8rem 1.15rem; border-radius:12px; font-weight:900}

  .grid-cards{display:grid; grid-template-columns:repeat(3,1fr); gap:.9rem}
  @media (max-width: 900px){ .grid-cards{grid-template-columns:1fr} }
  .cardx{
    position:relative;
    background:linear-gradient(180deg, rgba(255,255,255,.03), rgba(255,255,255,.015));
    border:1px solid rgba(255,255,255,.10);
    border-radius:16px; padding:1.1rem 1.15rem;
    box-shadow:0 14px 36px rgba(0,0,0,.22);
    display:grid; gap:.5rem;
  }
  .cardx h3{margin:0; color:#fff; font-weight:900}
  .cardx p{margin:0; color:var(--muted)}
  .cardx .go{justify-self:start; margin-top:.35rem}

  /* إحصائيات */
  .stats-grid{
    display:grid; grid-template-columns:repeat(4,1fr); gap:.6rem; margin:.2rem 0 .4rem;
  }
  @media(max-width:700px){ .stats-grid{grid-template-columns:repeat(2,1fr)} }
  .stat{
    background:#0f1118; border:1px solid rgba(255,255,255,.10);
    border-radius:14px; padding:.65rem .7rem; text-align:center;
    box-shadow:0 10px 28px rgba(0,0,0,.20);
  }
  .stat .num{display:block; font-weight:900; font-size:clamp(18px,4vw,24px); color:#fff}
  .stat .lbl{display:block; font-weight:800; color:#9aa3b2; margin-top:.15rem; font-size:.95rem}

  .title-underline{
    height:2px; background:linear-gradient(90deg, transparent, var(--accent), transparent);
    border-radius:2px; margin:.35rem auto 0; width:180px; opacity:.65;
  }

  .about{
    margin-top:1rem;
    background:linear-gradient(135deg, #fff8ec22, #f3efe622);
    border-inline-start:6px solid var(--accent);
    padding: .8rem 1rem; border-radius:12px;
    box-shadow:0 10px 30px rgba(212,175,55,.15);
  }
  .about .title{margin:.1rem 0 .4rem; color:#fff; font-weight:900}
  .about p{margin:0; color:#e9f5ef}
</style>

<div class="home-shell">

  <section class="welcome">
    <!-- بادج الترحيب (الدوت في اليمين) -->
    <div class="chip" style="margin-bottom:.55rem">
      <span class="dot" aria-hidden="true"></span>
      مرحبًا، {{ student.display_name|default:request.user.username }}
      {% if my_rank and my_rank|add:0 <= 3 %}
        <span class="badge-medal">
          {% if my_rank == 1 %}🥇{% elif my_rank == 2 %}🥈{% else %}🥉{% endif %} #{{ my_rank }}
        </span>
      {% endif %}
    </div>

    <h1>متواتر — <span style="color:var(--accent)">Mutawatir</span></h1>
    <div class="title-underline"></div>
    <p class="lead">
      منصة متطورة لاختبار وتثبيت حفظ القرآن، وترسيخ صورة المصحف في الذاكرة.
    </p>

    <div class="home-cta">
      <!-- تم تغيير الوجهة إلى كتالوج الاختبارات -->
      <a href="/tests/" class="btn btn-primary btn-lg">بدء اختبار جديد</a>
      {% if request.session.questions %}
        <a href="{% url 'core:test_question' %}" class="btn btn-outline btn-lg">استكمال الاختبار الحالي</a>
      {% endif %}
      <a href="{% url 'core:complaint' %}" class="btn btn-outline btn-lg">إبلاغ / اقتراح</a>
    </div>
  </section>

<section class="grid-cards" aria-label="الأقسام الرئيسية">
  <article class="cardx">
    <h3>اختبارات الحفظ</h3>
    <p>اختر نوع الاختبار ثم حدّد نطاقك (الأجزاء/الأرباع/السور) وابدأ.</p>
    <!-- تم تغيير الوجهة إلى كتالوج الاختبارات -->
    <a href="/tests/" class="btn btn-primary go">ابدأ الآن</a>
  </article>

  <article class="cardx">
    <h3>الإبلاغ والملاحظات</h3>
    <p>واجهت مشكلة أو عندك اقتراح لتحسين التجربة؟ شاركنا رأيك لنحسّن المنصة باستمرار.</p>
    <a href="{% url 'core:complaint' %}" class="btn btn-outline go">إرسال ملاحظة</a>
  </article>

  <!-- إحصائياتك (ستايل مماثل لصفحة /stats/) -->
  <article class="cardx">
    <h3>إحصائياتك</h3>

    <style>
      .stats-tiles{
        display:grid;
        grid-template-columns:repeat(4,1fr);
        gap:.6rem;
        margin:.4rem 0 .6rem;
      }
      @media(max-width:700px){ .stats-tiles{grid-template-columns:repeat(2,1fr)} }
      .tile{
        background:#0b0f16;
        border:1px solid rgba(255,255,255,.10);
        border-radius:14px;
        padding:.8rem .9rem;
        text-align:center;
        box-shadow:0 10px 28px rgba(0,0,0,.18);
      }
      .tile .v{display:block; font-weight:900; font-size:clamp(22px,4.6vw,28px); color:#fff}
      .tile .k{display:block; font-weight:800; color:#9aa3b2; margin-top:.2rem; font-size:.95rem}
    </style>

    <div class="stats-tiles">
      <div class="tile"><span class="v">{{ stats.exams }}</span><span class="k">امتحانات</span></div>
      <div class="tile"><span class="v">{{ stats.correct }}</span><span class="k">صحيح</span></div>
      <div class="tile"><span class="v">{{ stats.wrong }}</span><span class="k">خطأ</span></div>
      <div class="tile"><span class="v">{{ stats.unanswered }}</span><span class="k">غير مُجاب</span></div>
    </div>

    <a href="{% url 'core:stats' %}" class="btn btn-outline go">عرض تفصيلي</a>
  </article>
</section>


    <!-- حسابك -->
    <article class="cardx">
      <h3>حسابك</h3>
      <p>اسم العرض: <strong>{{ student.display_name|default:request.user.username }}</strong></p>
      {% if request.user.email %}
        <p>البريد: <strong>{{ request.user.email }}</strong></p>
      {% endif %}
      <div style="display:flex; gap:.5rem; flex-wrap:wrap; margin-top:.35rem">
        <a href="{% url 'core:account_settings' %}" class="btn btn-primary">تعديل معلومات الحساب</a>
        <a href="{% url 'core:logout' %}" class="btn btn-outline">تسجيل الخروج</a>
        {% if request.session.questions %}
          <a href="{% url 'core:test_question' %}" class="btn btn-outline">متابعة الاختبار</a>
        {% endif %}
      </div>
    </article>

    <!-- كارت اللوحة -->
    <article class="cardx">
      <h3>لوحة المنافسة</h3>
      <p>شاهد ترتيب الطلاب حسب الأداء والنشاط.</p>
      {% if my_rank %}<p>ترتيبك الحالي: <b>#{{ my_rank }}</b></p>{% endif %}
      <a href="{% url 'core:leaderboard' %}" class="btn btn-primary go">فتح اللوحة</a>
    </article>
  </section>

  <section class="about" aria-labelledby="about-title">
    <h2 id="about-title" class="title">عن متواتر</h2>
    <p>
      "متواتر" هو موقع تفاعلي مبتكر يهدف إلى مساعدة حفظة القرآن الكريم على اختبار وتقوية حفظهم،
      مع التركيز على الآيات المتشابهة. يوفر للمستخدمين اختبارات دقيقة تُبنى على اختيارهم للأجزاء أو الأرباع أو السور،
      مع عرض النتائج والتقييمات التفصيلية، مما يساعد على التثبيت وترسيخ صورة المصحف في الذاكرة.
    </p>
  </section>

</div>

<!-- إخفاء أي "مرحب" في الهيدر بجوار "تسجيل الخروج" على هذه الصفحة فقط -->
<script>
  document.addEventListener('DOMContentLoaded', function(){
    function hideNavWelcome(){
      var containers = document.querySelectorAll('header, nav, .navbar, .topbar, .site-header');
      containers.forEach(function(h){
        var hasLogout = /(تسجيل الخروج|Log ?out)/.test((h.textContent||'')); if(!hasLogout) return;
        h.querySelectorAll('*').forEach(function(el){
          if(el.children.length===0){
            var t=(el.textContent||'').trim();
            if(/مرحب/.test(t)){ el.style.display='none'; }
          }
        });
      });
    }
    hideNavWelcome();
    new MutationObserver(hideNavWelcome).observe(document.body,{subtree:true,childList:true});
  });
</script>
{% endblock %}


# ===== FILE: core/templates/core/pages_choose_juz.html =====
{% extends "core/base.html" %}
{% load i18n %}

{% block title %}اختيار الجزء — متواتر{% endblock %}

{% block content %}
<style>
  .wrap{min-height:70vh; display:grid; gap:1rem; align-content:start}
  .hero{ text-align:center; padding:.6rem 0 .2rem }
  .hero h1{ margin:.2rem 0 .4rem; color:#fff; font-weight:900; font-size:clamp(20px,3.2vw,26px) }
  .hero p{ color:var(--muted); margin:0 auto; max-width:820px }
  .grid{ display:grid; grid-template-columns:repeat(4,1fr); gap:.8rem }
  @media (max-width: 900px){ .grid{ grid-template-columns:1fr 1fr } }
  @media (max-width: 560px){ .grid{ grid-template-columns:1fr } }
  .card{
    border:1px solid rgba(255,255,255,.10); border-radius:14px;
    background:linear-gradient(180deg, rgba(255,255,255,.03), rgba(255,255,255,.015));
    padding:.9rem; display:grid; gap:.4rem; box-shadow:0 12px 30px rgba(0,0,0,.2)
  }
  .card h3{ margin:0; color:#fff; font-weight:900 }
  .muted{ color:var(--muted); margin:0 0 .3rem }
  .actions{ display:flex; flex-wrap:wrap; gap:.5rem; justify-content:center; margin-top:.4rem }
  .empty{ text-align:center; border:1px dashed rgba(255,255,255,.25); border-radius:14px; padding:1rem }
</style>

<div class="wrap">
  <div class="hero">
    <h1>اختر الجزء للموضع الأول</h1>
    <p>
      اختر الجزء الذي يحتوي على أول موضع من مواضع العبارة
      <b>«{{ current_phrase|default:"—" }}»</b>
      من قائمة الأجزاء داخل نطاقك المختار.
    </p>
    {% if feedback %}
      <div class="feedback feedback--{{ feedback.level|default:'info' }}">{{ feedback.text }}</div>
    {% endif %}
  </div>

  {% with items=juz_numbers %}
    {% if items %}
      <div class="grid" role="list">
        {% for jno in items %}
          <article class="card" role="listitem">
            <h3>الجزء {{ jno }}</h3>
            <p class="muted">سيفتح قائمة أرباع هذا الجزء.</p>
            <a class="btn btn-primary" href="{% url 'core:pages_choose_quarter' jno %}">اختيار هذا الجزء</a>
          </article>
        {% endfor %}
      </div>
    {% else %}
      <div class="empty">
        <p class="muted"><strong>لا توجد أجزاء ضمن النطاق الحالي.</strong></p>
        {% if no_juz_reason %}
          <p class="muted">{{ no_juz_reason }}</p>
        {% endif %}
        <div class="actions" style="margin-top:.6rem">
          <a class="btn btn-outline" href="{% url 'core:test_selection' %}">العودة لاختيار النطاق</a>
        </div>
      </div>
    {% endif %}
  {% endwith %}

  <div class="actions">
    <a class="btn btn-outline" href="{% url 'core:test_question' %}">رجوع للسؤال</a>
  </div>
</div>
{% endblock %}


# ===== FILE: core/templates/core/pages_choose_quarter.html =====
{% extends "core/base.html" %}
{% load i18n %}

{% block title %}اختيار الربع — متواتر{% endblock %}

{% block content %}
<style>
  .wrap{min-height:70vh; display:grid; gap:1rem; align-content:start}
  .hero{ text-align:center; padding:.6rem 0 .2rem }
  .hero h1{ margin:.2rem 0 .4rem; color:#fff; font-weight:900; font-size:clamp(20px,3.2vw,26px) }
  .hero p{ color:var(--muted); margin:0 auto; max-width:820px }
  .grid{ display:grid; grid-template-columns:repeat(4,1fr); gap:.8rem }
  @media (max-width: 900px){ .grid{ grid-template-columns:1fr 1fr } }
  @media (max-width: 560px){ .grid{ grid-template-columns:1fr } }
  .card{
    border:1px solid rgba(255,255,255,.10); border-radius:14px;
    background:linear-gradient(180deg, rgba(255,255,255,.03), rgba(255,255,255,.015));
    padding:.9rem; display:grid; gap:.35rem; box-shadow:0 12px 30px rgba(0,0,0,.2)
  }
  .card h3{ margin:0; color:#fff; font-weight:900 }
  .muted{ color:var(--muted) }
  .actions{ display:flex; gap:.6rem; justify-content:center; flex-wrap:wrap }
</style>

<div class="wrap">
  <div class="hero">
    <h1>اختيار الأرباع — الجزء {{ juz_no }}</h1>
    <p>
      اختر الربع الذي يبدأ فيه أول موضع من مواضع العبارة
      <b>«{{ current_phrase|default:"—" }}»</b>
      داخل هذا الجزء.
    </p>
    {% if feedback %}
      <div class="feedback feedback--{{ feedback.level|default:'info' }}">{{ feedback.text }}</div>
    {% endif %}
  </div>

  <div class="grid" role="list">
    {% for q in quarters %}
      <article class="card" role="listitem">
        <h3>الربع {{ q.index_in_juz }}</h3>
        <p class="muted">{{ q.label }}</p>
        <a class="btn btn-primary" href="{% url 'core:pages_quarter_pick' q.id %}">فتح صفحات هذا الربع</a>
      </article>
    {% endfor %}
  </div>

  <div class="actions">
    <a class="btn btn-outline" href="{% url 'core:pages_choose_juz' %}">رجوع لاختيار الجزء</a>
  </div>
</div>
{% endblock %}


# ===== FILE: core/templates/core/quarter_pages.html =====
{% extends "core/base.html" %}
{% load i18n %}

{% block title %}صفحات الربع — متواتر{% endblock %}

{% block content %}
<style>
  .wrap{min-height:70vh; display:grid; gap:1rem; align-content:start}
  .hero{ text-align:center; padding:.6rem 0 .2rem }
  .hero h1{ margin:.2rem 0 .4rem; color:#fff; font-weight:900; font-size:clamp(20px,3.2vw,26px) }

  .note{
    margin:10px auto 0; padding:8px 12px; border:1px solid #1f2a44;
    background:#0b1220; border-radius:10px; font-size:.95rem; color:#cfe3ff;
    max-width:1000px;
  }
  .note b{ color:#fff }
  .ok{color:#22c55e}
  .err{color:#f87171}

  .layout{display:grid; grid-template-columns:2fr 1fr; gap:20px; align-items:start; margin-top:12px}
  @media (max-width: 900px){ .layout{ grid-template-columns:1fr } }

  .grid{display:grid; grid-template-columns:repeat(auto-fill,minmax(180px,1fr)); gap:12px}
  .card{
    border:1px solid rgba(255,255,255,.10); border-radius:12px; padding:10px;
    background:linear-gradient(180deg, rgba(255,255,255,.03), rgba(255,255,255,.015));
  }
  .card .thumb{
    width:100%; height:220px; object-fit:contain; background:#0f172a; border-radius:8px;
    border:1px solid rgba(255,255,255,.06); display:block;
  }
  .card .title{ font-weight:800; color:#fff; margin-bottom:6px }

  .sidebar{
    position:sticky; top:8px; border:1px solid rgba(255,255,255,.10);
    padding:10px; border-radius:12px;
    background:linear-gradient(180deg, rgba(255,255,255,.03), rgba(255,255,255,.015));
  }
  .sidebar h3{ margin:0 0 8px; color:#fff }

  .ayah{
    padding:8px 10px; border:1px solid rgba(255,255,255,.08);
    border-radius:10px; margin:8px 0; background:rgba(2,6,23,.35);
  }
  .ayah:hover{ background:rgba(2,6,23,.55) }
  .ayah b{ color:#fff }
  .ayah .t{ font-size:13px; color:#cbd5e1; margin-top:4px }

  .btn-s{ cursor:pointer; padding:.45rem .6rem; border-radius:10px; border:1px solid rgba(212,175,55,.65);
          background:linear-gradient(135deg, var(--accent, #f1cf6b), var(--accent-2, #f3e4a8));
          font-weight:900; color:#0e1a14 }
</style>

<div class="wrap">
  <div class="hero">
    <h1>صفحات الربع — {{ qid }}</h1>
    {% if feedback %}
      <div class="feedback feedback--{{ feedback.level|default:'info' }}">{{ feedback.text }}</div>
    {% endif %}
  </div>

  <div class="note">
    اختر صفحة من الشبكة ثم اضغط <b>عرض آيات الصفحة</b> لاختيار <b>أول آية</b> في الربع.
    <span id="msg"></span>
  </div>

  <div class="layout">
    <div>
      <div class="grid" id="pages">
        {% for p in pages %}
        <div class="card">
          <div class="title">صفحة {{ p.number }}</div>
          {% comment %}
            نستخدم عرض الـ SVG عبر الـ view الموجود عندك: page_svg
          {% endcomment %}
          <img class="thumb" src="{% url 'core:page_svg' p.number %}" alt="صفحة {{ p.number }}">
          <div style="margin-top:10px">
            <button class="btn-s" onclick="loadAyat({{ p.number }})">عرض آيات الصفحة</button>
          </div>
        </div>
        {% endfor %}
      </div>
    </div>

    <aside class="sidebar">
      <h3>آيات الصفحة <span id="pno">—</span></h3>
      <div id="ayat"></div>
    </aside>
  </div>
</div>

<script>
function getCookie(name){
  const parts = document.cookie.split(';').map(s=>s.trim());
  for(const c of parts){
    if(c.startsWith(name+'=')) return decodeURIComponent(c.substring(name.length+1));
  }
  return '';
}

function setMsg(text, ok=true){
  const el = document.getElementById('msg');
  el.className = ok ? 'ok' : 'err';
  el.textContent = ' ' + text;
}

async function loadAyat(pno){
  document.getElementById('pno').textContent = pno;
  try{
    // نفس مسار API الموجود عندك: /api/page/<pno>/ayat/
    const res = await fetch(`/api/page/${pno}/ayat/`);
    if(!res.ok){ setMsg('تعذّر تحميل آيات الصفحة.', false); return; }
    const js  = await res.json();
    const cont = document.getElementById('ayat');
    cont.innerHTML = '';
    if(!js.ayat || !js.ayat.length){
      cont.innerHTML = '<div class="ayah">لا توجد آيات مرتبطة بهذه الصفحة.</div>';
      return;
    }
    js.ayat.forEach(a=>{
      const d = document.createElement('div');
      d.className = 'ayah';
      const safeVK = String(a.vk || '');
      d.innerHTML = `<b>${safeVK}</b>
        <div class="t">${a.text || ''}</div>
        <div style="margin-top:6px">
          <button class="btn-s" onclick="selectFirstAyah(${a.id}, '${safeVK.replace(/'/g, "\\'")}')">
            اختيار هذه كأول آية في الربع
          </button>
        </div>`;
      cont.appendChild(d);
    });
  }catch(e){
    setMsg('خطأ في الاتصال بالخادم.', false);
  }
}

async function selectFirstAyah(ayahId, vk){
  try{
    const res = await fetch("{% url 'core:api_pages_select_first' %}", {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
        'X-CSRFToken': getCookie('csrftoken'),
        'X-Requested-With': 'XMLHttpRequest'
      },
      body: new URLSearchParams({ ayah_id: String(ayahId) }).toString()
    });
    const js = await res.json();
    if(!res.ok || !js.ok){
      setMsg('تعذّر حفظ الاختيار' + (js && js.error ? ' ('+js.error+')' : ''), false);
      return;
    }
    setMsg(`تم اختيار ${vk} كأول آية في الربع ✅`, true);

    // بعد الحفظ، تقدر توجه المستخدم للخطوة التالية (مثال):
    // location.href = '{% url "core:pages_choose_juz" %}';
    alert(`تم اختيار ${vk} كأول آية في الربع ✅\nالخطوة التالية: تحديد الموضع (فوق/وسط/تحت) أو متابعة السؤال.`);
  }catch(e){
    setMsg('تعذّر الاتصال بالخادم.', false);
  }
}
</script>
{% endblock %}


# ===== FILE: core/templates/core/quarter_viewer.html =====
{% extends "core/base.html" %}
{% load static i18n %}

{% block title %}عارض الربع — متواتر{% endblock %}

{% block content %}
<style>
  .viewer-shell{min-height:72vh; display:grid; gap:1rem}
  .topbar{
    display:flex; align-items:center; justify-content:center; gap:.8rem; text-align:center;
    border:1px solid rgba(255,255,255,.10);
    background: linear-gradient(180deg, rgba(255,255,255,.03), rgba(255,255,255,.015));
    border-radius:16px; padding:.9rem 1.1rem; box-shadow:0 12px 32px rgba(0,0,0,.2);
  }
  .title{margin:0; color:#fff; font-weight:900}
  .muted{color:var(--muted)}

  .viewer{
    display:grid; gap:.8rem;
    border:1px solid rgba(255,255,255,.10);
    background: linear-gradient(180deg, rgba(255,255,255,.03), rgba(255,255,255,.015));
    border-radius:16px; padding:.8rem; box-shadow:0 14px 36px rgba(0,0,0,.22);
  }

  .spread{ display:grid; grid-template-columns: 1fr 1fr; gap:1rem; }
  @media (max-width: 980px){ .spread{ grid-template-columns: 1fr } }

  .page-card{
    display:grid; gap:.5rem;
    border:1px solid rgba(255,255,255,.08);
    background:#0c1713; border-radius:14px; padding:.6rem;
  }
  .page-head{display:flex; align-items:center; justify-content:space-between; color:var(--muted); font-weight:800}
  .thumb-wrap{
    position:relative;
    display:grid; place-items:center;
    background: #0a1210; border:1px dashed rgba(255,255,255,.08);
    border-radius:12px; padding:.4rem; min-height:360px;
    cursor:pointer;
  }
  .thumb{width:100%; height:100%; max-height:560px; object-fit:contain}
  .tap-hint{position:absolute; bottom:.5rem; inset-inline:0; text-align:center; font-size:.85rem; color:var(--muted)}

  .nav{ display:flex; align-items:center; justify-content:center; gap:.6rem; }
  .index-pill{
    background:#0c1713; border:1px solid rgba(255,255,255,.10);
    border-radius:999px; padding:.35rem .7rem; color:var(--text); font-weight:800
  }

  /* Modal */
  .modal-backdrop{
    position:fixed; inset:0; background:rgba(0,0,0,.55);
    display:none; align-items:flex-end; justify-content:center;
  }
  .modal{ width:min(860px, 92vw); max-height:74vh; overflow:auto;
    background:#0c1713; border:1px solid rgba(255,255,255,.12); border-radius:16px 16px 0 0;
    padding: .8rem 1rem; box-shadow:0 24px 80px rgba(0,0,0,.5);
  }
  .modal-head{ display:flex; align-items:center; justify-content:space-between; gap:.6rem; }
  .modal-title{ margin:0; color:#fff; font-weight:900 }
  .close{ background:transparent; border:1px solid rgba(255,255,255,.15); border-radius:10px; color:var(--text); padding:.3rem .6rem; cursor:pointer }
  .ayah-list{ display:grid; gap:.45rem; margin-top:.5rem }
  .ayah-item{ border:1px solid rgba(255,255,255,.1); border-radius:10px; padding:.55rem .65rem; background:#0a1210 }
  .ayah-item .vk{ font-weight:900; color:#fff }
  .ayah-item .txt{ font-size:.92rem; color:var(--muted); margin-top:.25rem }
  .ayah-actions{ margin-top:.4rem; display:flex; gap:.4rem; flex-wrap:wrap }
</style>

<div class="viewer-shell" data-qid="{{ qid }}">
  <section class="topbar">
    <div>
      <h1 class="title">عارض الربع (صفحتين–صفحتين)</h1>
      <div class="muted">اضغط على صورة الصفحة لاختيار «أول آية في الربع».</div>
    </div>
  </section>

  <section class="viewer" id="viewer">
    <div class="spread">
      <!-- اليسار -->
      <article class="page-card" id="left">
        <div class="page-head">
          <div>صفحة <b id="leftNo">—</b></div>
        </div>
        <div class="thumb-wrap" id="leftWrap">
          <img id="leftImg" class="thumb" alt="صفحة يسار" />
          <div class="tap-hint">اضغط لاختيار آية من هذه الصفحة</div>
        </div>
      </article>

      <!-- اليمين -->
      <article class="page-card" id="right">
        <div class="page-head">
          <div>صفحة <b id="rightNo">—</b></div>
        </div>
        <div class="thumb-wrap" id="rightWrap">
          <img id="rightImg" class="thumb" alt="صفحة يمين" />
          <div class="tap-hint">اضغط لاختيار آية من هذه الصفحة</div>
        </div>
      </article>
    </div>

    <div class="nav">
      <button class="btn btn-outline" id="prevBtn">⬅ السابق</button>
      <span class="index-pill">السبريد <span id="spreadIndex">1</span> من <span id="spreadTotal">—</span></span>
      <button class="btn btn-outline" id="nextBtn">التالي ➡</button>
    </div>
  </section>

  <div class="nav" style="margin-bottom:.4rem">
    <a href="javascript:history.back()" class="btn btn-outline">رجوع</a>
  </div>
</div>

<!-- Modal لاختيار آيات الصفحة -->
<div class="modal-backdrop" id="modal">
  <div class="modal">
    <div class="modal-head">
      <h3 class="modal-title">اختر أول آية من الصفحة <span id="modalPno">—</span></h3>
      <button class="close" id="closeModal">إغلاق</button>
    </div>
    <div class="ayah-list" id="modalAyat"></div>
  </div>
</div>

<script id="spreads-json" type="application/json">
  {{ spreads|safe }}
</script>

<script>
(function(){
  // جلب السبريدات
  let spreads = [];
  try {
    const raw = document.getElementById('spreads-json').textContent.trim();
    const safe = raw.replaceAll("(", "[").replaceAll(")", "]").replaceAll("None", "null").replaceAll("'", '"');
    spreads = JSON.parse(safe);
  } catch(e) { spreads = []; }

  const leftNo = document.getElementById('leftNo');
  const rightNo = document.getElementById('rightNo');
  const leftImg = document.getElementById('leftImg');
  const rightImg = document.getElementById('rightImg');
  const leftWrap = document.getElementById('leftWrap');
  const rightWrap = document.getElementById('rightWrap');
  const idxEl = document.getElementById('spreadIndex');
  const totEl = document.getElementById('spreadTotal');
  const prevBtn = document.getElementById('prevBtn');
  const nextBtn = document.getElementById('nextBtn');

  const modal = document.getElementById('modal');
  const closeModal = document.getElementById('closeModal');
  const modalAyat = document.getElementById('modalAyat');
  const modalPno = document.getElementById('modalPno');

  let index = 0;
  const total = spreads.length;
  if(totEl) totEl.textContent = total;

  function pageUrl(p){ return p ? `{% url 'core:page_svg_proxy' 99999 %}`.replace('99999', p) : ''; }

  async function openAyahPicker(pno){
    modalPno.textContent = pno || '—';
    modalAyat.innerHTML = '<div class="muted">... جاري التحميل</div>';
    modal.style.display = 'flex';
    try{
      const res = await fetch(`/api/page/${pno}/ayat/`);
      const js = await res.json();
      modalAyat.innerHTML = '';
      (js.ayat || []).forEach(a=>{
        const el = document.createElement('div');
        el.className = 'ayah-item';
        el.innerHTML = `
          <div class="vk">${a.vk}</div>
          <div class="txt">${a.text}</div>
          <div class="ayah-actions">
            <button class="btn btn-primary" data-ayah="${a.id}">اختيار هذه كأول آية</button>
          </div>
        `;
        modalAyat.appendChild(el);
      });

      modalAyat.querySelectorAll('button[data-ayah]').forEach(btn=>{
        btn.addEventListener('click', async ()=>{
          btn.disabled = true;
          try{
            const form = new FormData();
            form.append('ayah_id', btn.getAttribute('data-ayah'));
            const r = await fetch("{% url 'core:api_pages_select_first' %}", {
              method: 'POST',
              headers: {'X-Requested-With':'XMLHttpRequest', 'X-CSRFToken': '{{ csrf_token }}'},
              body: form
            });
            const jr = await r.json();
            if(jr.ok){
              alert('تم اختيار أول آية لهذا الربع. نكمل الخطوة التالية.');
              // TODO: الانتقال لخطوة موضع الآية (فوق/وسط/تحت)
              modal.style.display = 'none';
            }else{
              alert('تعذر الحفظ. حاول مرة أخرى.');
            }
          }catch(e){
            alert('تعذر الحفظ. تحقق من الاتصال.');
          }finally{
            btn.disabled = false;
          }
        });
      });
    }catch(e){
      modalAyat.innerHTML = '<div class="muted">تعذر تحميل آيات الصفحة.</div>';
    }
  }

  function attachPickers(pair){
    const [L, R] = pair || [null, null];
    leftWrap.onclick  = () => { if(L) openAyahPicker(L); };
    rightWrap.onclick = () => { if(R) openAyahPicker(R); };
  }

  async function render(){
    const pair = spreads[index] || [null, null];
    const [L, R] = pair;

    if(idxEl) idxEl.textContent = (index+1);

    leftNo.textContent  = L ?? '—';
    rightNo.textContent = R ?? '—';

    leftImg.src  = L ? pageUrl(L) : '';
    rightImg.src = R ? pageUrl(R) : '';

    prevBtn.disabled = index <= 0;
    nextBtn.disabled = index >= (total-1);

    attachPickers(pair);
  }

  prevBtn.addEventListener('click', ()=>{ if(index>0){ index--; render(); }});
  nextBtn.addEventListener('click', ()=>{ if(index<total-1){ index++; render(); }});
  window.addEventListener('keydown', (e)=>{
    if(e.key === 'ArrowLeft'){ nextBtn.click(); }
    if(e.key === 'ArrowRight'){ prevBtn.click(); }
  });

  closeModal.addEventListener('click', ()=>{ modal.style.display = 'none'; });
  modal.addEventListener('click', (e)=>{ if(e.target === modal){ modal.style.display = 'none'; } });

  if(total === 0){
    document.getElementById('viewer').innerHTML = '<div class="muted" style="padding:.8rem; text-align:center">لا توجد صفحات لهذا الربع.</div>';
    return;
  }
  render();
})();
</script>
{% endblock %}


# ===== FILE: core/templates/core/report_done.html =====
<div style="padding:.75rem 1rem; background:#0f1d17; color:#e9f5ef; font-weight:700; border-radius:10px; border:1px solid rgba(255,255,255,.12)">
  تم إرسال البلاغ، شكرًا لك.
</div>


# ===== FILE: core/templates/core/signup.html =====
{% extends "core/base.html" %}
{% load static i18n %}

{% block title %}إنشاء حساب — متواتر{% endblock %}

{% block content %}
<style>
  .auth-shell{
    min-height: 72vh;
    display: grid;
    place-items: center;
  }
  .auth-card{
    width: 100%;
    max-width: 460px;
    background: linear-gradient(180deg, rgba(255,255,255,.03), rgba(255,255,255,.015));
    border: 1px solid rgba(255,255,255,.10);
    border-radius: 16px;
    box-shadow: 0 18px 48px rgba(0,0,0,.28);
    padding: 1.1rem 1.15rem;
  }
  .auth-title{margin: .25rem 0 .9rem; color: #fff; font-weight: 900; letter-spacing: .2px; text-align:center}
  .auth-lead{margin: -.35rem 0 1rem; color: var(--muted); text-align:center}

  .form-control{display:grid; gap:.35rem; margin:.55rem 0}
  .form-control label{font-weight:800; color:#f1f6f3}
  .input{width:100%; background:#09130f; border:1px solid rgba(255,255,255,.16); color:var(--text); border-radius:12px; padding:.7rem .85rem}
  .input::placeholder{color:#dbe7e1; opacity:.9}

  .pwd-wrap{position:relative}
  .input.has-eye{padding-left: 2.3rem;}
  .eye-toggle{
    position:absolute; left:.45rem; top:50%; transform: translateY(-50%);
    display:grid; place-items:center;
    width: 28px; height: 28px;
    border: 1px solid rgba(255,255,255,.16);
    background:#0a1713; color: var(--text);
    border-radius: 8px; cursor: pointer;
  }
  .eye-toggle svg{width:18px; height:18px; display:block}
  .eye-toggle .icon-off{display:none}
  .eye-toggle[aria-pressed="true"] .icon-on{display:none}
  .eye-toggle[aria-pressed="true"] .icon-off{display:block}

  .hint{font-size:.9rem; color:var(--muted)}
  .auth-actions{display:flex; gap:.6rem; align-items:center; justify-content:center; margin-top: .9rem}
  .auth-links{display:flex; gap:.5rem; flex-wrap:wrap}
  .auth-links a{color:var(--accent); font-weight:800}
</style>

<div class="auth-shell">
  <div class="auth-card">
    <h1 class="auth-title">إنشاء حساب</h1>
    <p class="auth-lead">املأ البيانات التالية لبدء رحلتك.</p>

    <form method="post" action="{% url 'core:signup' %}">
      {% csrf_token %}
      <div class="form-control">
        <label for="id_student_name">اسم الطالب</label>
        <input id="id_student_name" name="student_name" class="input" placeholder="مثال: أحمد حافظ" required autofocus>
        <div class="hint">سيتم إنشاء اسم مستخدم تلقائيًا من الاسم (بالأحرف اللاتينية والشرطة السفلية).</div>
      </div>

      <div class="form-control">
        <label for="id_password">كلمة المرور</label>
        <div class="pwd-wrap">
          <input id="id_password" name="password" type="password"
                 class="input has-eye"
                 placeholder="على الأقل 8 أحرف وتحتوي أحرفًا وأرقامًا"
                 minlength="8"
                 pattern="(?=.*[A-Za-z])(?=.*\d).{8,}"
                 title="8 أحرف على الأقل وتحتوي على أحرف وأرقام"
                 required>
          <button type="button" id="togglePwd" class="eye-toggle" aria-label="إظهار كلمة المرور" aria-pressed="false">
            <!-- عين -->
            <svg class="icon-on" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Z" stroke="currentColor" stroke-width="2"/>
              <circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="2"/>
            </svg>
            <!-- عين متشطّبة -->
            <svg class="icon-off" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M3 3l18 18" stroke="currentColor" stroke-width="2"/>
              <path d="M2 12s3.5-6 10-6c-2.3 0-4.2.7-5.7 1.7M22 12s-3.5 6-10 6c-2.3 0-4.2-.7-5.7-1.7" stroke="currentColor" stroke-width="2"/>
              <circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="2"/>
            </svg>
          </button>
        </div>
        <div class="hint">يجب ألا تقل عن 8 أحرف وتحتوي على أحرف وأرقام.</div>
      </div>

      <div class="auth-actions">
        <button class="btn btn-primary" type="submit">إنشاء الحساب</button>
      </div>

      <div class="auth-actions">
        <div class="auth-links">
          <a href="{% url 'core:login' %}">لديك حساب؟ سجّل دخول</a>
        </div>
      </div>
    </form>
  </div>
</div>

<script>
  (function(){
    const btn = document.getElementById('togglePwd');
    const input = document.getElementById('id_password');
    if(btn && input){
      btn.addEventListener('click', ()=>{
        const show = input.getAttribute('type') === 'password';
        input.setAttribute('type', show ? 'text' : 'password');
        btn.setAttribute('aria-pressed', show ? 'true' : 'false');
        btn.setAttribute('aria-label', show ? 'إخفاء كلمة المرور' : 'إظهار كلمة المرور');
      });
    }
  })();
</script>
{% endblock %}


# ===== FILE: core/templates/core/stats.html =====
{% extends "core/base.html" %}
{% load static i18n arabic_extras %}

{% block title %}إحصائياتك — متواتر{% endblock %}

{% block content %}
<style>
  .s-wrap{max-width:980px; margin:18px auto; padding:14px; color:#fff}
  .s-head{
    border:1px solid rgba(212,175,55,.22);
    background: linear-gradient(180deg, rgba(255,255,255,.03), rgba(255,255,255,.015));
    border-radius:16px; box-shadow:0 14px 36px rgba(0,0,0,.22);
    padding:14px 16px; display:grid; gap:8px;
  }
  .s-title{margin:0; font-weight:900}
  .s-grid{display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin-top:6px}
  @media (max-width:900px){ .s-grid{grid-template-columns:repeat(2,1fr)} }
  @media (max-width:540px){ .s-grid{grid-template-columns:1fr} }
  .card{
    background:#0f1118; border:1px solid rgba(255,255,255,.10);
    border-radius:14px; padding:12px; display:grid; gap:4px; text-align:center
  }
  .num{ font-size:1.6rem; font-weight:900 }
  .lbl{ color:#c8d1cf; font-weight:800 }
  .ok .num{ color:#22c55e } .no .num{ color:#ef4444 } .muted .num{ color:#e5d18f }

  .s-actions{display:flex; gap:.6rem; margin-top:10px; flex-wrap:wrap}
</style>

<div class="s-wrap" dir="rtl">
  <header class="s-head">
    <h1 class="s-title">إحصائياتك</h1>
    <div class="s-grid">
      <div class="card muted">
        <div class="num">{{ stats.exams|arabic_digits }}</div>
        <div class="lbl">الاختبارات المُنجزة</div>
      </div>
      <div class="card ok">
        <div class="num">{{ stats.correct|arabic_digits }}</div>
        <div class="lbl">إجابات صحيحة</div>
      </div>
      <div class="card no">
        <div class="num">{{ stats.wrong|arabic_digits }}</div>
        <div class="lbl">إجابات خاطئة</div>
      </div>
      <div class="card">
        <div class="num">{{ stats.unanswered|arabic_digits }}</div>
        <div class="lbl">غير مُجاب</div>
      </div>
    </div>

    <div class="s-actions">
      <a href="{% url 'core:test_selection' %}" class="btn btn-primary">بدء اختبار جديد</a>
      <a href="{% url 'core:main_menu' %}" class="btn btn-outline">الرجوع للرئيسية</a>
    </div>
  </header>
</div>
{% endblock %}


# ===== FILE: core/templates/core/test_catalog.html =====
{% extends "core/base.html" %}
{% load static i18n %}

{% block title %}كتالوج الاختبارات — متواتر{% endblock %}

{% block content %}
<style>
  .catalog { min-height:66vh; display:grid; gap:1rem; align-content:start; }
  .head { text-align:center; padding:.8rem 0 .4rem; }
  .head h1 { margin:.2rem 0 .3rem; color:#fff; font-weight:900; font-size:clamp(20px,3.2vw,26px); }
  .head p  { color:var(--muted); margin:0 auto; max-width:820px; }

  .tests-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:.9rem; }
  @media (max-width: 900px){ .tests-grid{ grid-template-columns:1fr } }

  .test-card{
    position:relative; border:1px solid rgba(255,255,255,.10); border-radius:16px;
    background:linear-gradient(180deg, rgba(255,255,255,.03), rgba(255,255,255,.015));
    box-shadow:0 14px 36px rgba(0,0,0,.22); padding:1rem 1.15rem; display:grid; gap:.4rem;
  }
  .test-card h3{ margin:0; color:#fff; font-weight:900; }
  .test-card p { margin:0; color:var(--muted); min-height:3.2em; }
  .test-card .go{ justify-self:start; margin-top:.5rem }

  .test-card.disabled{ opacity:.55; filter:grayscale(.25); }
  .test-card.disabled .soon{
    position:absolute; top:.8rem; inset-inline-end:.8rem;
    font-size:.8rem; padding:.15rem .45rem; border-radius:999px;
    border:1px solid #d9b44a; background:#fffbea; color:#8a6d1d;
  }

  .backline{ text-align:center; margin-top:.4rem }
</style>

<div class="catalog">
  <div class="head">
    <h1>اختر نوع الاختبار</h1>
    <p>اختر نوع الاختبار الذي يناسب حفظك وإتقانك:</p>
  </div>

  <section class="tests-grid" aria-label="أنواع الاختبارات">
    {% for t in tests %}
      {% if t.available %}
        <article class="test-card">
          <h3>{{ t.title }}</h3>
          <p>{{ t.desc }}</p>
          {% if t.url %}
            <a href="{{ t.url }}" class="btn btn-primary go">اختيار هذا الاختبار</a>
          {% else %}
            <a href="{% url 'core:test_selection' %}?type={{ t.key }}" class="btn btn-primary go">اختيار هذا الاختبار</a>
          {% endif %}
        </article>
      {% else %}
        <article class="test-card disabled" aria-disabled="true">
          <span class="soon">قريبًا</span>
          <h3>{{ t.title }}</h3>
          <p>{{ t.desc }}</p>
          <button class="btn btn-outline go" disabled>غير متاح الآن</button>
        </article>
      {% endif %}
    {% endfor %}
  </section>

  <div class="backline">
    <a href="{% url 'core:main_menu' %}" class="btn btn-outline">عودة للرئيسية</a>
  </div>
</div>
{% endblock %}


# ===== FILE: core/templates/core/test_question.html =====
{% extends "core/base.html" %}
{% load static arabic_extras highlight %}

{% block title %}الاختبار — سؤال {{ question_number|arabic_digits }}{% endblock %}

{% block content %}
<div class="q-wrapper" dir="rtl">
  <!-- Toast -->
  <div id="toast" class="toast" aria-live="polite" aria-atomic="true"></div>

  <header class="q-header">
    <div class="q-scope">{{ scope_label }}</div>

    <div class="q-top">
      <div class="q-counter">
        سؤال <strong>{{ question_number|arabic_digits }}</strong>
        من <strong>{{ total_questions|arabic_digits }}</strong>
      </div>
      <div class="q-progress" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="{{ progress_percent }}">
        <div class="q-progress-bar" style="width: {{ progress_percent }}%;"></div>
      </div>

      <!-- زر إنهاء الاختبار نُقل للهيدر -->
      <div class="q-head-actions">
        <button type="button" class="btn btn-ghost" id="endBtn" aria-label="إنهاء الاختبار الآن">إنهاء الاختبار</button>
      </div>
    </div>
  </header>

  <main class="q-main">
    <article class="q-card">
      <h1 class="q-phrase" aria-live="polite">{{ phrase }}</h1>
    </article>

    <form id="answerForm" method="post" class="q-form">
      {% csrf_token %}
      <fieldset class="q-options">
        {% for opt in options %}
        <label class="q-option">
          <input type="radio" name="occurrence" value="{{ opt }}" required>
          <span class="q-pill">{{ opt|arabic_digits }}</span>
        </label>
        {% endfor %}
      </fieldset>

      <div id="feedback" class="q-feedback" hidden></div>

      <div class="q-actions">
        <button type="submit" class="btn btn-primary" id="nextBtn">تحقّق</button>
        <!-- تم حذف زر الإنهاء من هنا (موجود بالأعلى) -->
      </div>
    </form>

    <details class="q-report">
      <summary>الإبلاغ عن مشكلة في هذا السؤال</summary>
      <form id="reportForm" method="post" action="{% url 'core:report_question' %}" class="q-report-form">
        {% csrf_token %}
        <input type="hidden" name="phrase" value="{{ phrase }}">
        <input type="hidden" name="question_number" value="{{ question_number }}">
        <input type="hidden" name="given" id="givenField" value="">
        <input type="hidden" name="correct" value="{{ correct_count }}">
        <input type="hidden" name="from" value="test">
        <label for="repText" class="q-label">وصف المشكلة</label>
        <textarea id="repText" name="text" rows="3" placeholder="اكتب وصفًا مختصرًا للمشكلة…"></textarea>
        <button type="submit" class="btn btn-danger">إرسال الإبلاغ</button>
      </form>
    </details>

    <!-- إنهاء مبكر (نموذج خفي) -->
    <form id="endForm" method="post" style="display:none;">
      {% csrf_token %}
      <input type="hidden" name="action" value="end">
    </form>
  </main>
</div>

<!-- مودال إنهاء داخلي بنفس الستايل -->
<div class="q-modal" id="endModal" aria-hidden="true" role="dialog" aria-labelledby="endTitle">
  <div class="q-modal-card">
    <h3 id="endTitle" class="q-modal-title">إنهاء الاختبار؟</h3>
    <p class="q-modal-text">هل تريد إنهاء الاختبار الآن؟ سيتم عرض نتيجتك حتى هذه اللحظة.</p>
    <div class="q-modal-actions">
      <button type="button" class="btn btn-primary" id="confirmEnd">تأكيد الإنهاء</button>
      <button type="button" class="btn btn-ghost" id="cancelEnd">إلغاء</button>
    </div>
  </div>
</div>

<style>
  :root{
    /* خلفية وثيم متوافق مع باقي الصفحات */
    --q-bg:#0f0f15;
    --q-card:#11131d;
    --q-text:#f3f4f6;
    --q-sub:#9aa3b2;

    --q-gold:#d4af37;
    --q-gold-2:#b88900;
    --q-ring: rgba(212,175,55,.35);

    --q-danger:#ef4444;
    --q-ghost:#2a3040;
    --q-radius: 16px;
    --q-shadow: 0 10px 30px rgba(0,0,0,.35);
  }
  .q-wrapper{max-width: 900px; margin: 24px auto; padding: 16px; color: var(--q-text);}
  .q-header{margin-bottom: 16px;}
  .q-scope{color: var(--q-sub); font-size: 14px; margin-bottom: 8px}
  .q-top{display: grid; gap: 10px}
  .q-counter{font-size: 15px}
  .q-progress{
    width: 100%; height: 10px; background: #1d2230; border-radius: 999px; overflow: hidden;
    box-shadow: inset 0 0 0 1px rgba(255,255,255,.05);
  }
  .q-progress-bar{
    height: 100%; background: linear-gradient(90deg,var(--q-gold),var(--q-gold-2));
    transition: width .35s ease;
  }
  .q-head-actions{display:flex; justify-content:flex-end}

  .q-main{display: grid; gap: 16px}
  .q-card{
    background: linear-gradient(180deg,#0f1118, #11131d);
    border: 1px solid rgba(212,175,55,.20);
    border-radius: var(--q-radius);
    box-shadow: var(--q-shadow);
    padding: 18px 20px;
  }
  .q-phrase{margin: 0; line-height: 2.1; font-size: clamp(18px, 2.3vw, 22px); text-align: center;}

  .q-form{display: grid; gap: 16px}
  .q-options{
    display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 10px; border: 0; padding: 0; margin: 0;
  }
  @media (max-width: 720px){ .q-options{grid-template-columns: repeat(2, minmax(0,1fr));} }
  .q-option{position: relative; display: block; cursor: pointer}
  .q-option input{position: absolute; inset: 0; opacity: 0; pointer-events: none;}
  .q-pill{
    display: grid; place-items: center;
    height: 56px; border-radius: 14px;
    background: #0f1118;
    border: 1px solid rgba(212,175,55,.25);
    font-size: 18px; font-weight: 800; letter-spacing: .2px;
    transition: transform .12s ease, box-shadow .12s ease, border-color .12s ease, background .12s ease;
  }
  .q-option:hover .q-pill{transform: translateY(-1px); box-shadow: 0 8px 18px rgba(0,0,0,.25);}
  .q-option input:focus-visible + .q-pill{outline: 2px solid var(--q-ring); outline-offset: 2px;}
  .q-option input:checked + .q-pill{
    background: linear-gradient(180deg, rgba(212,175,55,.12), rgba(212,175,55,.08));
    border-color: var(--q-gold);
    box-shadow: 0 0 0 3px var(--q-ring), 0 10px 22px rgba(212,175,55,.15);
  }

  .q-option.correct .q-pill{
    background: linear-gradient(180deg, rgba(34,197,94,.14), rgba(34,197,94,.08));
    border-color: #22c55e;
  }
  .q-option.wrong .q-pill{
    background: linear-gradient(180deg, rgba(239,68,68,.14), rgba(239,68,68,.08));
    border-color: #ef4444;
  }

  .q-feedback{
    text-align:center; padding: 10px 12px; border-radius: 12px;
    border: 1px solid rgba(255,255,255,.10);
    background: #0f1118; color: var(--q-text); font-weight: 700;
  }
  .q-feedback.ok{border-color:#22c55e;}
  .q-feedback.err{border-color:#ef4444;}

  .q-actions{display: flex; gap: 10px; justify-content: center}
  .btn{
    appearance: none; border: 0; border-radius: 12px; padding: 12px 18px; font-weight: 800;
    cursor: pointer; transition: filter .12s ease, transform .08s ease; white-space: nowrap;
  }
  .btn:active{transform: translateY(1px)}
  .btn-primary{
    background: linear-gradient(180deg,var(--q-gold),var(--q-gold-2)); color: #1a1200;
    border: 1px solid rgba(212,175,55,.55);
  }
  .btn-primary:hover{filter: brightness(1.03)}
  .btn-ghost{background: #0f1118; color: var(--q-text); border: 1px solid var(--q-ghost)}
  .btn-danger{background: #ef4444; color: #310b0b;}

  .q-report{
    background: #0f1118;
    border: 1px dashed rgba(212,175,55,.35);
    border-radius: var(--q-radius);
    padding: 12px 14px;
  }
  .q-report > summary{cursor: pointer; font-weight: 800; color: var(--q-sub)}
  .q-report-form{display: grid; gap: 10px; margin-top: 10px}
  .q-label{font-size: 13px; color: var(--q-sub)}
  .q-report-form textarea{
    width: 100%; border-radius: 10px; padding: 10px; background: #0f0f15; color: var(--q-text);
    border: 1px solid rgba(255,255,255,.08);
  }

  /* Toast */
  .toast{
    position: fixed; inset-inline: 16px; bottom: 16px; z-index: 50;
    display: none; padding: 10px 12px; border-radius: 12px; font-weight: 700;
    background: #0f1118; color: var(--q-text); border: 1px solid rgba(212,175,55,.4);
    box-shadow: 0 10px 30px rgba(0,0,0,.35);
  }
  .toast.show{display: inline-block; animation: fadein .2s ease, fadeout .2s ease 2.8s forwards;}
  @keyframes fadein{from{opacity:0; transform: translateY(6px)} to{opacity:1; transform: translateY(0)}}
  @keyframes fadeout{to{opacity:0; transform: translateY(6px)}}

/* مودال إنهاء — غير شفّاف وواضح */
.q-modal{
  position: fixed; inset: 0; display: none; place-items: center; z-index: 60;
  /* خلفية معتمة بالكامل لطمس الصفحة */
  background: #000; /* بديل: rgba(0,0,0,.9) لو حابب نسبة بسيطة */
}
.q-modal.show{display: grid}

/* كارت المودال نفسه بخلفية صلبة وتباين أعلى */
.q-modal-card{
  width:min(520px, 92vw);
  border:1px solid rgba(212,175,55,.35);
  background: #0f1118; /* خلفية صلبة بدل تدرّج شفاف */
  border-radius:16px;
  padding:1rem 1.1rem;
  box-shadow: 0 24px 60px rgba(0,0,0,.6); /* ظل أقوى */
  display:grid; gap:.6rem;
}

  .q-modal-title{margin:0; color:#fff; font-weight:900; font-size:1.1rem}
  .q-modal-actions{display:flex; gap:.6rem; justify-content:flex-start; flex-wrap:wrap}
  .q-modal-text{color:var(--q-sub); margin:.2rem 0 .4rem}
</style>

<script>
  (function(){
    const form = document.getElementById('answerForm');
    const nextBtn = document.getElementById('nextBtn');
    const endBtn  = document.getElementById('endBtn');
    const endForm = document.getElementById('endForm');
    const givenField = document.getElementById('givenField');
    const reportForm = document.getElementById('reportForm');
    const toast = document.getElementById('toast');
    const feedbackBox = document.getElementById('feedback');

    const endModal = document.getElementById('endModal');
    const confirmEnd = document.getElementById('confirmEnd');
    const cancelEnd = document.getElementById('cancelEnd');

    const correct = parseInt('{{ correct_count|default:0 }}', 10) || 0;

    // خزّن اختيار الطالب للإبلاغ
    form.addEventListener('change', function(e){
      if (e.target && e.target.name === 'occurrence'){
        givenField.value = e.target.value || '';
      }
    });

    // تأكيد الإجابة (خطوتين): تحقّق ثم التالي
    let confirmed = false;

    form.addEventListener('submit', function(e){
      const chosen = form.querySelector('input[name="occurrence"]:checked');
      if (!confirmed){
        e.preventDefault();
        if (!chosen){
          showToast('من فضلك اختر إجابة أولًا.');
          return;
        }
        const val = parseInt(chosen.value, 10);

        // نظّف تلوين سابق
        form.querySelectorAll('.q-option').forEach(el => el.classList.remove('correct','wrong'));

        // تلوين الصحيح والخاطئ
        form.querySelectorAll('.q-option').forEach(el=>{
          const input = el.querySelector('input');
          const v = parseInt(input.value,10);
          if (v === correct) el.classList.add('correct');
          if (input.checked && v !== correct) el.classList.add('wrong');
        });

        // قفل الخيارات: تعطيل كل الراديوهات ما عدا المختار
        form.querySelectorAll('input[name="occurrence"]').forEach(inp=>{
          if (inp !== chosen) inp.disabled = true;
        });

        // فيدباك
        feedbackBox.hidden = false;
        if (val === correct){
          feedbackBox.className = 'q-feedback ok';
          feedbackBox.textContent = 'إجابة صحيحة ✅';
        }else{
          feedbackBox.className = 'q-feedback err';
          feedbackBox.textContent = 'إجابة غير صحيحة ❌';
        }

        nextBtn.textContent = 'التالي';
        confirmed = true; // المرة الجاية هنسيب الفورم يتبعت
        return;
      }
      // الإرسال الحقيقي: امنع الضغط المزدوج
      nextBtn.disabled = true;
    });

    // فتح/غلق مودال الإنهاء
    endBtn.addEventListener('click', ()=>{
      endModal.classList.add('show');
      endModal.setAttribute('aria-hidden', 'false');
    });
    cancelEnd.addEventListener('click', ()=>{
      endModal.classList.remove('show');
      endModal.setAttribute('aria-hidden', 'true');
    });
    confirmEnd.addEventListener('click', ()=>{
      endForm.submit();
    });

    // إرسال الإبلاغ والبقاء في الصفحة
    reportForm.addEventListener('submit', async function(e){
      e.preventDefault();
      const fd = new FormData(reportForm);
      try{
        const res = await fetch(reportForm.action, {
          method: 'POST',
          headers: {'X-Requested-With':'XMLHttpRequest'},
          body: fd
        });
        let ok = false, msg = 'تم إرسال الإبلاغ. شكراً لك.';
        const ct = res.headers.get('content-type') || '';
        if (ct.includes('application/json')){
          const data = await res.json();
          ok = !!data.ok; msg = data.message || msg;
        }else{
          ok = res.ok;
        }
        if (ok){
          showToast(msg);
          reportForm.reset();
          const details = reportForm.closest('details');
          if (details) details.open = false;
        }else{
          showToast('تعذّر إرسال الإبلاغ. حاول مرة أخرى.');
        }
      }catch(_){
        showToast('تعذّر الاتصال. تأكد من الشبكة وحاول مجددًا.');
      }
    });

    function showToast(text){
      if (!toast) return;
      toast.textContent = text;
      toast.classList.remove('show');
      void toast.offsetWidth;
      toast.classList.add('show');
    }
  })();
</script>
{% endblock %}


# ===== FILE: core/templates/core/test_result.html =====
{% extends "core/base.html" %}
{% load static i18n arabic_extras highlight %}

{% block title %}نتيجة الاختبار — متواتر{% endblock %}

{% block content %}
<style>
  :root{
    --r-text:#f3f4f6;
    --r-sub:#9aa3b2;
    --r-card:#11131d;
    --r-gold:#d4af37;
    --r-gold-2:#b88900;
    --r-ring: rgba(212,175,55,.35);
    --r-green:#22c55e;
    --r-red:#ef4444;
    --r-muted:#1d2230;
    --r-shadow: 0 12px 36px rgba(0,0,0,.28);
    --r-radius: 16px;
  }

  .r-wrap{max-width: 980px; margin: 20px auto; padding: 14px; color: var(--r-text)}
  .r-header{
    border:1px solid rgba(212,175,55,.22);
    background: linear-gradient(180deg, rgba(255,255,255,.03), rgba(255,255,255,.015));
    border-radius: var(--r-radius);
    box-shadow: var(--r-shadow);
    padding: 14px 16px;
    display: grid; gap: 10px;
  }
  .r-scope{color: var(--r-sub); font-weight: 800}

  .r-top{
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 12px; align-items: center;
  }
  @media(max-width: 720px){ .r-top{grid-template-columns: 1fr} }

  .r-score{
    display:flex; gap:10px; align-items:center; flex-wrap:wrap;
  }
  .r-chip{
    display:inline-flex; align-items:center; gap:.45rem;
    background:#0f1118; color:var(--r-text);
    border:1px solid rgba(255,255,255,.10);
    border-radius: 999px; padding: .42rem .7rem; font-weight: 800;
  }
  .r-chip.ok{ border-color: rgba(34,197,94,.45) }
  .r-chip.no{ border-color: rgba(239,68,68,.45) }

  /* === Thermometer (صح أخضر + خطأ أحمر) === */
  .r-bar{
    min-width: 220px; width: 100%;
    height: 14px; background: var(--r-muted); border-radius: 999px; overflow: hidden;
    border:1px solid rgba(255,255,255,.08);
    display:flex;
  }
  .r-bar > span{
    display:block; height:100%; width:0%;
    transition: width .4s ease;
  }
  .r-bar > .ok{ background: linear-gradient(90deg,#16a34a,#22c55e) }
  .r-bar > .no{ background: linear-gradient(90deg,#ef4444,#f87171) }

  .r-actions{display:flex; gap:10px; flex-wrap:wrap; justify-content:flex-start}
  .btn{
    appearance:none; border:1px solid transparent; border-radius:12px;
    padding: 10px 14px; font-weight: 900; cursor: pointer;
  }
  .btn-primary{background: linear-gradient(180deg,var(--r-gold),var(--r-gold-2)); color:#1a1200; border-color: rgba(212,175,55,.55)}
  .btn-outline{background:#0f1118; color:var(--r-text); border-color: rgba(255,255,255,.12)}
  .btn-ghost{background:#0f1118; color:var(--r-text); border-color: rgba(255,255,255,.08)}

  /* قائمة النتائج */
  .r-list{display:grid; gap:12px; margin-top: 14px}
  .r-item{
    background: linear-gradient(180deg, rgba(255,255,255,.03), rgba(255,255,255,.015));
    border:1px solid rgba(255,255,255,.10);
    border-radius: var(--r-radius);
    box-shadow: var(--r-shadow);
    padding: 12px 14px;
    display:grid; gap:8px;
  }
  .r-head{display:flex; align-items:center; justify-content:space-between; gap:8px; flex-wrap:wrap}
  .r-phrase{margin:0; font-weight: 900; color:#fff}
  .status{
    font-weight:900; border-radius:10px; padding:.35rem .6rem;
    border:1px solid rgba(255,255,255,.1);
  }
  .ok .status{ background: linear-gradient(135deg, rgba(34,197,94,.14), rgba(34,197,94,.08)); color:#eafff3; border-color:#22c55e }
  .no .status{ background: linear-gradient(135deg, rgba(239,68,68,.14), rgba(239,68,68,.08)); color:#ffecec; border-color:#ef4444 }

  .meta{
    display:flex; gap:8px; flex-wrap:wrap; align-items:center;
    color: var(--r-sub); font-weight: 800
  }
  .m-chip{
    border:1px solid rgba(255,255,255,.10); border-radius: 999px;
    padding:.25rem .55rem; background:#0f1118;
  }

  /* تفاصيل الأماكن */
  details{border-top:1px dashed rgba(255,255,255,.12); padding-top: 8px}
  summary{cursor:pointer; color: var(--r-gold); font-weight: 900}
  .occ-list{list-style:none; padding: 8px 0 0; margin:0; display:grid; gap:10px}
  .ayah{
    background:#0f1118; border:1px solid rgba(255,255,255,.08);
    border-radius:12px; padding:10px 12px; display:grid; gap:4px
  }
  .ayah-meta{color:var(--r-sub); font-size:.92rem; font-weight: 800}
  .ayah-text{line-height: 1.9}

  /* شريط أدوات القائمة */
  .r-toolstrip{display:flex; gap:8px; align-items:center; margin-top: 6px}
  .btn-sm{padding:.35rem .55rem; border-radius: 10px}

  /* Toast صغير */
  .toast{
    position: fixed; inset-inline: 16px; bottom: 16px; z-index: 50;
    display:none; padding:10px 12px; border-radius: 12px; font-weight: 800;
    background:#0f1118; color:#fff; border:1px solid rgba(212,175,55,.4);
    box-shadow: 0 10px 30px rgba(0,0,0,.35);
  }
  .toast.show{display:inline-block; animation: fadein .2s ease, fadeout .2s ease 2.6s forwards;}
  @keyframes fadein{from{opacity:0; transform: translateY(6px)} to{opacity:1; transform: translateY(0)}}
  @keyframes fadeout{to{opacity:0; transform: translateY(6px)}}
</style>

<div class="r-wrap" dir="rtl">
  <div id="toast" class="toast" aria-live="polite" aria-atomic="true"></div>

  <header class="r-header">
    <div class="r-scope">{{ scope_label }}</div>

    <div class="r-top">
      <div class="r-score">
        <span class="r-chip">النتيجة: <b>{{ score|arabic_digits }}</b> / <b>{{ total|arabic_digits }}</b></span>
        <span class="r-chip ok">صحيح: <b>{{ score|arabic_digits }}</b></span>
        <span class="r-chip no">خطأ: <b>{{ wrong|arabic_digits }}</b></span>
      </div>

      <!-- ترمومتر: أخضر (صح) + أحمر (خطأ) -->
      <div class="r-bar" id="rBar" data-score="{{ score }}" data-total="{{ total }}" data-wrong="{{ wrong }}"><span class="ok"></span><span class="no"></span></div>
    </div>

    <div class="r-actions">
      <a class="btn btn-primary" href="{% url 'core:test_selection' %}">ابدأ اختبارًا جديدًا</a>
      <a class="btn btn-outline" href="{% url 'core:main_menu' %}">الرجوع للرئيسية</a>
      <button type="button" class="btn btn-ghost" id="toggleAll">إظهار كل التفاصيل</button>
    </div>
  </header>

  <section class="r-list">
    {% for item in detailed_results %}
    {% with ga=item.given_answer|default_if_none:0 cc=item.correct_count|default_if_none:0 %}
    <article class="r-item {% if ga|add:0 == cc|add:0 %}ok{% else %}no{% endif %}">
      <div class="r-head">
        <h3 class="r-phrase">{{ item.phrase }}</h3>
        <span class="status">{% if ga|add:0 == cc|add:0 %}إجابة صحيحة{% else %}إجابة خاطئة{% endif %}</span>
      </div>

      <div class="meta">
        <span class="m-chip">إجابة الطالب:
          <b>{% if item.given_answer is not None %}{{ item.given_answer|arabic_digits }}{% else %}—{% endif %}</b>
        </span>
        <span class="m-chip">الإجابة الصحيحة: <b>{{ cc|arabic_digits }}</b></span>
        <span class="m-chip">عدد المواضع: <b>{{ item.occurrences|length|arabic_digits }}</b></span>
      </div>

      <!-- تُفتح تلقائيًا لو الإجابة خاطئة -->
      <details {% if ga|add:0 != cc|add:0 %}open{% endif %}>
        <summary>عرض مواضع العبارة</summary>
        <ol class="occ-list">
          {% for a in item.occurrences %}
          <li class="ayah">
            <div class="ayah-meta">
              سورة {{ a.surah|arabic_digits }}:{{ a.number|arabic_digits }}
              {% if a.juz_number %} — الجزء {{ a.juz_number|arabic_digits }}{% endif %}
              {% if a.quarter_label %} — {{ a.quarter_label }}{% endif %}
            </div>
            <div class="ayah-text">{{ a.text|highlight:item.phrase }}</div>
          </li>
          {% endfor %}
        </ol>
      </details>
    </article>
    {% endwith %}
    {% empty %}
      <div class="r-item">لا توجد تفاصيل لعرضها.</div>
    {% endfor %}
  </section>
</div>

<script>
  (function(){
    // ترمومتر: يحسب نسب الصحيح/الخطأ ويملأ الشريحتين
    const bar = document.getElementById('rBar');
    if (bar){
      const s = parseInt(bar.dataset.score || '0', 10) || 0;
      const t = parseInt(bar.dataset.total || '1', 10) || 1;
      const w = Math.max(0, t - s); // في حال لم يمرّر wrong
      const okPct = Math.max(0, Math.min(100, Math.round((s*100)/t)));
      const noPct = 100 - okPct;
      const ok = bar.querySelector('.ok');
      const no = bar.querySelector('.no');
      if (ok) ok.style.width = okPct + '%';
      if (no) no.style.width = noPct + '%';
    }

    // إظهار/إخفاء كل التفاصيل
    const btn = document.getElementById('toggleAll');
    if (btn){
      btn.addEventListener('click', ()=>{
        const details = document.querySelectorAll('.r-list details');
        const someClosed = Array.from(details).some(d => !d.open);
        details.forEach(d => d.open = someClosed);
        btn.textContent = someClosed ? 'إخفاء كل التفاصيل' : 'إظهار كل التفاصيل';
      });
    }
  })();
</script>
{% endblock %}


# ===== FILE: core/templates/core/test_selection.html =====
{% extends "core/base.html" %}
{% load static i18n arabic_extras %}

{% block title %}بدء اختبار — متواتر{% endblock %}

{% block content %}
<style>
  .page-shell{min-height:72vh; display:grid; gap:1rem}

  .header-card{
    border:1px solid rgba(212,175,55,.22);
    background: linear-gradient(180deg, rgba(255,255,255,.03), rgba(255,255,255,.015));
    border-radius:16px; padding:1rem 1.1rem; box-shadow:0 18px 44px rgba(0,0,0,.22);
  }
  .header-card h1{margin:.25rem 0 .2rem; color:#fff; font-weight:900}
  .sub{color:var(--muted); margin:0}
  .scope-tools{display:flex; align-items:center; justify-content:space-between; gap:.6rem; margin-top:.6rem}
  .tiny-link{
    background:#0c1713; border:1px solid rgba(255,255,255,.10);
    color:var(--accent); font-weight:800; cursor:pointer;
    padding:.35rem .6rem; border-radius:10px;
  }
  .tiny-link:hover{filter:brightness(1.05)}
  .stats{display:flex; gap:.6rem; flex-wrap:wrap; font-weight:800}
  .stat-chip{
    display:inline-flex; gap:.45rem; align-items:center;
    background:#0c1713; border:1px solid rgba(255,255,255,.10);
    padding:.42rem .7rem; border-radius:999px; color:var(--text);
  }
  .stat-chip .dot{width:8px;height:8px;border-radius:50%}
  .stat-chip .dot.juz{background:#16a34a}
  .stat-chip .dot.quarter{background:var(--accent)}

  .accordion{display:grid; gap:.7rem}
  .ac-item{
    background:linear-gradient(180deg, rgba(255,255,255,.03), rgba(255,255,255,.015));
    border:1px solid rgba(255,255,255,.10);
    border-radius:14px; box-shadow:0 8px 26px rgba(0,0,0,.18);
  }
  .ac-head{display:flex; align-items:center; gap:.6rem; padding:.65rem .75rem; justify-content:space-between}
  .ac-left{display:flex; align-items:center; gap:.55rem}
  .ac-title{margin:0; color:#fff; font-weight:900; font-size:1rem}
  .tiny{font-size:.85rem; color:var(--muted)}
  .expand{
    background:transparent; border:none; color:var(--accent); font-weight:800; cursor:pointer;
    padding:.25rem .4rem; border-radius:8px;
  }
  .expand:hover{text-decoration: underline}

  .juz-all{position:relative; display:inline-grid; place-items:center; width:22px; height:22px; cursor:pointer}
  .juz-all input{ position:absolute; inset:0; opacity:0; cursor:pointer; }
  .juz-all .box{
    width:20px; height:20px; border-radius:6px;
    border:1px solid rgba(255,255,255,.18); background:#0c1713;
    box-shadow: inset 0 0 0 0 var(--accent); transition: box-shadow .18s ease, border-color .18s ease;
  }
  .juz-all input:checked + .box{
    border-color: var(--accent);
    box-shadow: inset 0 0 0 999px var(--accent);
  }

  .ac-panel{ padding: .1rem 0 .7rem; border-top:1px dashed rgba(255,255,255,.12) }
  .ac-panel[hidden]{ display:none !important; }

  .q-list{ display:grid; gap:.45rem; padding:.55rem .75rem .1rem }
  @media (min-width: 720px){
    .q-list{ grid-template-columns: 1fr 1fr }
  }

  .q-item-row{
    position: relative;
    display:grid; grid-template-columns: auto 1fr; gap:.5rem; align-items:center;
    padding:.45rem .6rem; border-radius:10px;
    border:1px solid rgba(255,255,255,.12); background:#0c1713; color:var(--text);
    cursor:pointer; user-select:none;
  }
  .q-item-row input{ position:absolute; inset:0; opacity:0; cursor:pointer; }
  .q-item-row .tick{
    width:18px; height:18px; border-radius:5px;
    border:1px solid rgba(255,255,255,.2); background:transparent; position:relative;
  }
  .q-item-row input:checked + .tick{
    background: linear-gradient(135deg,var(--accent),var(--accent-2)); border-color:var(--accent);
  }
  .q-item-row input:checked + .tick::after{
    content:""; position:absolute; inset:3px 5px 3px 3px;
    border:2px solid #1b1b1b; border-top:0; border-left:0; transform:rotate(45deg);
  }
  .q-name{ font-weight:900 }
  .q-meta{ font-size:.85rem; color:var(--muted); margin-inline-start:.35rem }

  .controls-card{
    border:1px solid rgba(255,255,255,.10);
    background: linear-gradient(180deg, rgba(255,255,255,.03), rgba(255,255,255,.015));
    border-radius:16px; padding: .8rem 1rem; box-shadow:0 12px 32px rgba(0,0,0,.2);
  }
  .controls{
    display:grid; grid-template-columns: 1fr 1fr; gap:.8rem; align-items:center;
  }
  @media (max-width: 900px){ .controls{ grid-template-columns:1fr; } }

  .seg{
    display:flex; flex-wrap:wrap; gap:.4rem;
    background:rgba(255,255,255,.03); border:1px solid rgba(255,255,255,.10);
    padding:.35rem; border-radius:12px;
  }
  .seg input{display:none}
  .seg label{
    padding:.45rem .8rem; border-radius:10px; cursor:pointer; font-weight:900;
    border:1px solid rgba(255,255,255,.10); background:#0c1713; color:var(--text);
  }
  .seg input:checked + label{
    background: linear-gradient(135deg,var(--accent),var(--accent-2)); color:#1b1b1b;
    border-color: var(--accent);
  }

  .actions{ display:flex; gap:.6rem; flex-wrap:wrap; justify-content:center; margin-top: .2rem }
  .btn-lg{padding:.8rem 1.15rem; border-radius:12px; font-weight:900}
</style>

<form method="post" action="{% url 'core:test_selection' %}">
  {% csrf_token %}
  <div class="page-shell">
    <section class="header-card">
      <h1>اختيار النطاق</h1>
      <p class="sub">اختر الأجزاء المطلوبة ثم افتح أي جزء لتحديد أرباعه (إن رغبت).</p>

      <div class="scope-tools">
        <button type="button" id="expandAll" class="tiny-link" data-state="closed">إظهار كل الأرباع</button>
        <div class="stats" id="stats">
          <span class="stat-chip"><span class="dot juz"></span> أجزاء مختارة: <b id="juzCount">0</b></span>
          <span class="stat-chip"><span class="dot quarter"></span> أرباع مختارة: <b id="qCount">0</b></span>
        </div>
      </div>
    </section>

    <section class="accordion" aria-label="اختيار الأجزاء والأرباع">
      {% for j, data in juz_quarters_map.items %}
      <article class="ac-item" data-juz="{{ j.number }}">
        <div class="ac-head">
          <div class="ac-left">
            <label class="juz-all" title="تحديد الجزء كاملًا">
              <input type="checkbox" class="juz-toggle" name="selected_juz" value="{{ j.number }}">
              <span class="box" aria-hidden="true"></span>
            </label>
            <h3 class="ac-title">الجزء {{ j.number|arabic_digits }}</h3>
            <span class="tiny">— {{ data.first_label }}</span>
          </div>
          <button type="button" class="expand" aria-expanded="false" aria-controls="q-{{ j.number }}">إظهار الأرباع</button>
        </div>

        <div class="ac-panel" id="q-{{ j.number }}" hidden>
          <div class="q-list">
            {% for q in data.quarters %}
            <label class="q-item-row">
              <input type="checkbox" class="q-item" name="selected_quarters" value="{{ q.id }}">
              <span class="tick" aria-hidden="true"></span>
              <span class="q-name">الربع {{ q.index_in_juz }}</span>
              <span class="q-meta">{{ q.label }}</span>
            </label>
            {% endfor %}
          </div>
        </div>
      </article>
      {% endfor %}
    </section>

    <section class="controls-card" aria-label="إعدادات الاختبار">
      <div class="controls">
        <!-- عدد الأسئلة -->
        <div>
          <div class="tiny" style="margin:0 .2rem .35rem">عدد الأسئلة</div>
          <div class="seg">
            {% for n in num_questions_options %}
              <input type="radio" id="q{{ n }}" name="num_questions" value="{{ n }}" {% if forloop.first %}checked{% endif %}>
              <label for="q{{ n }}">{{ n }}</label>
            {% endfor %}
          </div>
        </div>

        <!-- مستوى الصعوبة (مخفي تلقائيًا لو نوع الامتحان هو الصفحات) -->
        {% if selected_test_type != 'similar_on_pages' %}
        <div>
          <div class="tiny" style="margin:0 .2rem .35rem">مستوى الصعوبة</div>
          <div class="seg">
            <input type="radio" id="d-mixed" name="difficulty" value="mixed" checked>
            <label for="d-mixed">مختلط</label>

            <input type="radio" id="d-easy" name="difficulty" value="easy">
            <label for="d-easy">سهل</label>

            <input type="radio" id="d-medium" name="difficulty" value="medium">
            <label for="d-medium">متوسط</label>

            <input type="radio" id="d-hard" name="difficulty" value="hard">
            <label for="d-hard">صعب</label>
          </div>
        </div>
        {% endif %}
      </div>
    </section>

    <!-- أزرار -->
    <section class="actions">
      <a href="{% url 'core:main_menu' %}" class="btn btn-outline btn-lg">الرجوع للرئيسية</a>
      <button class="btn btn-primary btn-lg" type="submit">ابدأ الاختبار</button>
      <button class="btn btn-outline btn-lg" type="button" id="clearAll">تفريغ الاختيارات</button>
    </section>
  </div>
</form>

<script>
  (function(){
    const items = document.querySelectorAll('.ac-item');
    const expandAll = document.getElementById('expandAll');
    const qCount = document.getElementById('qCount');
    const jCount = document.getElementById('juzCount');
    const clearBtn = document.getElementById('clearAll');

    function recalc(){
      const quarters = document.querySelectorAll('.q-item:checked');
      const juz = document.querySelectorAll('.juz-toggle:checked');
      if(qCount) qCount.textContent = quarters.length;
      if(jCount) jCount.textContent = juz.length;
    }

    function setOpen(card, open){
      const btn = card.querySelector('.expand');
      const panel = card.querySelector('.ac-panel');
      if(!btn || !panel) return;
      panel.toggleAttribute('hidden', !open);
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
      btn.textContent = open ? 'إخفاء الأرباع' : 'إظهار الأرباع';
    }

    items.forEach(card=>{
      const btn = card.querySelector('.expand');
      const panel = card.querySelector('.ac-panel');
      const toggle = card.querySelector('.juz-toggle');
      const quarters = card.querySelectorAll('.q-item');

      if(btn && panel){
        btn.addEventListener('click', ()=>{
          const isOpen = !panel.hasAttribute('hidden');
          setOpen(card, !isOpen);
        });
      }

      if(toggle){
        toggle.addEventListener('change', ()=>{
          quarters.forEach(q => { q.checked = toggle.checked; });
          recalc();
        });
      }

      quarters.forEach(q=>{
        q.addEventListener('change', ()=>{
          if(toggle){
            toggle.checked = Array.from(quarters).every(x => x.checked);
          }
          recalc();
        });
      });
    });

    if(expandAll){
      expandAll.addEventListener('click', ()=>{
        const open = expandAll.getAttribute('data-state') !== 'open';
        items.forEach(card => setOpen(card, open));
        expandAll.setAttribute('data-state', open ? 'open' : 'closed');
        expandAll.textContent = open ? 'إخفاء كل الأرباع' : 'إظهار كل الأرباع';
      });
    }

    if(clearBtn){
      clearBtn.addEventListener('click', ()=>{
        document.querySelectorAll('.q-item, .juz-toggle').forEach(x=> x.checked = false);
        recalc();
        window.scrollTo({top:0, behavior:'smooth'});
      });
    }

    recalc();
  })();
</script>
{% endblock %}


# ===== FILE: core/templatetags/__init__.py =====


# ===== FILE: core/templatetags/arabic_extras.py =====
from django import template

register = template.Library()

ARABIC_INDIC_DIGITS = str.maketrans('0123456789', '٠١٢٣٤٥٦٧٨٩')

@register.filter
def arabic_digits(value):
    try:
        return str(value).translate(ARABIC_INDIC_DIGITS)
    except Exception:
        return value

@register.filter
def juz_ordinal_arabic(number):
    mapping = {
        1:'الأول',2:'الثاني',3:'الثالث',4:'الرابع',5:'الخامس',6:'السادس',
        7:'السابع',8:'الثامن',9:'التاسع',10:'العاشر',11:'الحادي عشر',
        12:'الثاني عشر',13:'الثالث عشر',14:'الرابع عشر',15:'الخامس عشر',
        16:'السادس عشر',17:'السابع عشر',18:'الثامن عشر',19:'التاسع عشر',
        20:'العشرون',21:'الحادي والعشرون',22:'الثاني والعشرون',23:'الثالث والعشرون',
        24:'الرابع والعشرون',25:'الخامس والعشرون',26:'السادس والعشرون',
        27:'السابع والعشرون',28:'الثامن والعشرون',29:'التاسع والعشرون',
        30:'الثلاثون',
    }
    try:
        n = int(number)
        return f"الجزء {mapping.get(n, n)}"
    except Exception:
        return number

SURAH_NAMES = [
    "", "البقرة؟",  # placeholder index 0
]
# أسماء السور كاملة:
SURAH_NAMES = [
 "", "الفاتحة","البقرة","آل عمران","النساء","المائدة","الأنعام","الأعراف","الأنفال","التوبة",
 "يونس","هود","يوسف","الرعد","إبراهيم","الحجر","النحل","الإسراء","الكهف","مريم","طه",
 "الأنبياء","الحج","المؤمنون","النور","الفرقان","الشعراء","النمل","القصص","العنكبوت","الروم",
 "لقمان","السجدة","الأحزاب","سبأ","فاطر","يس","الصافات","ص","الزمر","غافر",
 "فصلت","الشورى","الزخرف","الدخان","الجاثية","الأحقاف","محمد","الفتح","الحجرات","ق",
 "الذاريات","الطور","النجم","القمر","الرحمن","الواقعة","الحديد","المجادلة","الحشر","الممتحنة",
 "الصف","الجمعة","المنافقون","التغابن","الطلاق","التحريم","الملك","القلم","الحاقة","المعارج",
 "نوح","الجن","المزمل","المدثر","القيامة","الإنسان","المرسلات","النبأ","النازعات","عبس",
 "التكوير","الانفطار","المطففين","الانشقاق","البروج","الطارق","الأعلى","الغاشية","الفجر","البلد",
 "الشمس","الليل","الضحى","الشرح","التين","العلق","القدر","البينة","الزلزلة","العاديات",
 "القارعة","التكاثر","العصر","الهمزة","الفيل","قريش","الماعون","الكوثر","الكافرون","النصر",
 "المسد","الإخلاص","الفلق","الناس"
]

@register.filter
def surah_name(num):
    try:
        n = int(num)
        if 1 <= n <= 114:
            return SURAH_NAMES[n]
    except Exception:
        pass
    return f"سورة {num}"

PLACE_WORDS = {1:"الأول",2:"الثاني",3:"الثالث",4:"الرابع",5:"الخامس",6:"السادس",7:"السابع",8:"الثامن",9:"التاسع",10:"العاشر",
               11:"الحادي عشر",12:"الثاني عشر",13:"الثالث عشر",14:"الرابع عشر",15:"الخامس عشر",16:"السادس عشر",
               17:"السابع عشر",18:"الثامن عشر",19:"التاسع عشر",20:"العشرون"}

@register.filter
def place_ordinal(n):
    try:
        n = int(n)
        return f"الموضع {PLACE_WORDS.get(n, n)}"
    except Exception:
        return f"الموضع {n}"


# ===== FILE: core/templatetags/highlight.py =====
import re
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

DIAC = re.compile(r'[\u064B-\u0652\u0670\u06DF-\u06ED]')

def _strip_diac(s: str) -> str:
    return DIAC.sub('', s or '')

@register.filter(is_safe=True)
def highlight(text, phrase):
    """
    إبراز العبارة داخل النص مع تجاهل الحركات.
    يبني نمطاً يسمح بظهور الحركات اختيارياً بين الحروف، والمسافات = \s+.
    """
    if not phrase or not text:
        return text
    plain = _strip_diac(phrase)
    if not plain:
        return text

    # ابنِ نمطًا حرف-بحرف يسمح بحركات اختيارية
    parts = []
    for ch in plain:
        if ch.isspace():
            parts.append(r'\s+')
        else:
            # الحرف ثم أي عدد من الحركات بعده
            parts.append(re.escape(ch) + r'[\u064B-\u0652\u0670\u06DF-\u06ED]*')
    pattern = ''.join(parts)

    def repl(m):
        return f"<mark>{m.group(0)}</mark>"

    try:
        highlighted = re.sub(pattern, repl, text, flags=re.IGNORECASE)
    except re.error:
        return text
    return mark_safe(highlighted)


# ===== FILE: core/urls.py =====
from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    # Landing على /
    path("", views.landing, name="landing"),

    # Main menu
    path("home/", views.main_menu, name="main_menu"),

    # Auth
    path("login/", views.login_view, name="login"),
    path("signup/", views.signup_view, name="signup"),
    path("logout/", views.logout_view, name="logout"),

    # Test flow
    path("test/", views.test_selection, name="test_selection"),
    path("start/", views.start_test, name="start_test"),
    path("test-question/", views.test_question, name="test_question"),
    path("report-question/", views.report_question, name="report_question"),

    # Complaints
    path("complaint/", views.complaint, name="complaint"),
    path("admin/complaints/", views.admin_complaints, name="admin_complaints"),

    path("account/", views.account_settings, name="account_settings"),

    path("stats/", views.stats, name="stats"),
    path('leaderboard/', views.leaderboard, name='leaderboard'),
    path("tests/", views.test_catalog, name="test_catalog"),
    path("api/quarter/<int:qid>/pages/", views.quarter_pages_api, name="quarter_pages_api"),
    path("api/page/<int:pno>/ayat/", views.page_ayat_api, name="page_ayat_api"),
    path("quarter/<int:qid>/pages/", views.quarter_pages_view, name="quarter_pages_view"),
    path("page-svg/<int:pno>.svg", views.page_svg, name="page_svg_proxy"),
    path("test/pages/choose-juz/", views.pages_choose_juz, name="pages_choose_juz"),
    path("test/pages/choose-quarter/<int:juz_no>/", views.pages_choose_quarter, name="pages_choose_quarter"),
    path("test/pages/choose-quarter/<int:juz_no>/", views.pages_choose_quarter, name="pages_choose_quarter"),
    path("test/pages/quarter/<int:qid>/", views.pages_quarter_pick, name="pages_quarter_pick"),
    path("api/test/pages/select-first/", views.api_pages_select_first, name="api_pages_select_first"),
    path("test/pages/quarter/<int:qid>/viewer/", views.pages_quarter_viewer, name="pages_quarter_viewer"),
    path("test/page-svg/<int:pno>/", views.page_svg, name="page_svg"),









]


# ===== FILE: core/validators.py =====
import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

class AlphaNumericPasswordValidator:
    """
    يفرض احتواء كلمة المرور على الأقل على حرف واحد ورقم واحد
    بالإضافة إلى حد الطول (الذي يفرضه MinimumLengthValidator).
    """
    def validate(self, password, user=None):
        if not re.search(r'[A-Za-z]', password or ''):
            raise ValidationError(_("يجب أن تحتوي كلمة المرور على حرف واحد على الأقل."), code="password_no_letter")
        if not re.search(r'\d', password or ''):
            raise ValidationError(_("يجب أن تحتوي كلمة المرور على رقم واحد على الأقل."), code="password_no_digit")

    def get_help_text(self):
        return _("يجب أن تحتوي كلمة المرور على أحرف وأرقام على الأقل.")


# ===== FILE: core/views.py =====
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.db.models import Count, Sum, Q
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from .forms import AccountForm, PasswordChangeTightForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.http import JsonResponse
from .models import Ayah, Page
from django.conf import settings
from django.http import FileResponse, Http404
import os
from django.db.models import Exists, OuterRef



import math, random, re, unicodedata

from django.views.decorators.http import require_POST
from .models import (
    Student, Complaint, Juz, Quarter, SimilarityGroup, Ayah,
    Phrase, PhraseOccurrence, TestSession, TestQuestion
)


# ===== Helpers for ordinals and occurrence mapping =====
AR_ORD = {1:"الأول",2:"الثاني",3:"الثالث",4:"الرابع",5:"الخامس",6:"السادس",7:"السابع",8:"الثامن",9:"التاسع",10:"العاشر"}
def ar_ordinal(n:int) -> str:
    return f"الـ{AR_ORD.get(n, n)}"

def _current_question_and_flow(request):
    """
    يرجّع السؤال الجاري (لو موجود في الفلو) + كائن flow كما هو.
    - يعتمد على: request.session['questions'] (قائمة أسئلة)
    - و: request.session['pages_flow'] (قاموس به q_index/current/target_total ...)
    """
    qs = request.session.get('questions') or []
    flow = request.session.get('pages_flow') or {}
    q_index = flow.get('q_index')
    if q_index is None or not (0 <= q_index < len(qs)):
        return None, flow
    return qs[q_index], flow
    
def _feedback(kind: str, text: str):
    """
    كائن بسيط للواجهة (علشان تعرض شارة/سطر حالة):
    kind: success | warning | error | info
    """
    return {"kind": kind, "text": text}

def _allowed_juz_numbers_for_scope(request):
    """
    يرجّع قائمة أرقام الأجزاء المسموحة طبقًا لنطاق الاختبار + وجود صفحات فعلًا.
    يعتمد على selected_quarters / selected_juz من السيشن.
    """
    sel_quarters = request.session.get('selected_quarters') or []
    sel_juz = request.session.get('selected_juz') or []

    # أرباع لديها صفحات فعلاً (أي آية فيها page__isnull=False)
    quarters_with_pages = Quarter.objects.filter(
        id=OuterRef('id'),
        ayah__page__isnull=False
    )

    qs = Quarter.objects.all().annotate(
        has_pages=Exists(quarters_with_pages)
    ).filter(has_pages=True)

    if sel_quarters:
        qs = qs.filter(id__in=sel_quarters)
    elif sel_juz:
        try:
            sel_juz = [int(j) for j in sel_juz]
        except Exception:
            sel_juz = []
        if sel_juz:
            qs = qs.filter(juz__number__in=sel_juz)

    allowed = sorted(set(qs.values_list('juz__number', flat=True)))

    # Fallback لو فاضيين: أي جزء فيه صفحات
    if not allowed:
        qs_any = Quarter.objects.annotate(
            has_pages=Exists(Quarter.objects.filter(
                id=OuterRef('id'), ayah__page__isnull=False
            ))
        ).filter(has_pages=True)
        allowed = sorted(set(qs_any.values_list('juz__number', flat=True)))

    return allowed

def _ctx_common(request, extra=None, feedback=None, delta=None):
    """
    يضيف للكونتكست:
    - score_now: الدرجة الحالية
    - current_phrase: نص العبارة الجارية
    - step_no/target_total/step_label: مرحلة اختيار المواضع
    - feedback: رسالة فورية (success/warning/error/info)
    - delta: +1/-1 لتحديث العدّاد بصريًا (اختياري)
    """
    extra = extra or {}
    q, flow = _current_question_and_flow(request)

    extra['score_now'] = int(request.session.get('score', 0))
    extra['step_no'] = int((flow or {}).get('current') or 1)
    extra['target_total'] = int((flow or {}).get('target_total') or 0)

    phrase = ''
    if q:
        phrase = q.get('phrase_text') or q.get('phrase') or ''
    extra['current_phrase'] = phrase or '—'

    extra['step_label'] = (
        f"الموضع {ar_ordinal(extra['step_no'])}"
        + (f" من {extra['target_total']}" if extra['target_total'] else "")
    )

    if feedback:
        extra['feedback'] = feedback
    if delta is not None:
        extra['delta'] = int(delta)

    return extra


# ------------------------------------------------------------------
# أدوات التطبيع
# ------------------------------------------------------------------
DIAC = re.compile(r'[\u064B-\u0652\u0670\u06DF-\u06ED]')
def norm(txt: str) -> str:
    txt = unicodedata.normalize('NFKD', txt)
    txt = DIAC.sub('', txt)
    txt = txt.replace('إ', 'ا').replace('أ', 'ا').replace('آ', 'ا')
    txt = txt.replace('ة', 'ه').replace('ى', 'ي')
    txt = re.sub(r'[^\w\s]', '', txt)
    return txt

# كلمات لها نهايات/صرفيات شائعة (احتياطي)
WORD_ALIASES = {
    'تكن': r'تكون(?:ن|نَّ)?',
    'قول': r'قول(?:وا)?',
    'تلبسون': r'تلبسون?|تلبسوا(?:ن)?',
}
def flex_regex(word_list):
    parts = []
    for w in word_list:
        key = norm(w)
        pat = WORD_ALIASES.get(key, re.escape(key))
        parts.append(pat)
    return r'\s+'.join(parts)
# ------------------------------------------------------------------

# Configuration
ALLOWED_NUM_QUESTIONS = [5, 10, 15, 20]
COMPLAINT_TYPES = [
    "خطأ في السؤال", "تصميم / واجهة", "اقتراح تحسين",
    "إضافة ميزة", "مشكلة تقنية", "أخرى",
]

def make_options(correct_count: int):
    """اختيارات مرتّبة تصاعديًا بدون تدوير، حول الإجابة الصحيحة."""
    pool = {correct_count}
    for off in (-3, -2, -1, 1, 2, 3, 4, 5):
        v = correct_count + off
        if v >= 1:
            pool.add(v)
        if len(pool) >= 4:
            break
    return sorted(pool)[:4]


def _build_scope_label(selected_juz_ids, selected_quarter_ids):
    if selected_quarter_ids:
        quarters = Quarter.objects.filter(id__in=selected_quarter_ids).select_related('juz')
        by_juz = {}
        for q in quarters:
            by_juz.setdefault(q.juz.number, []).append(q)
        parts = []
        for j in sorted(by_juz):
            qs = by_juz[j]
            if len(qs) == 8:
                parts.append(f"الجزء {j}")
            else:
                idx = ', '.join(f"الربع {q.index_in_juz}" for q in sorted(qs, key=lambda x: x.index_in_juz))
                parts.append(f"الجزء {j} - {idx}")
        return "اختبار على: " + "؛ ".join(parts)
    elif selected_juz_ids:
        lbl = '؛ '.join(f"الجزء {j}" for j in sorted(selected_juz_ids))
        return f"اختبار على: {lbl}"
    return "اختبار على: نطاق غير محدد"

# --------------------------- landing --------------------------- #
def landing(request):
    """صفحة هبوط عامة في الجذر /"""
    # لو المستخدم مسجّل دخوله، حوّله للـ Home
    if request.user.is_authenticated:
        student, _ = Student.objects.get_or_create(
            user=request.user, defaults={'display_name': request.user.username}
        )
        request.session['student_id'] = student.id
        return redirect('core:main_menu')

    # لو مش مسجّل دخوله، اعرض الاندينج عادي
    ctx = {
        'hide_footer': False,
        'show_splash': True,
        'is_logged_in': False,
    }
    return render(request, 'core/landing.html', ctx)



# --------------------------- auth --------------------------- #
def login_view(request):
    # لو المستخدم داخل بالفعل، ودِّيه على الهوم
    if request.user.is_authenticated:
        student, _ = Student.objects.get_or_create(
            user=request.user, defaults={'display_name': request.user.username}
        )
        request.session['student_id'] = student.id
        return redirect('core:main_menu')

    if request.method == 'POST':
        identifier = request.POST.get('username', '').strip()
        password   = request.POST.get('password', '').strip()

        if not identifier or not password:
            messages.error(request, "كل الحقول مطلوبة لتسجيل الدخول.")
            return redirect('core:login')

        # ابحث أولاً بـ display_name ثم username ثم email (بدون حساسية لحالة الأحرف)
        user_obj = None
        stu = Student.objects.select_related('user').filter(display_name__iexact=identifier).first()
        if stu:
            user_obj = stu.user
        else:
            user_obj = User.objects.filter(username__iexact=identifier).first()
            if not user_obj:
                user_obj = User.objects.filter(email__iexact=identifier).first()

        user = None
        if user_obj:
            user = authenticate(request, username=user_obj.username, password=password)

        if user is None:
            messages.error(request, "اسم الدخول/البريد أو كلمة المرور غير صحيحة.")
            return redirect('core:login')

        login(request, user)
        student, _ = Student.objects.get_or_create(user=user, defaults={'display_name': user.username})
        request.session['student_id'] = student.id
        return redirect('core:main_menu')

    return render(request, 'core/login.html', {'hide_footer': False})


def signup_view(request):
    if request.user.is_authenticated:
        return redirect('core:main_menu')

    if request.method == 'POST':
        student_name = request.POST.get('student_name','').strip()
        password = request.POST.get('password','').strip()

        if not student_name:
            messages.error(request,"اسم الطالب مطلوب للتسجيل.")
            return redirect('core:signup')
        if not password:
            messages.error(request,"كلمة المرور مطلوبة.")
            return redirect('core:signup')

        # تحقق المتطلبات عبر Validators الرسمية
        username = student_name.lower().replace(' ','_')
        try:
            tmp_user = User(username=username, email="")
            validate_password(password, user=tmp_user)
        except ValidationError as e:
            messages.error(request, " ".join(e.messages))
            return redirect('core:signup')

        # امنع تكرار اسم الطالب (display_name)
        if Student.objects.filter(display_name__iexact=student_name).exists():
            messages.error(request, "اسم الطالب مستخدم بالفعل. لو ده حسابك جرّب تسجيل الدخول، أو اختر اسمًا مميزًا.")
            return redirect('core:signup')

        if User.objects.filter(username=username).exists():
            messages.error(request,"اسم المستخدم موجود بالفعل. جرّب تعديل الاسم قليلًا.")
            return redirect('core:signup')

        try:
            user = User.objects.create_user(username=username)
            user.set_password(password)
            user.save()
        except IntegrityError:
            messages.error(request,"حصل خطأ في إنشاء الحساب، جرب اسم آخر.")
            return redirect('core:signup')

        student = Student.objects.create(user=user, display_name=student_name)
        login(request,user)
        request.session['student_id'] = student.id
        return redirect('core:main_menu')

    return render(request,'core/signup.html', {'hide_footer': False})


@login_required
def logout_view(request):
    logout(request)
    messages.success(request,"تم تسجيل الخروج.")
    return redirect('core:login')

@login_required
def main_menu(request):
    sid = request.session.get('student_id')
    if not sid:
        student, _ = Student.objects.get_or_create(
            user=request.user, defaults={'display_name': request.user.username}
        )
        request.session['student_id'] = student.id
    student = get_object_or_404(Student, id=request.session['student_id'])

    stats = _user_stats(student)
    # ترتيب المستخدم (لو سبق له الامتحان)
    lb_all = _leaderboard()
    my_rank = next((r['rank'] for r in lb_all if r['student_id'] == student.id), None)

    return render(request,'core/main_menu.html',{
        'student': student,
        'stats': stats,
        'my_rank': my_rank,
        'show_splash': True,
        'hide_footer': False,
    })


# === حساب نقاط السكوربورد (احتفظنا بيها لو حبيت تستخدمها لاحقًا) ===
def _score_formula(exams, correct, wrong, unanswered):
    # أساس عادل + مكافأة دقة + مكافأة حجم نشاط (سقف 30 امتحان)
    base = correct - 0.6 * wrong - 0.2 * unanswered
    acc = (correct / (correct + wrong)) if (correct + wrong) else 0.0
    volume_bonus = min(exams, 30) * 2
    return round(max(0, base + 40 * acc + volume_bonus), 2)


@login_required
def leaderboard(request):
    student = get_object_or_404(Student, user=request.user)
    rows = _leaderboard()
    my_rank = next((r['rank'] for r in rows if r['student_id'] == student.id), None)
    return render(request, 'core/leaderboard.html', {
        'rows'      : rows,
        'student'   : student,
        'my_rank'   : my_rank,
        'hide_footer': False,
    })


def _leaderboard():
    """
    لوح منافسة عادل:
    - accuracy (الدقة) لها وزن أساسي.
    - correct (إجمالي الصح) له وزن بحساب لوجاريتمي (علشان يقلّل أثر التفرعات الكبيرة).
    - exams (عدد الامتحانات المكتملة) له وزن برضه لوجاريتمي.
    score = 600*accuracy + 300*log10(1+correct) + 100*log10(1+exams)
    """
    # كل الجلسات المكتملة
    sess = (TestSession.objects
            .filter(completed=True)
            .values('student')
            .annotate(exams=Count('id'),
                      total_q=Sum('num_questions')))

    # إجابات الأسئلة المربوطة بجلسات مكتملة
    ans = (TestQuestion.objects
           .filter(session__completed=True)
           .values('session__student')
           .annotate(
               answered=Count('id'),
               correct=Count('id', filter=Q(is_correct=True)),
               wrong=Count('id', filter=Q(is_correct=False)),
           ))

    by_student = {}
    for r in sess:
        sid = r['student']
        by_student[sid] = {
            'student_id': sid,
            'exams': r.get('exams', 0) or 0,
            'total_q': r.get('total_q', 0) or 0,
            'answered': 0,
            'correct': 0,
            'wrong': 0,
        }
    for r in ans:
        sid = r['session__student']
        row = by_student.setdefault(sid, {
            'student_id': sid, 'exams': 0, 'total_q': 0,
            'answered': 0, 'correct': 0, 'wrong': 0
        })
        row['answered'] = (row['answered'] or 0) + (r.get('answered', 0) or 0)
        row['correct']  = (row['correct']  or 0) + (r.get('correct', 0) or 0)
        row['wrong']    = (row['wrong']    or 0) + (r.get('wrong', 0) or 0)

    if not by_student:
        return []

    sids = list(by_student.keys())
    students = (Student.objects
                .select_related('user')
                .filter(id__in=sids))
    stu_map = {s.id: s for s in students}

    rows = []
    for sid, r in by_student.items():
        s = stu_map.get(sid)
        if not s:
            continue
        exams = r['exams'] or 0
        if exams <= 0:
            # ما يدخلش اللوحة إلا اللي عنده امتحان مكتمل على الأقل
            continue
        correct = r['correct'] or 0
        wrong   = r['wrong'] or 0
        answered = r['answered'] or 0
        total_q = r['total_q'] or 0
        unanswered = max(0, total_q - answered)

        # الدقة تحسب غير مُجاب أيضًا
        denom = max(1, correct + wrong + unanswered)
        accuracy = correct / denom

        # خصم بسيط مقابل غير المُجاب + منع السكور السالب
        score = (600.0 * accuracy) \
                + (300.0 * math.log10(1 + correct)) \
                + (100.0 * math.log10(1 + exams)) \
                - (10.0 * unanswered)
        score = int(round(max(0, score)))


        rows.append({
            'student_id': sid,
            'display_name': s.display_name or s.user.username,
            'avatar': s.avatar.url if getattr(s, 'avatar', None) else '',
            'exams': exams,
            'correct': correct,
            'wrong': wrong,
            'unanswered': unanswered,
            'accuracy': accuracy,
            'accuracy_pct': round(accuracy*100, 2),
            'score': score,
        })

    # الترتيب والتساوي
    rows.sort(key=lambda x: (-x['score'], -x['accuracy'], -x['correct'], x['display_name']))
    last_score = None
    rank = 0
    for i, r in enumerate(rows, start=1):
        if r['score'] != last_score:
            rank = i
            last_score = r['score']
        r['rank'] = rank

    return rows


# ---------------------- complaint ------------------------ #
@login_required
def complaint(request):
    sid=request.session.get('student_id')
    if not sid:
        messages.warning(request,"الرجاء تسجيل الدخول أولاً."); return redirect('core:login')
    student=get_object_or_404(Student,id=sid)
    if request.method == 'POST':
        cats=request.POST.getlist('category'); txt=request.POST.get('text','').strip()
        if not txt and not cats:
            messages.error(request,"لا يمكن إرسال شكوى فارغة.")
        else:
            prefix=f"[{', '.join(cats)}] " if cats else ''
            Complaint.objects.create(student=student, text=prefix+txt if txt else prefix)
            messages.success(request,"تم إرسال الشكوى/الاقتراح بنجاح.")
            return redirect('core:main_menu')
    return render(request,'core/complaint.html',{'student':student,'types':COMPLAINT_TYPES, 'hide_footer': False})



# -----------------------------------------------------
# 1) كتالوج الاختبارات: النوعين يمرّوا على test_selection
# -----------------------------------------------------
def test_catalog(request):
    tests = [
        {
            "key": "similar_count",
            "title": " عدد مواضع المتشابهات",
            "desc": "يعرض عبارة ويطلب عدد مواضعها الصحيحة في نطاقك.",
            "available": True,
            "url": reverse("core:test_selection") + "?type=similar_count",
        },
        {
            "key": "similar_on_pages",
            "title": "مواضع المتشابهات في الصفحات",
            "desc": "اختيار النطاق ثم تحديد الصفحات والمواضع لكل سؤال.",
            "available": True,
            "url": reverse("core:test_selection") + "?type=similar_on_pages",
        },
        {
            "key": "page_edges_quarters",
            "title": "بداية ونهاية الصفحات مع الأرباع",
            "desc": "استنتاج بدايات/نهايات الآيات بين الصفحات داخل نطاقك.",
            "available": False,
        },
        {
            "key": "order_juz_quarters",
            "title": "اختبار ترتيب الأجزاء والأرباع",
            "desc": "أسئلة لقياس ترتيب الأجزاء والأرباع وتسلسلها.",
            "available": False,
        },
        {
            "key": "semantic_similarities",
            "title": "متشابهات معاني الآيات",
            "desc": "أسئلة على التشابه الدلالي للمعاني.",
            "available": False,
        },
    ]
    return render(request, "core/test_catalog.html", {
        "tests": tests,
        "hide_footer": False,
    })


# -----------------------------------------------------
# 2) شاشة اختيار النطاق (مُوحَّدة للاختبارين)
# -----------------------------------------------------
@login_required
def test_selection(request):
    sid = request.session.get('student_id')
    if not sid:
        messages.warning(request, "الرجاء إدخال اسمك أولاً.")
        return redirect('core:login')
    student = get_object_or_404(Student, id=sid)

    # خزّن نوع الاختبار إن جالك من الكتالوج
    test_type_qs = request.GET.get('type')
    if test_type_qs:
        request.session['selected_test_type'] = test_type_qs
    if not request.session.get('selected_test_type'):
        request.session['selected_test_type'] = 'similar_count'

    if request.method == 'POST':
        sel_juz = request.POST.getlist('selected_juz')
        sel_q   = request.POST.getlist('selected_quarters')
        try:
            num_q = int(request.POST.get('num_questions', 5))
        except ValueError:
            num_q = 5
        if num_q not in [5,10,15,20]:
            num_q = 5

        difficulty = request.POST.get('difficulty', 'mixed')  # لو صفحات مش هنستخدمها لاحقًا

        sel_juz = [int(j) for j in sel_juz if str(j).isdigit()]
        sel_q   = [int(q) for q in sel_q if str(q).isdigit()]
        if not sel_juz and not sel_q:
            messages.error(request, "لازم تختار جزء أو رُبع.")
            return redirect('core:test_selection')

        request.session.update({
            'selected_juz': sel_juz,
            'selected_quarters': sel_q,
            'num_questions': num_q,
            'difficulty': difficulty,
            'test_index': 0,
            'score': 0,
        })
        request.session.pop('scope_label', None)
        return redirect('core:start_test')

    # تجهيز عرض الأجزاء + أرباعها
    juz_list = Juz.objects.all().order_by('number')
    juz_quarters_map = {}
    for j in juz_list:
        qs = list(Quarter.objects.filter(juz=j).order_by('index_in_juz'))
        first_label = qs[0].label if qs else ''
        juz_quarters_map[j] = {'quarters': qs, 'first_label': first_label}

    return render(request, 'core/test_selection.html', {
        'student': student,
        'juz_quarters_map': juz_quarters_map,
        'num_questions_options': [5,10,15,20],
        'show_splash': True,
        'hide_footer': False,
        'selected_test_type': request.session.get('selected_test_type', 'similar_count'),
    })


# -----------------------------------------------------
# 3) بدء الاختبار: اختيار الأسئلة ثم التفريع حسب النوع
# -----------------------------------------------------
@login_required
def start_test(request):
    sid = request.session.get('student_id')
    if not sid:
        messages.warning(request, "الرجاء إدخال اسمك أولاً.")
        return redirect('core:login')
    student = get_object_or_404(Student, id=sid)

    juz_ids = request.session.get('selected_juz', [])
    q_ids   = request.session.get('selected_quarters', [])
    desired = int(request.session.get('num_questions', 5))
    difficulty = request.session.get('difficulty','mixed')

    # آيات النطاق
    if q_ids:
        ayat_qs = Ayah.objects.filter(quarter_id__in=q_ids)
    elif juz_ids:
        ayat_qs = Ayah.objects.filter(quarter__juz__number__in=juz_ids)
    else:
        messages.error(request, "مفيش نطاق محدد.")
        return redirect('core:test_selection')

    if not ayat_qs.exists():
        messages.error(request, "النطاق لا يحتوى آيات.")
        return redirect('core:test_selection')

    ayat_ids = list(ayat_qs.values_list('id', flat=True))

    # احصاءات التكرار للنطاق
    MAX_OCC_SCOPE = 60
    stats = (PhraseOccurrence.objects
                .filter(ayah_id__in=ayat_ids)
                .values('phrase_id')
                .annotate(freq=Count('id'))
                .filter(freq__gte=2, freq__lte=MAX_OCC_SCOPE))
    if not stats:
        messages.error(request, "مافيش عبارات متشابهة كافية فى النطاق.")
        return redirect('core:test_selection')

    phrase_ids = [s['phrase_id'] for s in stats]
    freq_map = {s['phrase_id']: s['freq'] for s in stats}

    # occurrences per phrase
    occ_rows = (PhraseOccurrence.objects
                .filter(ayah_id__in=ayat_ids, phrase_id__in=phrase_ids)
                .values('phrase_id', 'ayah_id'))

    occ_by_phrase = {}
    for r in occ_rows:
        occ_by_phrase.setdefault(r['phrase_id'], set()).add(r['ayah_id'])

    phrases = {p.id: p for p in Phrase.objects.filter(id__in=phrase_ids)}

    # إزالة العبارات الفرعية
    sorted_pids = sorted(
        phrase_ids,
        key=lambda pid: (-phrases[pid].length_words, -freq_map[pid], phrases[pid].text)
    )
    kept, kept_sets = [], []
    for pid in sorted_pids:
        aset = occ_by_phrase[pid]
        if any(aset.issubset(S) for S in kept_sets):
            continue
        kept.append(pid); kept_sets.append(aset)

    # buckets (نفس قواعد القديم لضمان جودة الانتقاء)
    def bucket(ph_len, freq):
        if ph_len >= 5 and 2 <= freq <= 3:
            return 'easy'
        if ph_len >= 4 and 2 <= freq <= 6:
            return 'medium'
        if ph_len >= 3 and 7 <= freq <= 60:
            return 'hard'
        return 'other'

    candidates = []
    for pid in kept:
        ph = phrases[pid]; freq = freq_map[pid]
        b = bucket(ph.length_words, freq)
        if b == 'other': continue
        ayahs = (Ayah.objects
                 .filter(id__in=occ_by_phrase[pid])
                 .select_related('quarter__juz')
                 .order_by('surah', 'number'))
        literal = [{
            'surah': a.surah, 'number': a.number,
            'juz_number': a.quarter.juz.number if a.quarter else None,
            'quarter_label': a.quarter.label if a.quarter else None,
            'text': a.text,
        } for a in ayahs]
        candidates.append({
            'phrase_id': pid,
            'phrase_text': ph.text,
            'correct_count': freq,
            'occurrence_ayah_ids': list(occ_by_phrase[pid]),
            'literal_ayahs': literal,
            'bucket': b,
            'score': freq * math.log(1 + ph.length_words),
        })

    if not candidates:
        messages.error(request, "بعد تطبيق مستوى الصعوبة مابقاش فيه أسئلة مناسبة.")
        return redirect('core:test_selection')

    # اختيار نهائي
    if difficulty == 'mixed':
        E = [c for c in candidates if c['bucket']=='easy']
        M = [c for c in candidates if c['bucket']=='medium']
        H = [c for c in candidates if c['bucket']=='hard']
        random.shuffle(E); random.shuffle(M); random.shuffle(H)

        ne = max(0, round(desired * 0.40))
        nm = max(0, round(desired * 0.45))
        nh = max(0, desired - ne - nm)

        take = E[:ne] + M[:nm] + H[:nh]
        for pool in [M[nm:], E[ne:], H[nh:]]:
            if len(take) >= desired: break
            need = desired - len(take)
            take += pool[:need]
        selected = take[:desired]
        random.shuffle(selected)
    else:
        filtered = [c for c in candidates if c['bucket']==difficulty]
        if not filtered:
            messages.error(request, "لا توجد أسئلة مناسبة لهذا المستوى في النطاق.")
            return redirect('core:test_selection')
        filtered.sort(key=lambda x: (-x['score'], x['phrase_text']))
        selected = filtered[:desired]

    # إنشاء جلسة اختبار + أسئلة DB (زي القديم)
    selected_type = request.session.get('selected_test_type', 'similar_count')
    session_db = TestSession.objects.create(
        student=student,
        test_type=selected_type,
        num_questions=len(selected),
        difficulty=difficulty,
        completed=False,
    )
    if juz_ids:
        session_db.juzs.add(*Juz.objects.filter(number__in=juz_ids))
    if q_ids:
        session_db.quarters.add(*Quarter.objects.filter(id__in=q_ids))
    request.session['db_session_id'] = session_db.id

    db_qids = []
    for _ in selected:
        tq = TestQuestion.objects.create(session=session_db)
        db_qids.append(tq.id)
    request.session['db_question_ids'] = db_qids

    request.session['scope_label'] = _build_scope_label(juz_ids, q_ids)
    request.session['questions'] = [{
        'phrase_id': c['phrase_id'],
        'phrase_text': c['phrase_text'],
        'correct_count': c['correct_count'],
        'occurrence_ayah_ids': c['occurrence_ayah_ids'],
        'literal_ayahs': c['literal_ayahs'],
        'given_answer': None,
    } for c in selected]
    request.session['test_index'] = 0
    request.session['score'] = 0

    return redirect('core:test_question')




# -------------------- test question ------------------------- #
@login_required
def test_question(request):
    sid = request.session.get('student_id')
    if not sid:
        messages.warning(request, "الرجاء إدخال اسمك أولاً.")
        return redirect('core:login')
    student = get_object_or_404(Student, id=sid)

    idx   = request.session.get('test_index', 0)
    qs    = request.session.get('questions', [])
    total = len(qs)

    # انتهى الامتحان؟
    if idx >= total:
        score = request.session.get('score', 0)
        scope_lbl = request.session.get('scope_label', '')
        detailed = [{
            'phrase': q.get('phrase_text') or q.get('phrase', ''),
            'correct_count': q.get('correct_count'),
            'given_answer': q.get('given_answer'),
            'occurrences': q.get('literal_ayahs', []),
        } for q in qs]
        wrong = max(0, total - score)

        # علّم الجلسة كمكتملة
        db_sid = request.session.get('db_session_id')
        if db_sid:
            TestSession.objects.filter(id=db_sid).update(completed=True)

        # نظّف السيشن (بما فيها مفاتيح الـDB)
        for k in ['questions','test_index','score','selected_juz','selected_quarters',
                  'num_questions','scope_label','difficulty','db_session_id','db_question_ids']:
            request.session.pop(k, None)

        return render(request, 'core/test_result.html', {
            'student': student, 'score': score, 'total': total,
            'detailed_results': detailed,
            'scope_label': scope_lbl,
            'wrong': wrong,
            'hide_footer': True,
        })

    question = qs[idx]
    progress = round((idx + 1) / total * 100) if total else 0

    # إنهاء مبكر
    if request.method == 'POST' and request.POST.get('action') == 'end':
        db_sid = request.session.get('db_session_id')
        if db_sid:
            TestSession.objects.filter(id=db_sid).update(completed=True)
        request.session['test_index'] = len(qs)
        return redirect('core:test_question')

    if request.method == 'POST':
        ans = request.POST.get('occurrence')
        # خزّن الإجابة في السيشن
        try:
            qs[idx]['given_answer'] = int(ans)
        except (ValueError, TypeError):
            qs[idx]['given_answer'] = None
        request.session['questions'] = qs

        # الصحيحة لهذا السؤال
        try:
            correct_count = int(question.get('correct_count'))
        except (TypeError, ValueError):
            correct_count = -1

        # سجّل الإجابة في الـDB حسب ترتيب السؤال
        db_qids = request.session.get('db_question_ids') or []
        if isinstance(db_qids, list) and idx < len(db_qids):
            given = qs[idx]['given_answer']
            is_corr = bool(given is not None and int(given) == correct_count)
            TestQuestion.objects.filter(id=db_qids[idx]).update(
                student_response=str(given if given is not None else ''),
                is_correct=is_corr
            )

        # لو النوع صفحات → جهّز فلو الصفحات لهذا السؤال ولا تزود المؤشر
        selected_type = request.session.get('selected_test_type', 'similar_count')
        ans_val = None
        try:
            ans_val = int(ans) if ans and ans.isdigit() else None
        except Exception:
            ans_val = None

        if selected_type == 'similar_on_pages':
            request.session['pages_flow'] = {
                'q_index': idx,                           # نفس السؤال الحالي
                'target_total': max(0, ans_val or 0),     # عدد المواضع التي سيحددها
                'current': 1,                              # ابدأ بالموضع الأول
            }
            return redirect('core:pages_choose_juz')

        # غير كده: فلو الامتحان الأول كالعادة
        if ans and ans.isdigit() and int(ans) == correct_count:
            request.session['score'] = request.session.get('score', 0) + 1
        request.session['test_index'] = idx + 1
        return redirect('core:test_question')

    # تجهيز نص العبارة للعرض
    phrase_txt = question.get('phrase_text') or question.get('phrase')
    if not phrase_txt:
        pid = question.get('phrase_id')
        if pid:
            try:
                phrase_txt = Phrase.objects.only('text').get(id=pid).text
            except Phrase.DoesNotExist:
                phrase_txt = ''
        else:
            phrase_txt = ''

    try:
        correct_count = int(question.get('correct_count'))
    except (TypeError, ValueError):
        correct_count = 2
    options = make_options(correct_count)

    return render(request, 'core/test_question.html', {
        'student': student,
        'question_number': idx + 1, 'total_questions': total,
        'phrase': phrase_txt,
        'options': options,
        'scope_label': request.session.get('scope_label', ''),
        'progress_percent': progress,
        'correct_count': correct_count,
        'submitted': False,
        'hide_footer': True,
    })

# -------------------- admin complaints ---------------------- #
@user_passes_test(lambda u:u.is_staff)
def admin_complaints(request):
    comps=Complaint.objects.select_related('student__user').order_by('-created_at')
    if request.method=='POST':
        cid=request.POST.get('complaint_id'); action=request.POST.get('action')
        try:
            c=Complaint.objects.get(id=cid)
            if action=='toggle':
                c.resolved=not c.resolved; c.save()
                messages.success(request,f"تم تحديث حالة الشكوى #{cid}.")
        except Complaint.DoesNotExist:
            messages.error(request,"الشكوى غير موجودة.")
    return render(request,'core/complaint_admin.html',{'complaints':comps, 'hide_footer': False})

# -------------------- report question (زر الإبلاغ) --------- #
from django.http import JsonResponse

@login_required
@require_POST
def report_question(request):
    sid = request.session.get('student_id')
    student = get_object_or_404(Student, id=sid)

    text = (request.POST.get('text','') or '').strip() or '(بدون وصف)'
    phrase = (request.POST.get('phrase','') or '').strip()
    q_no = request.POST.get('question_number','?')
    given = request.POST.get('given','—')
    correct = request.POST.get('correct','—')
    src = request.POST.get('from','test')

    body = (
        f"[إبلاغ سؤال — المصدر: {src}] "
        f"سؤال رقم: {q_no} | العبارة: \"{phrase}\" | إجابة الطالب: {given} | الصحيحة: {correct}\n"
        f"وصف المشكلة: {text}"
    )
    Complaint.objects.create(student=student, text=body)

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({"ok": True, "message": "تم إرسال الإبلاغ. شكراً لك."})

    return render(request, 'core/report_done.html', {'hide_footer': True})

@login_required
def account_settings(request):
    student = get_object_or_404(Student, user=request.user)
    prof_form = AccountForm(initial={
        'display_name': student.display_name,
        'email': request.user.email,
    })
    pass_form = PasswordChangeTightForm(user=request.user)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'update_profile':
            prof_form = AccountForm(request.POST, request.FILES)
            if prof_form.is_valid():
                request.user.email = prof_form.cleaned_data.get('email', '') or ''
                request.user.save()
                student.display_name = prof_form.cleaned_data['display_name']
                avatar_file = prof_form.cleaned_data.get('avatar')
                if avatar_file:
                    student.avatar = avatar_file
                if request.POST.get('remove_avatar') == '1' and student.avatar:
                    student.avatar.delete(save=False)
                    student.avatar = None
                student.save()
                messages.success(request, "تم تحديث بيانات الحساب.")
                return redirect('core:account_settings')
        elif action == 'change_password':
            pass_form = PasswordChangeTightForm(user=request.user, data=request.POST)
            if pass_form.is_valid():
                user = pass_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, "تم تحديث كلمة المرور.")
                return redirect('core:account_settings')

    return render(request,'core/account_settings.html',{
        'student': student,
        'profile_form': prof_form,
        'password_form': pass_form,
        'hide_footer': False,
    })

def _user_stats(student: Student):
    """احسب إحصائيات المستخدم من الجلسات والأسئلة المخزنة (بدقة)."""
    # نستخدم الأسئلة الفعلية المسجّلة
    qs = TestQuestion.objects.filter(session__student=student)
    total_qs = qs.count()
    correct = qs.filter(is_correct=True).count()
    # الغلط المُجاب: is_correct=False لكن فيه student_response
    wrong   = qs.filter(is_correct=False).exclude(student_response='').exclude(student_response__isnull=True).count()
    answered = qs.exclude(student_response='').exclude(student_response__isnull=True).count()
    unanswered = max(0, total_qs - answered)

    # عدد الامتحانات المكتملة
    exams = TestSession.objects.filter(student=student, completed=True).count()

    return {
        'exams': exams,
        'correct': correct,
        'wrong': wrong,
        'unanswered': unanswered,
    }

@login_required
def stats(request):
    student = get_object_or_404(Student, user=request.user)
    data = _user_stats(student)
    return render(request, 'core/stats.html', {
        'student': student,
        'stats': data,
        'hide_footer': False,
    })


@login_required
def quarter_pages_api(request, qid: int):
    qs = (Ayah.objects
          .filter(quarter_id=qid, page__isnull=False)
          .values_list('page__number', flat=True)
          .distinct())
    pages = sorted(set(p for p in qs if p is not None))
    pmin = pages[0] if pages else None
    items = []
    for p in pages:
        items.append({
            "page_number": p,
            "index_in_quarter": (p - pmin + 1) if pmin else None
        })
    return JsonResponse({"pages": items})

@login_required
def page_ayat_api(request, pno: int):
    ay = (Ayah.objects
          .filter(page__number=pno)
          .order_by('surah','number')
          .values('id','surah','number','text','quarter_id'))
    data = [{
        "id": a["id"],
        "vk": f"{a['surah']}:{a['number']}",
        "text": a["text"],
        "quarter_id": a["quarter_id"],
    } for a in ay]
    return JsonResponse({"page": pno, "ayat": data})

@login_required
def quarter_pages_view(request, qid: int):
    pg_nums = (Ayah.objects
               .filter(quarter_id=qid, page__isnull=False)
               .values_list('page__number', flat=True))
    pg_nums = sorted(set(pg for pg in pg_nums if pg is not None))
    pages = Page.objects.filter(number__in=pg_nums).order_by('number')
    return render(request, 'core/quarter_pages.html', {
        'qid': qid,
        'pages': pages,
        'hide_footer': True,
    })

def page_svg(request, pno: int):
    candidates = [f"{pno}.svg", f"{pno:02d}.svg", f"{pno:03d}.svg"]
    base = os.path.join(settings.MEDIA_ROOT, 'pages')
    for fname in candidates:
        path = os.path.join(base, fname)
        if os.path.exists(path) and os.path.getsize(path) > 0:
            return FileResponse(open(path, 'rb'), content_type='image/svg+xml')
    raise Http404("Page SVG not found")


# =========================
# Similar on pages: steps B/C
# =========================
# === pages_quarter_pick (استبدال الدالة) ===
@login_required
def pages_quarter_pick(request, qid: int):
    sid = request.session.get('student_id')
    student = get_object_or_404(Student, id=sid)

    qobj = get_object_or_404(Quarter, id=qid)
    juz_no_for_q = qobj.juz.number

    question, flow = _current_question_and_flow(request)
    feedback = None
    delta = None

    if question:
        expected = int((request.session.get('pages_flow') or {}).get('current', 1))
        occ_ids = question.get('occurrence_ayah_ids', []) or []
        ay_quarters = list(
            Ayah.objects.filter(id__in=occ_ids)
                .order_by('surah','number')
                .values_list('id','quarter_id')
        )
        idx_to_qid = {i: q for i, (_, q) in enumerate(ay_quarters, start=1)}
        expected_qid = idx_to_qid.get(expected)

        if expected_qid == qid:
            request.session['score'] = max(0, int(request.session.get('score', 0)) + 1)
            delta = +1
            feedback = _feedback('success', f"تمام! اخترت الربع الصحيح للموضع {ar_ordinal(expected)}. +1")
        else:
            picked_index = next((i for i, q in idx_to_qid.items() if q == qid), None)
            if picked_index:
                flow['current'] = picked_index
                request.session['pages_flow'] = flow
                feedback = _feedback('warning', f"الربع المختار يخص الموضع {ar_ordinal(picked_index)} وليس {ar_ordinal(expected)}. سنكمل على هذا الموضع.")
            else:
                # مفيش أي موضع في هذا الربع → -1 وابقَ في اختيار ربع نفس الجزء
                request.session['score'] = max(0, int(request.session.get('score', 0)) - 1)
                delta = -1
                quarters = Quarter.objects.filter(juz__number=juz_no_for_q).order_by('index_in_juz')
                ctx = {
                    'student': student,
                    'juz_no': juz_no_for_q,
                    'quarters': quarters,
                    'hide_footer': True,
                }
                fb = _feedback('error', "لا يوجد أي موضع في هذا الربع. −1")
                return render(request, 'core/pages_choose_quarter.html', _ctx_common(request, ctx, fb, delta))

    # بعد التقييم → اعرض صفحات الربع (أو كمل الطبيعي)
    pg_nums = (Ayah.objects
               .filter(quarter_id=qid, page__isnull=False)
               .values_list('page__number', flat=True))
    pg_nums = sorted(set(pg for pg in pg_nums if pg is not None))
    pages = Page.objects.filter(number__in=pg_nums).order_by('number')

    ctx = {
        'qid': qid,
        'pages': pages,
        'hide_footer': True,
    }
    return render(request, 'core/quarter_pages.html', _ctx_common(request, ctx, feedback, delta))



@login_required
@require_POST
def api_pages_select_first(request):
    sid = request.session.get('student_id')
    get_object_or_404(Student, id=sid)

    try:
        ayah_id = int(request.POST.get('ayah_id', '0'))
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'ayah_id_invalid'}, status=400)

    if not Ayah.objects.filter(id=ayah_id).exists():
        return JsonResponse({'ok': False, 'error': 'ayah_not_found'}, status=404)

    # خزّن اختيار أول آية لهذا السؤال الجاري
    flow = request.session.get('pages_flow', {}) or {}
    flow['first_ayah_id'] = ayah_id
    request.session['pages_flow'] = flow

    return JsonResponse({'ok': True, 'next': 'pick_page_position'})


@login_required
def pages_quarter_viewer(request, qid: int):
    sid = request.session.get('student_id')
    student = get_object_or_404(Student, id=sid)

    pg_nums = (Ayah.objects
               .filter(quarter_id=qid, page__isnull=False)
               .values_list('page__number', flat=True))
    pages = sorted(set(p for p in pg_nums if p is not None))
    if not pages:
        # بدل الرسالة، نرجّع لاختيار الجزء/الربع بدون توست:
        quarters = Quarter.objects.filter(id=qid).select_related('juz')
        juz_no = quarters[0].juz.number if quarters else None
        if juz_no:
            ctx = {
                'student': student,
                'juz_no': juz_no,
                'quarters': Quarter.objects.filter(juz__number=juz_no).order_by('index_in_juz'),
                'hide_footer': True,
            }
            fb = _feedback('error', "لا توجد صفحات لهذا الربع.")
            return render(request, 'core/pages_choose_quarter.html', _ctx_common(request, ctx, fb, None))
        return redirect('core:pages_choose_juz')

    spreads = []
    i = 0
    while i < len(pages):
        left = pages[i]
        right = pages[i+1] if i+1 < len(pages) else None
        spreads.append((left, right))
        i += 2

    ctx = {
        'qid': qid,
        'spreads': spreads,
        'first_pair': spreads[0],
        'hide_footer': True,
    }
    return render(request, 'core/quarter_viewer.html', _ctx_common(request, ctx))


# === pages_choose_juz (استبدل دالتك بنفس الاسم) ===
@login_required
def pages_choose_juz(request):
    sid = request.session.get('student_id')
    student = get_object_or_404(Student, id=sid)

    allowed_juz_numbers = _allowed_juz_numbers_for_scope(request)
    context = {
        'student': student,
        'juz_numbers': allowed_juz_numbers,
        'had_scope': bool(request.session.get('selected_quarters') or request.session.get('selected_juz')),
        'hide_footer': True,
    }
    if not allowed_juz_numbers:
        reason = []
        if request.session.get('selected_quarters') or request.session.get('selected_juz'):
            reason.append("النطاق الذي اخترته لا يحتوي على أرباع بها صفحات.")
        else:
            reason.append("لا توجد صفحات مرتبطة بالأرباع حتى الآن.")
        context['no_juz_reason'] = " ".join(reason)

    return render(request, 'core/pages_choose_juz.html', _ctx_common(request, context))


# === pages_choose_quarter (استبدال الدالة) ===
@login_required
def pages_choose_quarter(request, juz_no: int):
    sid = request.session.get('student_id')
    student = get_object_or_404(Student, id=sid)

    # جهّز التقييم على الموضع المتوقع
    question, flow = _current_question_and_flow(request)
    feedback = None
    delta = None

    # quarters لهذا الجزء
    quarters = Quarter.objects.filter(juz__number=juz_no).order_by('index_in_juz')

    if question:
        expected = int((request.session.get('pages_flow') or {}).get('current', 1))
        occ_ids = question.get('occurrence_ayah_ids', []) or []
        ay_juzs = list(
            Ayah.objects.filter(id__in=occ_ids)
                .order_by('surah','number')
                .values_list('id','quarter__juz__number')
        )
        idx_to_juz = {i: j for i, (_, j) in enumerate(ay_juzs, start=1)}
        expected_juz = idx_to_juz.get(expected)

        if expected_juz is not None:
            if juz_no == expected_juz:
                # صح → +1
                request.session['score'] = max(0, int(request.session.get('score', 0)) + 1)
                delta = +1
                feedback = _feedback('success', f"تمام! اخترت الجزء الصحيح للموضع {ar_ordinal(expected)}. +1")
            else:
                # هل يخص موضعًا آخر؟
                picked_index = next((i for i, j in idx_to_juz.items() if j == juz_no), None)
                if picked_index:
                    flow['current'] = picked_index
                    request.session['pages_flow'] = flow
                    feedback = _feedback('warning', f"الجزء المختار يخص الموضع {ar_ordinal(picked_index)} وليس {ar_ordinal(expected)}. سنكمل على هذا الموضع.")
                else:
                    # لا يوجد أي موضع في هذا الجزء → -1 وابقَ في صفحة اختيار الجزء
                    request.session['score'] = max(0, int(request.session.get('score', 0)) - 1)
                    delta = -1
                    fb = _feedback('error', "لا يوجد أي موضع في هذا الجزء. −1")
                    allowed_juz_numbers = _allowed_juz_numbers_for_scope(request)
                    ctx = {
                        'student': student,
                        'juz_numbers': allowed_juz_numbers,
                        'had_scope': bool(request.session.get('selected_quarters') or request.session.get('selected_juz')),
                        'hide_footer': True,
                    }
                    return render(request, 'core/pages_choose_juz.html', _ctx_common(request, ctx, fb, delta))

    ctx = {
        'student': student,
        'juz_no': juz_no,
        'quarters': quarters,
        'hide_footer': True,
    }
    return render(request, 'core/pages_choose_quarter.html', _ctx_common(request, ctx, feedback, delta))


# ===== FILE: manage.py =====
#!/usr/bin/env python
"""
This file acts as the command‑line utility for administrative tasks.
It provides a minimal stub for Django's `manage.py`. Since the
full Django package may not be available in this environment,
this script illustrates the typical entry point without executing
framework‑specific code. When run in a proper Django environment,
it will delegate commands to `django.core.management`.
"""
import os
import sys


def main() -> None:
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quran_helper.settings')
    try:
        from django.core.management import execute_from_command_line  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "Django does not seem to be installed. This script is a placeholder."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()


# ===== FILE: quran_helper/__init__.py =====
"""Package initializer for the core project."""

# ===== FILE: quran_helper/settings.py =====
from pathlib import Path
import os

# في أي مكان فوق نهاية الملف
VERSION_LABEL = "Mutawatir 1.0 Alpha"


# =========================
# Paths & Core
# =========================
BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-secret-change-me")
DEBUG = True  # في الإنتاج خليها False

ALLOWED_HOSTS = ["essa.pythonanywhere.com"]

# =========================
# Applications
# =========================
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
]

# =========================
# Middleware
# =========================
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # لو بتخدم استاتيك من Django
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "quran_helper.urls"

# =========================
# Templates
# =========================
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "core.context_processors.inject_student",
                "core.context_processors.inject_version",  # ← أضف السطر ده
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "quran_helper.wsgi.application"

# =========================
# Database (SQLite)
# =========================
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# =========================
# Password validation
# =========================
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
    {"NAME": "core.validators.AlphaNumericPasswordValidator"},  # جديد
]

# =========================
# Internationalization
# =========================
LANGUAGE_CODE = "ar"
TIME_ZONE = "Africa/Cairo"
USE_I18N = True
USE_L10N = True
USE_TZ = True

# =========================
# Static files
# =========================
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

# ملاحظة: في Django 5 الأفضل استخدام STORAGES، لكن هنسيب الإعداد
# زي اللي عندك كما ظهر في الدامب، مع تخزين WhiteNoise للـ manifest
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# لو عندك STORAGES زي اللي في الدامب وعايز تسيبه:
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


# =========================
# Media (user uploads)
# =========================
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# =========================
# Auth redirects
# =========================
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/home/"
LOGOUT_REDIRECT_URL = "/login/"

# =========================
# Security / HTTPS behind proxy (PythonAnywhere)
# =========================
# مهم جدًا على PythonAnywhere علشان Django يفهم إن الطلب HTTPS خلف البروكسي
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# اعتمد على Force HTTPS من لوحة PythonAnywhere لتفادي حلقات التحويل
SECURE_SSL_REDIRECT = False

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

CSRF_TRUSTED_ORIGINS = [
    "https://essa.pythonanywhere.com",
]

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# =========================
# Messages / Misc
# =========================
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# (اختياري) إعدادات WhiteNoise إضافية
# WHITENOISE_MAX_AGE = 31536000


# ===== FILE: quran_helper/urls.py =====
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),

    # يضيف view باسم set_language على /i18n/setlang/
    path("i18n/", include("django.conf.urls.i18n")),

    # كل مسارات التطبيق
    path("", include(("core.urls", "core"), namespace="core")),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# ===== FILE: quran_helper/wsgi.py =====
"""
WSGI config for the Quran memorization assistant.

This file exposes the WSGI callable as a module-level variable named
``application``. It is used by Django's development server and any
WSGI-compatible servers.
"""
import os

from django.core.wsgi import get_wsgi_application  # type: ignore

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quran_helper.settings')

application = get_wsgi_application()
