from django.urls import path
from . import views, cuentas

urlpatterns = [
    path('', views.index, name='index'),
    path('generar/', views.generar, name='generar'),
    path('reprompt/', views.reprompt_ejercicio, name='reprompt'),
    path('reglamento/', views.reglamento, name='reglamento'),
    path('pdf/', views.descargar_pdf, name='pdf'),
    path('feedback/', views.guardar_feedback, name='feedback'),
    path('jugadas/', cuentas.jugadas, name='jugadas'),
    path('jugadas/guardadas/', cuentas.guardadas, name='jugadas_guardadas'),
    path('jugadas/guardadas/<int:pk>/', cuentas.guardada, name='jugada_guardada'),
    path('cuenta/entrar/', cuentas.Entrar.as_view(), name='entrar'),
    path('cuenta/salir/', cuentas.salir, name='salir'),
    path('privacidad/', views.privacidad, name='privacidad'),
    path('aviso-legal/', views.aviso_legal, name='aviso_legal'),
]
