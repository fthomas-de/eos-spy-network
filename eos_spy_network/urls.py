from django.urls import path

from . import views

app_name = "eos_spy_network"

urlpatterns = [
    path("", views.index, name="index"),
    path("corporations/", views.corporations, name="corporations"),
    path("corporations/<int:corporation_id>/", views.corporation, name="corporation"),
    path("network/", views.network, name="network"),
    path("network/search/", views.network_search, name="network_search"),
    path("network/<int:corporation_id>/", views.network_corporation, name="network_corporation"),
    path("contracts/<int:character_id>/<int:counterpart_id>/", views.contracts, name="contracts"),
    path("network/contracts/<int:character_id>/<int:counterpart_id>/", views.network_contracts, name="network_contracts"),
    path(
        "network/contract-payments/<int:character_id>/<int:counterpart_id>/",
        views.network_payment_contracts,
        name="network_payment_contracts",
    ),
    path("capital-contract/<int:contract_id>/", views.capital_contract, name="capital_contract"),
    path("kills/note/", views.kill_note, name="kill_note"),
    path("kills/day/", views.kill_day_note, name="kill_day_note"),
    path("findings/note/", views.finding_note, name="finding_note"),
    path("network/ignore/", views.ignore_counterpart, name="ignore_counterpart"),
    path("rebuild/", views.rebuild, name="rebuild"),
    path("rebuild/progress/", views.rebuild_progress, name="rebuild_progress"),
    path("settings/", views.settings, name="settings"),
    path("statistics/", views.statistics, name="statistics"),
    path("log/", views.log, name="log"),
]
