from base.views import index,person_data,login,Person_view
from django.urls import path

urlpatterns = [
    path('index/', index ),
    path('person/', person_data),
    path('login/', login ),
    path('person_view/', Person_view.as_view()),
]
