from django.conf import settings
from django.db import models


class Jugada(models.Model):
    """Una jugada del editor guardada en la cuenta de su autor (el JSON del editor: fases, piezas y flechas)."""
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='jugadas')
    nombre = models.CharField(max_length=80)
    datos = models.JSONField()
    actualizada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-actualizada']
        constraints = [models.UniqueConstraint(fields=['usuario', 'nombre'], name='jugada_unica_por_usuario_y_nombre')]

    def __str__(self):
        return f'{self.nombre} ({self.usuario})'


class JugadaBiblioteca(models.Model):
    """Cambio del administrador sobre una jugada de la biblioteca (jugadas.json): sustituye a la original con ese id o la añade.
    Vive en la base de datos (volumen /data), así que sobrevive a los despliegues; borrar la fila restaura la original."""
    id_jugada = models.CharField(max_length=20, unique=True)
    datos = models.JSONField()
    actualizada = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.id_jugada
