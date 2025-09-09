from django.core.management.base import BaseCommand
from pathlib import Path

class Command(BaseCommand):
    help = "جمع الملفات الرئيسية فقط داخل ملف واحد (افتراضيًا: all code.txt)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--output", "-o",
            default="all code.txt",
            help="اسم الملف أو المسار النهائي (افتراضي: all code.txt). يقبل مسارًا مطلقًا أو نسبيًا."
        )

    def handle(self, *args, **options):
        # جذر المشروع (…/core/management/commands -> …/…/..)
        ROOT = Path(__file__).resolve().parents[3]

        # تحديد ملف الإخراج (يدعم المطلق/النسبي)
        out_opt = Path(options["output"])
        OUT = out_opt if out_opt.is_absolute() else (ROOT / out_opt)
        OUT.parent.mkdir(parents=True, exist_ok=True)

        # الملفات/الأنماط المطلوبة
        GLOBS = [
            "core/models.py",
            "core/views.py",
            "core/forms.py",
            "core/urls.py",
            "core/admin.py",
            "core/templates/core/**/*.html",
            "core/management/commands/*.py",
        ]
        IGNORE_PARTS = {
            "__pycache__", ".venv", "venv", ".git",
            "node_modules", "static", "media", "migrations"
        }

        def wanted(p: Path) -> bool:
            return all(part not in IGNORE_PARTS for part in p.parts)

        seen, files = set(), []
        for pattern in GLOBS:
            for p in ROOT.glob(pattern):
                if p.is_file() and wanted(p):
                    rp = p.relative_to(ROOT)
                    if rp not in seen:
                        seen.add(rp)
                        files.append(rp)

        files.sort(key=lambda x: str(x).lower())

        def read_text_safe(p: Path) -> str:
            try:
                return p.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                return p.read_text(encoding="latin-1")

        with OUT.open("w", encoding="utf-8") as f:
            for rp in files:
                content = read_text_safe(ROOT / rp)
                f.write(f"# ===== FILE: {rp.as_posix()} =====\n")
                f.write(content)
                if not content.endswith("\n"):
                    f.write("\n")
                f.write("\n")

        self.stdout.write(self.style.SUCCESS(
            f"تم تحديث {OUT} ({len(files)} ملف)."
        ))
