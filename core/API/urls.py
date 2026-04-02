from django.urls import include, path

urlpatterns = [
    path('v1/', include('API.v1.urls')),
    path('v2/', include('API.v2.urls')),
]
