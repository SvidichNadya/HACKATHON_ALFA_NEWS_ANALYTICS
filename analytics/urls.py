from django.urls import path
from . import views
urlpatterns = [path("", views.dashboard, name="dashboard"), path("api/overview/", views.overview_api, name="overview_api"), path("api/signals/", views.signals_api, name="signals_api")]
