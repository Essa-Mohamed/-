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
