from base.views import index,person_data
from django.urls import path

urlpatterns = [
    path('index/', index ),
    path('person/', person_data),
]
