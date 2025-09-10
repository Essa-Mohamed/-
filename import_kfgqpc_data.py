#!/usr/bin/env python
"""
Script لاستيراد بيانات KFGQPC إلى قاعدة البيانات
"""
import json
import os
import sys
import django

# إعداد Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quran_helper.settings')
django.setup()

from core.models import Ayah, Page

def import_kfgqpc_data():
    """استيراد بيانات KFGQPC من ملف JSON"""
    
    # قراءة ملف البيانات
    json_file = 'elec_mushaf/kfgqpc_hafs_smart_data/hafs_smart_v8.json'
    
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"❌ ملف البيانات غير موجود: {json_file}")
        return
    except json.JSONDecodeError as e:
        print(f"❌ خطأ في قراءة ملف JSON: {e}")
        return
    
    print(f"📖 تم قراءة {len(data)} آية من ملف البيانات")
    
    # إنشاء صفحات إذا لم تكن موجودة
    pages_created = set()
    
    # استيراد الآيات
    imported_count = 0
    updated_count = 0
    
    for item in data:
        surah = item['sura_no']
        ayah_num = item['aya_no']
        page_num = item['page']
        line = item['line_start']  # نستخدم line_start
        text_imlaei = item['aya_text_emlaey']
        text_uthmani = item['aya_text']
        
        # إنشاء الصفحة إذا لم تكن موجودة
        if page_num not in pages_created:
            page, created = Page.objects.get_or_create(number=page_num)
            if created:
                pages_created.add(page_num)
                print(f"✅ تم إنشاء صفحة {page_num}")
        
        # إنشاء أو تحديث الآية
        ayah, created = Ayah.objects.get_or_create(
            surah=surah,
            number=ayah_num,
            defaults={
                'text': text_uthmani,  # النص العثماني كقيمة افتراضية
                'text_imlaei': text_imlaei,
                'text_uthmani': text_uthmani,
                'line': line,
                'page': Page.objects.get(number=page_num)
            }
        )
        
        if created:
            imported_count += 1
        else:
            # تحديث البيانات الموجودة
            ayah.text_imlaei = text_imlaei
            ayah.text_uthmani = text_uthmani
            ayah.line = line
            ayah.page = Page.objects.get(number=page_num)
            ayah.save()
            updated_count += 1
    
    print(f"✅ تم استيراد {imported_count} آية جديدة")
    print(f"🔄 تم تحديث {updated_count} آية موجودة")
    print(f"📄 إجمالي الصفحات: {len(pages_created)}")

if __name__ == '__main__':
    import_kfgqpc_data()

