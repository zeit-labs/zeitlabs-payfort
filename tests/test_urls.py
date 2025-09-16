"""URLs configuration for testing purposes."""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    # Admin URLs
    path('admin/', admin.site.urls),

    # Plugin urls
    path('', include('payfort.urls')),
]
