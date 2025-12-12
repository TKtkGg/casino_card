from . import views
from django.urls import path

urlpatterns = [
    path('', views.top, name='top'),
    path('bacarrat/', views.bacarrat, name='bacarrat'),
]