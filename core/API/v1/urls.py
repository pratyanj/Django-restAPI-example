from django.urls import include, path
from rest_framework.routers import DefaultRouter
from base.views import *

router = DefaultRouter()
router.register('person_class', PersonViewSet, basename='person')
router.register('gender', GenderViewSet , basename="gender")

urlpatterns = [
    path('', include(router.urls)),
    path('index/', index),
    # path('person/', person_data),
    path('login/', login),
    path('person_view/', Person_view.as_view()),
]