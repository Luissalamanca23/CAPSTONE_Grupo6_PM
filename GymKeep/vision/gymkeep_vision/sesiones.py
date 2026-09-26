"""Maquina de estados de uso por equipo (histeresis T_on / T_off).

Implementa §6.6.2 y §6.7.3 de `Estudio_Modelo_Preventivo_Mantenimiento.md`: una persona
detectada sobre una maquina NO es una sesion de uso. La presencia tiene que sostenerse
`t_on_s` segundos para abrir una sesion, y la ausencia tiene que sostenerse `t_off_s`
segundos para cerrarla (el descanso entre series no parte la sesion en dos).

Dos decisiones que fijan el tiempo de uso medido:

- El inicio de la sesion es **retroactivo**: es el instante en que la persona aparecio,
  no el instante en que se cumplio `t_on_s`. Si no, cada sesion perderia 30 s.
- El fin de la sesion es la **ultima presencia observada**, no el instante en que se
  cumplio `t_off_s`. Si no, cada sesion ganaria 90 s que nadie uso la maquina.

Todo se mide con el reloj del video (`t`, en segundos), nunca contando cuadros: asi el
tiempo de uso no depende de los FPS de la camara ni de cada cuantos cuadros se analiza
(§6.6.7).

Este modulo no sabe nada de video ni de YOLO: recibe una `Observacion` por instante y
devuelve eventos. Por eso se puede probar con datos sinteticos (ver tests/).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum


class Estado(str, Enum):
    LIBRE = "libre"
    CANDIDATA = "candidata"  # hay alguien, pero todavia no cumple t_on_s
    EN_USO = "en_uso"
    PAUSA = "pausa"  # sesion abierta, nadie encima ahora (ej. descanso entre series)


@dataclass(frozen=True)
class ParametrosUso:
    t_on_s: float = 30.0  # MP-45
    t_off_s: float = 90.0  # MP-46
    # Huecos de deteccion mas cortos que esto no cuentan como ausencia (parpadeo del
    # detector, una persona que tapa a otra un instante).
    gracia_s: float = 2.0
    # Cada cuanto se emite `uso_en_curso` mientras la sesion sigue abierta. Le sirve al
    # backend para distinguir una sesion real de un `inicio_uso` huerfano (§6.6.5).
    heartbeat_s: float = 60.0
    # Un salto de tiempo mayor que esto entre dos observaciones (video cortado, camara
    # caida) no se suma como presencia: no se imputa uso no observado (MP-50).
    dt_max_s: float = 5.0

    def __post_init__(self):
        if self.t_off_s <= self.gracia_s:
            raise ValueError("t_off_s debe ser mayor que gracia_s")


@dataclass(frozen=True)
class Observacion:
    """Lo que el detector ve sobre UNA maquina en un instante."""

    t: float
    personas: int
    confianza: float | None = None  # la mayor confianza entre las personas presentes
    track_ids: tuple[int, ...] = ()


@dataclass
class Sesion:
    ref: str  # UUID local: correlaciona inicio_uso / uso_en_curso / fin_uso
    inicio: float
    ultima_presencia: float
    fin: float | None = None
    presencia_s: float = 0.0  # tiempo con alguien efectivamente encima de la maquina
    pausas: int = 0
    pausa_max_s: float = 0.0
    suma_confianza: float = 0.0
    n_confianza: int = 0
    personas_max: int = 0
    track_ids: set[int] = field(default_factory=set)
    eventos: int = 0
    cierre: str | None = None  # 'ausencia' | 'fin_de_video' | 'interrumpido'

    @property
    def abierta(self) -> bool:
        return self.fin is None

    @property
    def duracion_s(self) -> float:
        fin = self.fin if self.fin is not None else self.ultima_presencia
        return max(0.0, fin - self.inicio)

    @property
    def confianza_promedio(self) -> float | None:
        if not self.n_confianza:
            return None
        return self.suma_confianza / self.n_confianza


@dataclass(frozen=True)
class EventoUso:
    tipo: str  # 'inicio_uso' | 'uso_en_curso' | 'fin_uso'
    t: float  # instante al que corresponde el evento (inicio real, ahora, ultima presencia)
    t_emision: float  # instante en que el pipeline pudo afirmarlo
    sesion: Sesion
    confianza: float | None


class MonitorMaquina:
    """Sigue el estado de uso de una maquina a partir de observaciones sucesivas."""

    def __init__(self, parametros: ParametrosUso):
        self.p = parametros
        self.estado = Estado.LIBRE
        self.sesion: Sesion | None = None
        self.sesiones: list[Sesion] = []
        self.candidatas_descartadas = 0  # transeuntes: presencia menor a t_on_s

        self._t_prev: float | None = None
        self._presente_prev = False
        self._candidata: Sesion | None = None
        self._ultimo_heartbeat = 0.0

    @property
    def uso_total_s(self) -> float:
        total = sum(s.duracion_s for s in self.sesiones)
        if self.sesion is not None:
            total += self.sesion.duracion_s
        return total

    def actualizar(self, obs: Observacion) -> list[EventoUso]:
        if self._t_prev is not None and obs.t < self._t_prev:
            raise ValueError("las observaciones deben llegar en orden de tiempo")

        presente = obs.personas > 0
        dt = 0.0 if self._t_prev is None else obs.t - self._t_prev
        continua = presente and self._presente_prev and dt <= self.p.dt_max_s
        self._t_prev = obs.t
        self._presente_prev = presente

        if self.estado == Estado.LIBRE:
            if presente:
                self._candidata = Sesion(ref=str(uuid.uuid4()), inicio=obs.t, ultima_presencia=obs.t)
                self._acumular(self._candidata, obs, 0.0)
                self.estado = Estado.CANDIDATA
            return []

        if self.estado == Estado.CANDIDATA:
            cand = self._candidata
            if presente:
                if obs.t - cand.ultima_presencia > self.p.gracia_s:
                    # Volvio despues de un hueco real: la presencia no fue continua,
                    # asi que la candidatura empieza de nuevo desde aqui.
                    self.candidatas_descartadas += 1
                    cand = self._candidata = Sesion(
                        ref=str(uuid.uuid4()), inicio=obs.t, ultima_presencia=obs.t
                    )
                self._acumular(cand, obs, dt if continua else 0.0)
                if obs.t - cand.inicio >= self.p.t_on_s:
                    return [self._abrir(cand, obs)]
            elif obs.t - cand.ultima_presencia > self.p.gracia_s:
                self.candidatas_descartadas += 1
                self._candidata = None
                self.estado = Estado.LIBRE
            return []

        # EN_USO o PAUSA: hay una sesion abierta.
        sesion = self.sesion
        if presente:
            hueco = obs.t - sesion.ultima_presencia
            if hueco > self.p.gracia_s:
                sesion.pausas += 1
                sesion.pausa_max_s = max(sesion.pausa_max_s, hueco)
            self._acumular(sesion, obs, dt if continua else 0.0)
            self.estado = Estado.EN_USO
            if obs.t - self._ultimo_heartbeat >= self.p.heartbeat_s:
                self._ultimo_heartbeat = obs.t
                sesion.eventos += 1
                return [EventoUso("uso_en_curso", obs.t, obs.t, sesion, obs.confianza)]
            return []

        ausencia = obs.t - sesion.ultima_presencia
        if ausencia >= self.p.t_off_s:
            return [self._cerrar(obs.t, "ausencia")]
        if ausencia > self.p.gracia_s:
            self.estado = Estado.PAUSA
        return []

    def finalizar(self, t: float, motivo: str = "fin_de_video") -> list[EventoUso]:
        """Cierra lo que quede abierto al terminar el video o al interrumpir el proceso.

        Una candidatura que no alcanzo t_on_s se descarta: no hay evidencia de uso."""
        if self._candidata is not None and self.estado == Estado.CANDIDATA:
            self.candidatas_descartadas += 1
            self._candidata = None
            self.estado = Estado.LIBRE
        if self.sesion is None:
            return []
        return [self._cerrar(t, motivo)]

    def _acumular(self, sesion: Sesion, obs: Observacion, dt_presente: float) -> None:
        sesion.ultima_presencia = obs.t
        sesion.presencia_s += dt_presente
        sesion.personas_max = max(sesion.personas_max, obs.personas)
        sesion.track_ids.update(obs.track_ids)
        if obs.confianza is not None:
            sesion.suma_confianza += obs.confianza
            sesion.n_confianza += 1

    def _abrir(self, candidata: Sesion, obs: Observacion) -> EventoUso:
        self.sesion = candidata
        self._candidata = None
        self.estado = Estado.EN_USO
        self._ultimo_heartbeat = obs.t
        candidata.eventos = 1
        return EventoUso("inicio_uso", candidata.inicio, obs.t, candidata, candidata.confianza_promedio)

    def _cerrar(self, t_emision: float, motivo: str) -> EventoUso:
        sesion = self.sesion
        sesion.fin = sesion.ultima_presencia
        sesion.cierre = motivo
        sesion.eventos += 1
        self.sesiones.append(sesion)
        self.sesion = None
        self.estado = Estado.LIBRE
        return EventoUso("fin_uso", sesion.fin, t_emision, sesion, sesion.confianza_promedio)
