"""Validación de las jugadas del editor que llegan al servidor: solo se guarda una forma conocida y acotada
(el JSON se pinta en el navegador con textContent, pero igualmente no se acepta nada raro)."""

ANCHO, ALTO = 500, 470
MAX_FASES, MAX_PIEZAS, MAX_FLECHAS, CURVA_MAX = 12, 30, 40, 0.8
TIPOS_PIEZA = ('A', 'D', 'B', 'C')
TIPOS_FLECHA = ('pase', 'bote', 'corte', 'bloqueo')
ETIQUETAS = ('num', 'letra')


def _num(v, minimo, maximo, decimales=1):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v or v in (float('inf'), float('-inf')):
        return None
    return round(max(minimo, min(maximo, float(v))), decimales)


def validar_jugada(datos):
    """Devuelve la jugada normalizada ({'fases': [...]}) o None si no es válida."""
    if not isinstance(datos, dict) or not isinstance(datos.get('fases'), list):
        return None
    if not 1 <= len(datos['fases']) <= MAX_FASES:
        return None
    fases = []
    for fase in datos['fases']:
        if not isinstance(fase, dict) or not isinstance(fase.get('piezas'), list) or len(fase['piezas']) > MAX_PIEZAS:
            return None
        piezas, ids = [], set()
        for p in fase['piezas']:
            if not isinstance(p, dict) or p.get('tipo') not in TIPOS_PIEZA:
                return None
            tipo = p['tipo']
            n = 0 if tipo == 'B' else _num(p.get('n'), 1, 9)
            x, y = _num(p.get('x'), 0, ANCHO), _num(p.get('y'), 0, ALTO)
            if x is None or y is None or n is None:
                return None
            n = int(n)
            pid = 'B' if tipo == 'B' else f'{tipo}{n}'
            if pid in ids:
                return None
            ids.add(pid)
            piezas.append({'id': pid, 'tipo': tipo, 'n': n, 'x': x, 'y': y})
        flechas = []
        for a in (fase.get('flechas') if isinstance(fase.get('flechas'), list) else [])[:MAX_FLECHAS]:
            if not isinstance(a, dict) or a.get('tipo') not in TIPOS_FLECHA or a.get('de') not in ids:
                continue
            f = {'tipo': a['tipo'], 'de': a['de']}
            if isinstance(a.get('aId'), str) and a['aId'] in ids:
                f['aId'] = a['aId']
            elif isinstance(a.get('a'), dict) and _num(a['a'].get('x'), 0, ANCHO) is not None and _num(a['a'].get('y'), 0, ALTO) is not None:
                f['a'] = {'x': _num(a['a']['x'], 0, ANCHO), 'y': _num(a['a']['y'], 0, ALTO)}
            else:
                continue
            curva = _num(a.get('curva'), -CURVA_MAX, CURVA_MAX, 2)
            if curva:
                f['curva'] = curva
            if a.get('sigue') is True and a['tipo'] != 'pase':
                f['sigue'] = True      # tramo encadenado con el anterior de la misma pieza
            flechas.append(f)
        fases.append({'piezas': piezas, 'flechas': flechas})
    etiquetas = datos.get('etiquetas')
    salida = {'etiquetas': etiquetas if etiquetas in ETIQUETAS else 'num', 'fases': fases}
    if datos.get('defensa') is True:
        salida['defensa'] = True       # jugada de defensa: la reproducción no acaba en tiro
    return salida
