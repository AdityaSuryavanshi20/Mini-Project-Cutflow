from django.urls import path
from . import views
urlpatterns = [
    path('systems/', views.system_list, name='system_list'),
    path('profiles/', views.profile_list, name='profile_list'),
    path('glass/', views.glass_list, name='glass_list'),
    path('hardware/', views.hardware_list, name='hardware_list'),
]
