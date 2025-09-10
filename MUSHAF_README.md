# المصحف التفاعلي - Quran Interactive Mushaf

## نظرة عامة
نظام مصحف تفاعلي يستخدم صفحات SVG جاهزة مع بيانات KFGQPC وطبقة تفاعل ذكية فوق الـSVG.

## المكونات الرئيسية

### 1. البيانات
- **KFGQPC Data**: بيانات القرآن الكريم مع مواقع الآيات في الصفحات
- **SVG Pages**: صفحات المصحف بصيغة SVG (صفحات 001-604)
- **HafsSmart Font**: خط عثماني للقياس الدقيق

### 2. النماذج (Models)
```python
class Ayah(models.Model):
    surah = models.PositiveSmallIntegerField()
    number = models.PositiveSmallIntegerField()
    text = models.TextField()
    page = models.ForeignKey(Page, on_delete=models.SET_NULL, null=True, blank=True)
    line = models.PositiveSmallIntegerField(null=True, blank=True)
    text_imlaei = models.TextField(blank=True)  # النص الإملائي
    text_uthmani = models.TextField(blank=True)  # النص العثماني
```

### 3. API Endpoints
- `GET /quran/api/page/<num>/meta/` - بيانات آيات صفحة معينة
- `GET /quran/mushaf/page/<num>/` - عرض صفحة المصحف
- `GET /quran/mushaf/demo/` - صفحة تجريبية تفاعلية

### 4. الملفات الرئيسية
```
quran/
├── views.py          # Views للصفحات وAPI
├── urls.py           # URLs للتطبيق
└── models.py         # (في core/models.py)

templates/
├── mushaf_page.html  # قالب صفحة المصحف
└── mushaf_demo.html  # قالب الصفحة التجريبية

static/
├── css/mushaf.css    # تنسيقات CSS
└── fonts/HafsSmart_08.ttf  # خط عثماني

assets/mushaf/svg/    # صفحات SVG
├── page001.svg
├── page002.svg
└── ...
```

## كيفية الاستخدام

### 1. تشغيل النظام
```bash
python manage.py runserver
```

### 2. الوصول للصفحات
- **صفحة تجريبية**: http://127.0.0.1:8000/quran/mushaf/demo/
- **صفحة محددة**: http://127.0.0.1:8000/quran/mushaf/page/3/
- **API**: http://127.0.0.1:8000/quran/api/page/3/meta/

### 3. الميزات التفاعلية
- **نقر على الآيات**: اضغط على أي آية لرؤية معلوماتها
- **تأثيرات بصرية**: إطار أخضر عند التمرير فوق الآيات
- **قياس دقيق**: استخدام Canvas 2D لقياس عرض النص بالخط العثماني
- **تصفح سريع**: أزرار للانتقال بين الصفحات

## التقنيات المستخدمة

### Frontend
- **HTML5 + CSS3**: تخطيط وتنسيق الصفحات
- **JavaScript (ES6+)**: التفاعل والقياس
- **SVG**: عرض صفحات المصحف
- **Canvas 2D**: قياس عرض النص

### Backend
- **Django**: إطار العمل الرئيسي
- **SQLite**: قاعدة البيانات
- **REST API**: توفير البيانات

### الخطوط والتصميم
- **HafsSmart_08.ttf**: خط عثماني للقياس
- **RTL Support**: دعم الكتابة من اليمين لليسار
- **Responsive Design**: تصميم متجاوب

## إعدادات الضبط

### 1. تطابق النص مع SVG
```javascript
const FONT = (vbW * 0.018);        // حجم الخط
const topPad = vbH * 0.065;         // المسافة العلوية
const rightMargin = minX + vbW * 0.06;  // الهامش الأيمن
```

### 2. هندسة الصفحة
- **عدد الأسطر**: 15 سطر
- **viewBox**: 0 0 1200 1800 (قابل للتعديل)
- **نسبة الخط**: 1.8% من عرض viewBox

## استيراد البيانات

### 1. تشغيل سكريبت الاستيراد
```bash
python import_kfgqpc_data.py
```

### 2. البيانات المستوردة
- **6236 آية** من ملف JSON
- **604 صفحة** في قاعدة البيانات
- **بيانات السطور** ومواقع الآيات

## التطوير المستقبلي

### 1. ميزات مخططة
- [ ] دعم صفحات SVG حقيقية
- [ ] تحسين دقة القياس
- [ ] إضافة تفسير الآيات
- [ ] دعم البحث في النص
- [ ] حفظ التقدم

### 2. تحسينات تقنية
- [ ] تحسين الأداء
- [ ] دعم PWA
- [ ] إضافة اختبارات
- [ ] تحسين الأمان

## الدعم والمساهمة

للمساهمة في المشروع أو الإبلاغ عن مشاكل، يرجى:
1. فتح issue جديد
2. وصف المشكلة أو الميزة المطلوبة
3. إرفاق لقطات شاشة إن أمكن

## الترخيص

هذا المشروع مفتوح المصدر ومتاح للاستخدام التعليمي والديني.

