from django.shortcuts import get_object_or_404
from rest_framework.generics import ListAPIView

from .models import Photo, Voyage
from .serializers import PhotoSerializer


class PhotosDuVoyageView(ListAPIView):
    """GET /api/voyages/<slug>/photos/ : photos visibles, dans l'ordre du voyage."""

    serializer_class = PhotoSerializer

    def get_queryset(self):
        voyage = get_object_or_404(Voyage, slug=self.kwargs["slug"])
        return (
            Photo.objects.filter(jour__voyage=voyage, visible=True)
            .select_related("jour")
            .prefetch_related("rendus")
        )
