from django.urls import path

from . import views

app_name = "eos_spy_network"

urlpatterns = [
    path("", views.index, name="index"),
    path("hostiles/", views.hostiles, name="hostiles"),
    path("settings/", views.settings, name="settings"),
]
