from django.urls import path

from .views import PhotosDuVoyageView

urlpatterns = [
    path("voyages/<slug:slug>/photos/", PhotosDuVoyageView.as_view(), name="photos-du-voyage"),
]
