#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re
import sys

def extraer_ejercicios(texto):
    # Buscar bloques que empiezan con "o " o con títulos en mayúsculas seguidos de descripción
    # Patrón: o ... hasta siguiente "o" o cambio de sección
    patron = r'(?:^|\n)(o .+?)(?=\n\s*o\s|\n[A-ZÁÉÍÓÚ][A-ZÁÉÍÓÚ\s]+\n|$)'
    matches = re.findall(patron, texto, re.DOTALL)
    ejercicios = []
    for m in matches:
        # Limpiar saltos de línea internos pero mantener legibilidad
        limpio = ' '.join(m.split())
        if len(limpio) > 15:
            ejercicios.append(limpio)
    return ejercicios

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python dividir_pdf.py archivo.txt")
        sys.exit(1)
    with open(sys.argv[1], 'r', encoding='utf-8') as f:
        contenido = f.read()
    ejercicios = extraer_ejercicios(contenido)
    for ej in ejercicios:
        print(ej)