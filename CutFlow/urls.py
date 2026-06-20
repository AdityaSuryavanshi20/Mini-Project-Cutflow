from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('', include('core.urls')),
    path('catalog/', include('catalog.urls')),
    path('projects/', include('projects.urls')),
    path('quotations/', include('quotations.urls')),
    path('production/', include('production.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
