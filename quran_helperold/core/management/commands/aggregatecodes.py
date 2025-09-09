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
