from django.urls import path

from . import views

app_name = "eos_spy_network"

urlpatterns = [
    path("", views.index, name="index"),
    path("corporations/", views.corporations, name="corporations"),
    path("corporations/<int:corporation_id>/", views.corporation, name="corporation"),
    path("network/", views.network, name="network"),
    path("network/<int:corporation_id>/", views.network_corporation, name="network_corporation"),
    path("rebuild/", views.rebuild, name="rebuild"),
    path("rebuild/progress/", views.rebuild_progress, name="rebuild_progress"),
    path("settings/", views.settings, name="settings"),
]
