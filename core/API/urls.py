from base.views import index,person_data,login
from django.urls import path

urlpatterns = [
    path('index/', index ),
    path('person/', person_data),
    path('login/', login ),
]
