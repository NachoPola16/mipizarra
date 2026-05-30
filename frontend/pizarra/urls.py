from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('generar/', views.generar, name='generar'),
    path('reglamento/', views.reglamento, name='reglamento'),
    path('pdf/', views.descargar_pdf, name='pdf'),
    path('feedback/', views.guardar_feedback, name='feedback'),
    path('privacidad/', views.privacidad, name='privacidad'),
    path('aviso-legal/', views.aviso_legal, name='aviso_legal'),
]
