from django.urls import path

from . import views
from . import pwa

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("manifest.webmanifest", pwa.manifest, name="manifest"),
    path("service-worker.js", pwa.service_worker, name="service_worker"),
    path("offline/", pwa.offline, name="offline"),
]
