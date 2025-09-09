# دليل النشر الآمن - مساعد القرآن

## 🚨 خطوات النشر الآمنة

### 1. إعداد متغيرات البيئة

#### أ) إنشاء ملف .env:
```bash
# انسخ ملف env.example إلى .env
cp env.example .env
```

#### ب) ملء ملف .env بالقيم الآمنة:
```bash
# مفتاح Django السري - استخدم مفتاح قوي وعشوائي
DJANGO_SECRET_KEY=your-super-secret-key-here-change-this

# وضع الإنتاج
DEBUG=False

# النطاقات المسموحة
ALLOWED_HOSTS=essa.pythonanywhere.com
```

#### ج) إنشاء مفتاح سري قوي:
```python
# في Python shell
from django.core.management.utils import get_random_secret_key
print(get_random_secret_key())
```

### 2. تثبيت المتطلبات

```bash
pip install -r requirements.txt
```

### 3. إعداد قاعدة البيانات

```bash
python manage.py migrate
python manage.py collectstatic --noinput
```

### 4. إنشاء مستخدم مدير

```bash
python manage.py createsuperuser
```

### 5. اختبار الإعدادات

```bash
python manage.py check --deploy
```

## 🔒 إعدادات الأمان المطبقة

### ✅ تم إصلاحها:
- [x] DEBUG = False في الإنتاج
- [x] SECRET_KEY آمن من متغيرات البيئة
- [x] ALLOWED_HOSTS محدود للنطاق المطلوب
- [x] إعدادات HTTPS محسنة
- [x] حماية الكوكيز محسنة
- [x] Security headers إضافية
- [x] Logging للأمان
- [x] حماية الملفات الحساسة

### 🛡️ إعدادات الأمان المضافة:
- `SECURE_BROWSER_XSS_FILTER = True`
- `SECURE_HSTS_SECONDS = 31536000`
- `SECURE_HSTS_INCLUDE_SUBDOMAINS = True`
- `SECURE_HSTS_PRELOAD = True`
- `SESSION_COOKIE_HTTPONLY = True`
- `CSRF_COOKIE_HTTPONLY = True`
- `SESSION_COOKIE_SAMESITE = 'Strict'`
- `CSRF_COOKIE_SAMESITE = 'Strict'`

## 📋 فحص ما قبل النشر

### 1. تأكد من:
- [ ] ملف .env موجود ومحمي
- [ ] DEBUG = False
- [ ] SECRET_KEY قوي وآمن
- [ ] ALLOWED_HOSTS محدود
- [ ] قاعدة البيانات محدثة
- [ ] الملفات الثابتة مجمعة

### 2. اختبار الأمان:
```bash
# فحص إعدادات Django
python manage.py check --deploy

# فحص الأمان
python manage.py check --tag security
```

## 🚀 النشر على PythonAnywhere

### 1. رفع الملفات:
- رفع جميع الملفات عدا .env
- إنشاء ملف .env على الخادم

### 2. إعداد متغيرات البيئة على PythonAnywhere:
- في لوحة التحكم: Web → Environment variables
- إضافة: `DJANGO_SECRET_KEY=your-secret-key`
- إضافة: `DEBUG=False`
- إضافة: `ALLOWED_HOSTS=essa.pythonanywhere.com`

### 3. تشغيل الأوامر:
```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
```

## ⚠️ تحذيرات مهمة

1. **لا تشارك ملف .env أبداً**
2. **تأكد من حماية ملف .env على الخادم**
3. **استخدم HTTPS دائماً**
4. **راقب ملفات السجل بانتظام**
5. **حدث Django والمكتبات بانتظام**

## 📞 في حالة المشاكل

### مشاكل شائعة:
1. **خطأ SECRET_KEY**: تأكد من وجود متغير البيئة
2. **خطأ ALLOWED_HOSTS**: تأكد من النطاق الصحيح
3. **خطأ DEBUG**: تأكد من DEBUG=False

### ملفات السجل:
- `logs/django.log` - سجل Django العام
- `logs/security.log` - سجل الأمان

## ✅ الموقع جاهز للنشر!

بعد تطبيق هذه الخطوات، سيكون موقعك آمناً وجاهزاً للنشر الأولي.
