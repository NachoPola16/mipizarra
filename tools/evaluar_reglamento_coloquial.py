#!/usr/bin/env python3
"""Mide si el modo Reglamento recupera la norma cuando la pregunta no usa las palabras del reglamento.

Cada tema lleva varias formulaciones «de la calle» (cuartos en vez de periodos, niños en vez de jugadores,
benjamín sin tilde, «mini»...) y los términos que tiene que contener el contexto que llega al modelo. Se mide
sobre `recuperar_contexto_reglamento`, es decir, con la ampliación de consulta y los presupuestos de caracteres
reales: lo que no aparece aquí, el modelo no lo ve.

Los temas de FIBA y de la federación se prueban en el ámbito general y en el de Aragón (que también debe poder
responderlos); los de Aragón, solo en el suyo.

Se ejecuta dentro del contenedor de la API (necesita ChromaDB y Ollama):

  docker cp tools/evaluar_reglamento_coloquial.py mipizarra-api:/app/tools/   (si no está montado)
  docker exec mipizarra-api python /app/tools/evaluar_reglamento_coloquial.py
  docker exec mipizarra-api python /app/tools/evaluar_reglamento_coloquial.py --detalle
"""
import argparse
import sys
import unicodedata
from pathlib import Path

# en el repositorio los módulos están en api/; dentro del contenedor, en /app (junto a tools/)
sys.path[:0] = [str(Path(__file__).resolve().parent.parent), str(Path(__file__).resolve().parent.parent / "api")]

# (id, ámbitos a probar, términos: basta uno, [formulaciones])
GENERAL, AMBOS, ARAGON = ("general",), ("general", "aragon"), ("aragon",)
TEMAS = [
    ("ocho_segundos", AMBOS, ["8 segundos para avanzar"],
     ["cuanto tiempo hay para pasar del medio campo", "tiempo para cruzar el campo con la pelota",
      "cuantos segundos para subir la bola"]),
    ("veinticuatro", AMBOS, ["efectuar un tiro a canasta", "24 segundos (art. 29)"],
     ["cuanto tiempo tiene un equipo para tirar", "reloj de posesion", "cuanto dura la posesion de balon"]),
    ("tres_segundos", AMBOS, ["3 segundos consecutivos"],
     ["cuanto tiempo puedo estar en la pintura", "tiempo maximo en la zona", "cuantos segundos en la zona rival"]),
    ("cinco_faltas", AMBOS, ["5 faltas personales", "5 faltas de jugador", "5 faltas = exclusion"],
     ["cuantas faltas puede hacer un jugador", "con cuantas faltas se echa a un jugador",
      "a las cuantas faltas se sale del partido"]),
    ("faltas_equipo", AMBOS, ["5 faltas de equipo", "4 faltas de equipo"],
     ["cuando tiran tiros libres por las faltas del equipo", "bonus de faltas", "cuantas faltas de equipo para penalizar"]),
    ("disruptiva", AMBOS, ["falta disruptiva", "antideportiva desaparece"],
     ["que falta ha sustituido a la antideportiva", "falta nueva de este ano", "cuando pitan falta disruptiva"]),
    ("tecnica", AMBOS, ["categoria 1", "dos categorias"],
     ["que pasa si el entrenador protesta", "falta tecnica por protestar", "cuantas tecnicas para descalificar"]),
    ("pasos", AMBOS, ["paso 0", "desplazamiento ilegal"],
     ["cuantos pasos puedo dar con el balon", "que es el paso cero", "pasos despues de parar de botar"]),
    ("pantalla", AMBOS, ["inmovil", "pantalla (bloqueo) legal"],
     ["cuando es ilegal un bloqueo", "pantalla ilegal", "bloqueo ilegal porque se mueve el jugador"]),
    ("semicirculo", AMBOS, ["semicirculo de no-carga"],
     ["que es la zona de no carga", "carga debajo del aro", "puede el defensor hacer falta de carga bajo la canasta"]),
    ("goaltending", AMBOS, ["goaltending", "trayectoria descendente"],
     ["tocar el balon cuando baja hacia el aro", "que es interferencia", "tapon ilegal"]),
    ("triple_formacion", AMBOS, ["6,25"],
     ["a que distancia es el triple en infantil", "linea de tres en infantil", "distancia del triple en cadete"]),
    ("aro_mini", AMBOS, ["2,60"],
     ["a que altura va la canasta en mini", "altura del aro en benjamin", "canasta de minibasket"]),
    ("participacion_mini", AMBOS, ["2 periodos de los 5 primeros", "al menos dos periodos"],
     ["que reglas hay sobre los cuartos jugados por ninos en categoria benjamin",
      "participacion minima en minibasket", "que pasa si un nino no juega ningun cuarto"]),
    ("participacion_infantil", AMBOS, ["1 cuarto completo", "un cuarto completo"],
     ["cuanto tiene que jugar cada nino en infantil", "tiempo minimo de juego en infantil",
      "tienen que jugar todos los cuartos en infantil"]),
    ("cambios_infantil", AMBOS, ["ultimo cuarto"],
     ["cuando se pueden hacer cambios en infantil", "sustituciones en infantil",
      "puedo cambiar jugadores en cualquier cuarto de infantil"]),
    ("zona_mini", AMBOS, ["sin defensa zonal", "prohibidas las defensas en zona"],
     ["se puede defender en zona en minibasket", "presion a toda pista en benjamin", "que defensas estan prohibidas en alevin"]),
    ("cincuenta_puntos", AMBOS, ["50 puntos"],
     ["que pasa si ganamos por mucha diferencia", "diferencia de 50 puntos", "cuando se acaba el partido por diferencia"]),
    ("duracion_mini", AMBOS, ["6 periodos", "6 x 8", "6×8", "6 × 8"],
     ["cuanto dura un partido de minibasket", "cuantos cuartos tiene un partido de benjamin", "tiempo de partido en alevin"]),
    ("jugadores_acta", AMBOS, ["minimo de ocho jugadores", "minimo 9 jugadores", "min. 9", "de 8 a 14"],
     ["cuantos jugadores hay que apuntar en el acta en minibasket", "minimo de jugadores para jugar en alevin",
      "con cuantos ninos se puede jugar un partido"]),
    ("mixto", ARAGON, ["al menos una nina"],
     ["cuantas chicas tiene que haber en un equipo mixto", "reglas de equipo mixto", "minimo de ninas en mixto"]),
    ("arbitro_balon", ARAGON, ["arbitro no toca el balon"],
     ["el arbitro me da el balon en el saque de banda", "quien pone el balon en juego tras saque de banda en infantil",
      "el arbitro toca la pelota en el saque"]),
    ("tiempos_muertos", ARAGON, ["2 + 3"],
     ["cuantos tiempos muertos hay en infantil", "tiempos muertos en cadete", "cuantos tiempos muertos tengo"]),
    ("reloj_mini", ARAGON, ["reloj corrido"],
     ["el reloj se para en minibasket", "reloj corrido en alevin", "como se cuenta el tiempo en minibasket"]),
    ("sancion_zona", ARAGON, ["dos tiros libres y posesion"],
     ["que pasa si defiendo en zona en benjamin", "sancion por defensa en zona", "castigo por zona en minibasket"]),
    ("descanso_mini", ARAGON, ["descanso de cinco minutos"],
     ["cuanto dura el descanso en minibasket", "descanso entre periodos", "descanso de la media parte en benjamin"]),
    # ciegas de la ronda anterior: ya se usaron para ajustar, así que pasan a ser temas normales

    ("pista_trasera", AMBOS, ["devolver el balon a su pista trasera"],
     ["puedo devolver el balon atras una vez pasado el medio campo", "se puede pasar hacia atras pasando la linea central"]),
    ("cinco_segundos", AMBOS, ["5 segundos"],
     ["cuanto tiempo tengo para sacar de banda", "limite de tiempo para un saque"]),
    ("doble_regate", AMBOS, ["ambas manos a la vez"],
     ["puedo botar con las dos manos a la vez", "que pasa si agarro el balon y vuelvo a botar"]),
    ("salida_terreno", AMBOS, ["toca la linea limitrofe"],
     ["cuando se considera que el balon se ha ido fuera", "pisar la raya cuenta como salir"]),
    ("flagrante", AMBOS, ["temerario"],
     ["que es una falta flagrante", "falta muy dura o peligrosa"]),
    ("descalificacion", AMBOS, ["dos tecnicas de categoria 1"],
     ["cuantas tecnicas me echan del partido", "cuando descalifican a un jugador por tecnicas"]),
    ("senal_pasos", AMBOS, ["violacion de pasos"],
     ["que senal hace el arbitro cuando son pasos", "como se senala el desplazamiento ilegal"]),
    ("cilindro", AMBOS, ["cilindro"],
     ["que es el cilindro", "espacio vertical de un jugador"]),
    ("diferencia_mini", ARAGON, ["otro encuentro sin consecuencias"],
     ["que se hace con el tiempo que queda cuando hay mucha diferencia en benjamin",
      "si vamos ganando de muchos puntos se sigue jugando"]),
    ("triple_mini", AMBOS, ["triple de minibasket", "~4 m"],
     ["a que distancia se tira el triple en minibasket", "linea de tres en alevin"]),
    ("descanso_infantil", ARAGON, ["descansa en el banquillo durante uno de los tres primeros cuartos"],
     ["tiene que descansar un jugador de infantil", "puede un nino de infantil jugar todos los cuartos"]),
    ("sin_ocho", ARAGON, ["decide el resultado el comite de competicion"],
     ["que pasa si no tengo ocho ninos para el partido", "equipo con menos jugadores de los necesarios"]),
    ("bonus_mini", AMBOS, ["4 faltas de equipo", "5 faltas de equipo"],
     ["cuantas faltas de equipo hasta los tiros libres", "cuando entra el equipo en bonus"]),

    # ciegas de la ronda de señales/prórroga/descansos (2026-10-11): ya se usaron para ajustar
    ("senal_pasos", AMBOS, ["girando los punos"],
     ["que gesto hace el arbitro cuando pita pasos", "como indica el arbitro que me he pasado de pasos",
      "movimiento de brazos del arbitro por andar con el balon"]),
    ("senal_doble", AMBOS, ["palmear"],
     ["que senal es el doble regate", "como se marca que he botado dos veces", "gesto del arbitro por doble bote"]),
    ("senal_reloj_falta", AMBOS, ["levanta un puno cerrado"],
     ["como para el reloj el arbitro cuando hay falta", "que significa el puno en alto del arbitro",
      "diferencia entre parar el reloj por falta o por violacion"]),
    ("senal_cambio", AMBOS, ["antebrazos cruzados"],
     ["como piden los arbitros un cambio de jugador", "gesto de sustitucion del arbitro",
      "que significan los brazos cruzados del arbitro"]),
    ("senal_disruptiva", AMBOS, ["dos dedos a la altura de la cara"],
     ["como senala el arbitro la falta disruptiva", "gesto de la falta que sustituye a la antideportiva",
      "que hace el arbitro cuando pita una disruptiva"]),
    ("balon_fuera", AMBOS, ["ultimo jugador que toco el balon"],
     ["de quien es el balon cuando sale por la banda", "quien saca cuando el balon se va fuera",
      "pisar la linea de fondo con el balon en la mano"]),
    ("prorroga", AMBOS, ["prorrogas de 5 minutos", "1 tiempo muerto en cada prorroga"],
     ["cuanto dura el tiempo extra si hay empate", "que pasa si acabamos empatados el partido",
      "cuantos tiempos muertos hay en la prorroga"]),
    ("tiempo_muerto", AMBOS, ["cada tiempo muerto dura 1 minuto", "entrenador principal o el primer ayudante"],
     ["cuanto dura un tiempo muerto", "cuanto se para el partido en un tiempo muerto",
      "quien puede pedir tiempo muerto"]),
    ("minimo_comunidad", AMBOS, ["cada comunidad autonoma fija su minimo"],
     ["cuantos jugadores hay que tener en el acta en mi comunidad", "se puede jugar con seis jugadores en infantil",
      "minimo de jugadores para presentar el equipo en cadete"]),
    ("sustituir_cadete", AMBOS, ["en cadete se puede sustituir"],
     ["cuando puedo hacer cambios en cadete", "limitaciones para sustituir en cadete",
      "en cadete solo se cambia en el ultimo cuarto"]),
    ("descanso_partido", ARAGON, ["descanso del partido"],
     ["cuanto se para el partido entre el tercer y cuarto periodo de mini", "pausa entre periodos en alevin",
      "cuanto dura el intermedio en benjamin"]),
    ("descanso_jugador", ARAGON, ["descanso del jugador"],
     ["cuantos periodos descansa cada nino en alevin", "cada cuanto tiene que sentarse un jugador de minibasket",
      "tiene que salir del campo algun periodo un nino de benjamin"]),
    ("saque_rapido", AMBOS, ["saque rapido no se aplica en infantil"],
     ["cuando puede sacar el equipo sin esperar al arbitro", "saque sin que el arbitro entregue el balon tras violacion",
      "en que categorias no vale el saque rapido"]),
]


# Prueba ciega: formulaciones y temas escritos DESPUÉS de ajustar los sinónimos y los .md, sin tocar nada para ellas.
# Mide si lo ajustado generaliza. Si se corrige algo por culpa de estas, hay que escribir otras nuevas (dejan de ser
# ciegas) y pasar estas a TEMAS. Ronda 2 de 2026-10-11 (señales, balón fuera, prórroga, tiempos muertos, descansos...).
PRUEBA_CIEGA = [
    ("senal_pasos", AMBOS, ["girando los punos"],
     ["como avisa el colegiado de que hay pasos", "el arbitro gira los punos que significa",
      "gesto cuando un jugador camina con el balon en las manos"]),
    ("senal_doble", AMBOS, ["palmear"],
     ["que significa que el arbitro haga como que bota con la mano abierta",
      "senal de que he vuelto a botar tras agarrar la pelota", "como pita el doble el arbitro con las manos"]),
    ("senal_reloj_falta", AMBOS, ["levanta un puno cerrado"],
     ["cuando el arbitro levanta el puno que ocurre", "que gesto para el cronometro por una falta",
      "diferencia entre mano abierta y puno en alto"]),
    ("senal_cambio", AMBOS, ["antebrazos cruzados"],
     ["gesto que hace el arbitro para dejar entrar a un suplente", "que significa cruzar los antebrazos el colegiado",
      "como se indica que va a haber un cambio"]),
    ("senal_disruptiva", AMBOS, ["dos dedos a la altura de la cara"],
     ["que gesto indica la nueva falta de 2026 que no descalifica", "como la pita el arbitro con dos dedos en la cara",
      "senal de falta disruptiva"]),
    ("senal_24", AMBOS, ["tocandose el hombro"],
     ["como se senala el reloj de 24 segundos", "gesto de los 24 segundos del arbitro",
      "que hace el arbitro con la mano en el hombro"]),
    ("senal_tecnica", AMBOS, ["formando una t"],
     ["como senala el arbitro la tecnica", "gesto de falta tecnica", "senal de tiempo muerto con las manos en t"]),
    ("balon_fuera", AMBOS, ["ultimo jugador que toco el balon"],
     ["a quien le toca sacar si la pelota sale tras tocar a un defensor",
      "cuando se considera que un jugador esta fuera de la pista", "toca la pelota la raya y sale de quien es"]),
    ("prorroga", AMBOS, ["prorrogas de 5 minutos"],
     ["cuantos minutos dura la prorroga", "si hay empate al final del cuarto cuarto que se hace",
      "se acumulan los tiempos muertos que no use a la prorroga"]),
    ("tiempo_muerto", AMBOS, ["cada tiempo muerto dura 1 minuto", "entrenador principal o el primer ayudante",
                              "oportunidad de tiempo muerto"],
     ["duracion del tiempo muerto", "puede el ayudante pedir tiempo muerto", "cuando se puede pedir tiempo muerto"]),
    ("minimo_comunidad", AMBOS, ["cada comunidad autonoma fija su minimo"],
     ["cuantos ninos minimo tiene que haber en el acta en aragon", "puedo inscribir menos jugadores en otra comunidad",
      "minimo de jugadores en el acta segun la federacion territorial"]),
    ("sustituir_cadete", AMBOS, ["en cadete se puede sustituir"],
     ["se pueden hacer cambios libremente en cadete", "restricciones de cambios en cadete en aragon",
      "en que cuartos puedo cambiar a un cadete"]),
    ("descanso_partido", ARAGON, ["descanso del partido"],
     ["cuanto tiempo se para el juego entre periodos en minibasket", "pausa de la media parte en alevin",
      "intermedio entre el tercer y el cuarto periodo de benjamin"]),
    ("descanso_jugador", ARAGON, ["descanso del jugador"],
     ["cuantos periodos se queda sentado un nino de alevin", "cuanto tiene que estar en el banquillo un jugador de minibasket",
      "en infantil cuando descansa cada jugador"]),
    ("saque_rapido", AMBOS, ["saque rapido no se aplica en infantil"],
     ["en que casos se saca sin que el arbitro toque el balon", "puede un equipo de infantil sacar rapido",
      "saque rapido en los ultimos dos minutos"]),
]


def normalizar(texto: str) -> str:
    sin = unicodedata.normalize("NFD", texto.lower())
    # sin tildes y con los saltos de línea del .md colapsados: una frase partida en dos líneas sigue siendo la frase
    return " ".join("".join(c for c in sin if unicodedata.category(c) != "Mn").split())


def _corpus_por_ambito() -> dict[str, str]:
    """Texto normalizado de los .md que ve cada ámbito: el general, y el general más el suyo."""
    from config import REGLAMENTO_DIR  # noqa: E402
    base = Path(REGLAMENTO_DIR)
    def leer(carpeta: str) -> str:
        d = base / carpeta
        return normalizar("\n".join(f.read_text(encoding="utf-8") for f in sorted(d.glob("*.md")))) if d.is_dir() else ""
    general = leer("general")
    return {"general": general, "aragon": general + leer("aragon")}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--detalle", action="store_true", help="muestra también las formulaciones que aciertan")
    ap.add_argument("--ciega", action="store_true", help="solo la prueba ciega (formulaciones no usadas para ajustar)")
    ap.add_argument("--ausentes-fallan", action="store_true",
                    help="los temas cuya respuesta no está en los .md cuentan como fallos (línea base antes de ampliar el corpus)")
    ap.add_argument("--sin-ampliacion", action="store_true",
                    help="línea base: busca con la pregunta tal cual, sin añadir los términos del reglamento")
    args = ap.parse_args(argv)

    import reglamento  # noqa: E402  (necesita config y ChromaDB)
    from reglamento import recuperar_contexto_reglamento  # noqa: E402
    if args.sin_ampliacion:
        reglamento.consulta_ampliada = lambda pregunta: pregunta

    corpus = _corpus_por_ambito()
    total = aciertos = 0
    fallos, sin_respuesta = [], []
    for id_, ambitos, terminos, formulaciones in (PRUEBA_CIEGA if args.ciega else TEMAS):
        claves = [normalizar(t) for t in terminos]
        for ambito in ambitos:
            # la respuesta tiene que estar en los .md de ese ámbito (y en el general, que lo completa)
            if not any(c in corpus[ambito] for c in claves):
                sin_respuesta.append(f"{id_} [{ambito}]")
                if args.ausentes_fallan:
                    total += len(formulaciones)
                    fallos.extend((id_, ambito, f"(sin respuesta en los .md) {p}") for p in formulaciones)
                continue
            for pregunta in formulaciones:
                contexto = normalizar("\n".join(recuperar_contexto_reglamento(pregunta, ambito)))
                ok = any(c in contexto for c in claves)
                total += 1
                aciertos += ok
                if not ok:
                    fallos.append((id_, ambito, pregunta))
                elif args.detalle:
                    print(f"  ok   [{ambito:7}] {id_}: {pregunta}")
    print(f"\nFormulaciones coloquiales: {aciertos}/{total} ({aciertos / total:.0%}) recuperan la norma en el contexto del modelo")
    if sin_respuesta:
        print(f"Sin la respuesta en los .md (excluidos): {', '.join(sin_respuesta)}")
    for id_, ambito, pregunta in fallos:
        print(f"  FALLA [{ambito:7}] {id_}: {pregunta}")
    return 0 if not fallos else 1


if __name__ == "__main__":
    sys.exit(main())
