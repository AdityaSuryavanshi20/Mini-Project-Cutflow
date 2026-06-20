from django.urls import path
from . import views

urlpatterns = [
    path('', views.job_list, name='job_list'),
    path('project/<int:project_pk>/create/', views.job_create, name='job_create'),
    path('<int:pk>/', views.job_detail, name='job_detail'),
    path('<int:pk>/generate/', views.generate_items, name='generate_production_items'),
    path('<int:pk>/optimize/', views.run_optimization_view, name='run_optimization'),
    path('<int:pk>/cutting-list.pdf', views.cutting_list_pdf, name='cutting_list_pdf'),
    path('<int:pk>/optimization/', views.optimization_summary, name='optimization_summary'),
    path('<int:pk>/hardware/', views.hardware_summary, name='hardware_summary'),
    path('<int:pk>/glass/', views.glass_schedule, name='glass_schedule'),
    path('<int:pk>/status/', views.update_job_status, name='update_job_status'),
]
