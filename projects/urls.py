from django.urls import path
from . import views

urlpatterns = [
    path('customers/', views.customer_list, name='customer_list'),
    path('customers/new/', views.customer_create, name='customer_create'),
    path('customers/<int:pk>/', views.customer_detail, name='customer_detail'),
    path('', views.project_list, name='project_list'),
    path('new/', views.project_create, name='project_create'),
    path('<int:pk>/', views.project_detail, name='project_detail'),
    path('<int:project_pk>/measurements/add/', views.measurement_add, name='measurement_add'),
    path('measurements/<int:pk>/edit/', views.measurement_edit, name='measurement_edit'),
    path('measurements/<int:pk>/delete/', views.measurement_delete, name='measurement_delete'),
    path('<int:pk>/lock/', views.project_lock, name='project_lock'),
    path('<int:pk>/unlock/', views.project_unlock, name='project_unlock'),
]
