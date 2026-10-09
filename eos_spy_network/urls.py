from django.urls import path

from . import views

app_name = "eos_spy_network"

urlpatterns = [
    path("", views.index, name="index"),
    path("corporations/", views.corporations, name="corporations"),
    path("corporations/<int:corporation_id>/", views.corporation, name="corporation"),
    path("settings/", views.settings, name="settings"),
]
