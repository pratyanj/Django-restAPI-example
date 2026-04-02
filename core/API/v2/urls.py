from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import PersonV2ViewSet, IndexV2View

router = DefaultRouter()
router.register('persons', PersonV2ViewSet, basename='person')

urlpatterns = [
    path('', include(router.urls)),
    path('index/', IndexV2View.as_view()),
]