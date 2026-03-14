from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from django.conf import settings
from django.conf.urls.static import static

# Each HTML page is served by Django directly from /templates/
# This means NO CORS issues — frontend and backend are on the same server (port 8000)

urlpatterns = [
    # ── Django admin ──────────────────────────────────────
    path('admin/', admin.site.urls),

    # ── REST API ──────────────────────────────────────────
    path('api/auth/',          include('authentication.urls')),
    path('api/accommodation/', include('accommodation.urls')),
    path('api/dining/',        include('dining.urls')),
    path('api/security/',      include('security.urls')),

    # ── Frontend pages (served by Django) ─────────────────
    path('',            TemplateView.as_view(template_name='mtc_login.html'),          name='login'),
    path('login/',      TemplateView.as_view(template_name='mtc_login.html'),          name='login-page'),
    path('dashboard/accommodation/', TemplateView.as_view(template_name='mtc_accommodation.html'), name='accom'),
    path('dashboard/dining/',        TemplateView.as_view(template_name='mtc_dining.html'),        name='dining'),
    path('dashboard/security/',      TemplateView.as_view(template_name='mtc_security.html'),      name='security'),
    path('portal/',     TemplateView.as_view(template_name='mtc_student_portal.html'), name='portal'),
    path('scanner-test/', TemplateView.as_view(template_name='scanner_test.html'),        name='scanner-test'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

admin.site.site_header  = 'Mutare Teachers College — Admin'
admin.site.site_title   = 'MTC Admin'
admin.site.index_title  = 'Campus Management System'