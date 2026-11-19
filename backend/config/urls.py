from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("core.urls")),
    path("api/", include("voyages.urls")),
]

# En dev, Django sert le cache des rendus (static() ne fait rien si DEBUG est faux).
# En prod, un nginx dédié s'en chargera (voir docs/decisions.md).
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
