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
