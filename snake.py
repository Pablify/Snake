#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
snake.py — Juego "Snake" en un solo archivo usando pygame.

Requisitos:
- Python 3.10+
- pip install pygame

Ejecución:
    python snake.py [--mode easy|normal|hard] [--wrap on|off]

Controles (en juego):
- Flechas o WASD: mover
- P: pausa
- R: reiniciar
- M: sonido ON/OFF
- ESC: menú principal / salir en el menú
- ENTER en el menú: confirmar

Notas:
- Puntuaciones máximas y estado del sonido se guardan en snake_highscores.json
- Si no se puede leer/escribir el archivo o el mixer falla, el juego sigue sin guardar/sonido.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Iterable, Optional, Tuple

import pygame

# =========================
# == Configuración global ==
# =========================

# Ventana y cuadrícula
WIDTH, HEIGHT = 640, 480
CELL = 20
GRID_W, GRID_H = WIDTH // CELL, HEIGHT // CELL

# Colores (RGB)
COLOR_BG = (30, 30, 30)
COLOR_GRID = (45, 45, 45)
COLOR_SNAKE = (0, 170, 0)
COLOR_SNAKE_HEAD = (0, 220, 0)
COLOR_FOOD = (220, 50, 50)
COLOR_GOLD = (255, 200, 0)
COLOR_TEXT = (230, 230, 230)
COLOR_OVERLAY = (0, 0, 0, 140)

# Opciones de depuración
SHOW_GRID = True
SHOW_DEBUG = False  # mostrar FPS/level en HUD

# Lógica de comida
GOLD_CHANCE = 1 / 12.0      # prob. tras comer comida normal
GOLD_LIFETIME = 7.0         # segundos

# Puntuación
SCORE_NORMAL = 10
SCORE_GOLD = 30
GROW_NORMAL = 1
GROW_GOLD = 2

# Velocidades por modo
BASE_FPS = {
    "easy": 8.0,
    "normal": 10.0,
    "hard": 12.0,
}
MAX_FPS_CAP = {
    "easy": 20.0,
    "normal": 24.0,
    "hard": 28.0,
}
SPEED_STEP_EVERY_SCORE = 5       # cada 5 puntos
SPEED_INCREMENT = 0.5            # +0.5 FPS

# Fuentes (tamaños)
FONT_HUD = 20
FONT_MENU = 32
FONT_TITLE = 48

# Archivo de guardado
SAVE_FILE = "snake_highscores.json"

# =========================
# == Utilidades varias   ==
# =========================

Vec2 = Tuple[int, int]


def grid_to_px(x: int, y: int) -> Tuple[int, int]:
    """Convierte coordenadas de cuadrícula a píxeles."""
    return x * CELL, y * CELL


def clamp(n: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, n))


def key_for_record(mode: str, wrap_on: bool) -> str:
    return f"{mode}_{'on' if wrap_on else 'off'}"


def safe_load_highscores() -> dict:
    """Carga el JSON de puntuaciones; si falla, devuelve estructura por defecto sin romper."""
    data = {
        "sound": True,
        "records": {}
    }
    try:
        if os.path.exists(SAVE_FILE):
            with open(SAVE_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                data.update(raw)
    except Exception:
        # Silencioso: si no se puede leer, seguimos con valores por defecto
        pass
    return data


def safe_save_highscores(data: dict) -> None:
    """Guarda el JSON; ignora silenciosamente si falla (sin romper la partida)."""
    try:
        with open(SAVE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# =========================
# == Sonido (opcionales) ==
# =========================

class SFX:
    """Generación de sonidos simples sin archivos externos.
    Nota: pygame.mixer.Sound(buffer=...) puede variar entre plataformas;
    si algo falla, desactivamos sonido sin romper el juego.
    """
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.ok = False
        self._sounds: dict[str, Optional[pygame.mixer.Sound]] = {}

        if not enabled:
            return

        try:
            pygame.mixer.init()  # puede lanzar excepción
            self.ok = True
            # Preparamos pequeños "bips" de distinta frecuencia
            self._sounds["eat"] = self._make_beep(440, 80)      # A4 corto
            self._sounds["eat_gold"] = self._make_beep(660, 120)
            self._sounds["start"] = self._make_beep(523, 100)   # C5
            self._sounds["over"] = self._make_beep(200, 200)
        except Exception:
            # Si algo sale mal, no usamos sonido
            self.ok = False
            self.enabled = False
            try:
                pygame.mixer.quit()
            except Exception:
                pass

    def _make_beep(self, freq_hz: int, duration_ms: int) -> Optional[pygame.mixer.Sound]:
        """Crea un tono cuadrado básico. Si falla la ruta del buffer, devolvemos None."""
        try:
            sample_rate = 22050
            length = int(sample_rate * (duration_ms / 1000.0))
            # Onda cuadrada simple 16-bit mono
            buf = bytearray()
            amplitude = 20000  # 16-bit
            period = sample_rate / float(freq_hz)
            for i in range(length):
                # mitad del periodo arriba, mitad abajo
                v = amplitude if (i % int(period)) < period / 2 else -amplitude
                # empaquetar en little-endian 16-bit
                buf += int(v).to_bytes(2, byteorder="little", signed=True)
            sound = pygame.mixer.Sound(buffer=bytes(buf))
            return sound
        except Exception:
            return None

    def play(self, name: str) -> None:
        if not (self.enabled and self.ok):
            return
        s = self._sounds.get(name)
        if s is not None:
            try:
                s.play()
            except Exception:
                pass

    def toggle(self) -> bool:
        """Alterna sonido. Si mixer falló, se queda en False."""
        self.enabled = not self.enabled and self.ok
        return self.enabled


# =========================
# == Modelos del juego   ==
# =========================

DIRS: dict[str, Vec2] = {
    "UP": (0, -1),
    "DOWN": (0, 1),
    "LEFT": (-1, 0),
    "RIGHT": (1, 0),
}


def opposite(a: Vec2, b: Vec2) -> bool:
    return a[0] == -b[0] and a[1] == -b[1]


class Snake:
    """Representa la serpiente con un deque de segmentos (x, y) en la cuadrícula."""
    def __init__(self, start: Vec2, length: int = 3, direction: Vec2 = DIRS["RIGHT"]):
        self.body: Deque[Vec2] = deque()
        self.dir: Vec2 = direction
        for i in range(length):
            # cuerpo inicial extendiéndose hacia la izquierda
            self.body.appendleft((start[0] - i, start[1]))

    @property
    def head(self) -> Vec2:
        return self.body[0]

    def turn(self, newdir: Vec2) -> None:
        """Cambiar dirección evitando giro 180° instantáneo."""
        if opposite(self.dir, newdir):
            return
        self.dir = newdir

    def next_head(self) -> Vec2:
        x, y = self.head
        dx, dy = self.dir
        return (x + dx, y + dy)

    def move(self, grow: bool = False) -> None:
        """Avanza un paso. Si grow=True, no elimina la cola (la serpiente crece)."""
        nx, ny = self.next_head()
        self.body.appendleft((nx, ny))
        if not grow:
            self.body.pop()

    def hits_self(self) -> bool:
        """Comprueba si la cabeza toca el cuerpo."""
        return self.head in list(self.body)[1:]

    def occupies(self) -> set[Vec2]:
        return set(self.body)


@dataclass
class Food:
    pos: Vec2
    kind: str  # "normal" | "gold"
    spawn_time: float = 0.0  # para oro


# =========================
# == Lógica de juego     ==
# =========================

class Game:
    def __init__(self, mode: str = "normal", wrap_on: bool = False, cfg_loaded: Optional[dict] = None):
        pygame.init()
        pygame.display.set_caption("SNAKE")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), flags=0)
        self.clock = pygame.time.Clock()

        # Fuentes
        self.font_hud = pygame.font.SysFont(None, FONT_HUD)
        self.font_menu = pygame.font.SysFont(None, FONT_MENU)
        self.font_title = pygame.font.SysFont(None, FONT_TITLE)

        # Estado general
        self.mode = mode
        self.wrap_on = wrap_on
        self.state = "menu"  # "menu" | "playing" | "paused" | "gameover"

        # Cargar/salvar estado persistente
        self.save = cfg_loaded if cfg_loaded is not None else safe_load_highscores()
        self.sound = SFX(enabled=bool(self.save.get("sound", True)))

        # Puntuaciones
        self.records: dict = self.save.get("records", {})

        # Inicializar partida
        self.reset_run(full_reset=True)

        # Menú
        self.menu_items = [
            ("Start", None),
            ("Mode", ["easy", "normal", "hard"]),
            ("Wrap", ["off", "on"]),
            ("Sound", ["off", "on"]),
            ("Quit", None),
        ]
        self.menu_index = 0

    # --------------- Estado de partida ----------------

    def reset_run(self, full_reset: bool = False) -> None:
        """Prepara una nueva partida (o reinicia tras game over)."""
        cx, cy = GRID_W // 2, GRID_H // 2
        self.snake = Snake(start=(cx, cy), length=3, direction=DIRS["RIGHT"])
        self.score = 0
        self.current_fps = BASE_FPS[self.mode]
        self.logic_acc = 0.0  # acumulador de tiempo para ticks lógicos
        self.game_over_reason = ""

        # Comida inicial
        self.food: Optional[Food] = None
        self.spawn_food(force_normal=True)

        # Mejor puntuación para clave actual
        self.best = int(self.records.get(key_for_record(self.mode, self.wrap_on), 0))

        if full_reset and self.sound.enabled:
            self.sound.play("start")

    # --------------- Comida ---------------------------

    def spawn_food(self, force_normal: bool = False) -> None:
        """Genera comida en una celda libre. Si force_normal es True, siempre será normal."""
        occ = self.snake.occupies()
        free = [(x, y) for x in range(GRID_W) for y in range(GRID_H) if (x, y) not in occ]
        if not free:
            # tablero lleno: victoria simbólica, pero tratamos como sin espacio
            return
        pos = random.choice(free)
        if not force_normal and random.random() < GOLD_CHANCE and self.food is None:
            self.food = Food(pos=pos, kind="gold", spawn_time=time.time())
        else:
            self.food = Food(pos=pos, kind="normal", spawn_time=0.0)

    # --------------- Guardado -------------------------

    def persist(self) -> None:
        """Guarda récord y estado de sonido."""
        self.save["sound"] = bool(self.sound.enabled and self.sound.ok)
        self.save["records"] = self.records
        safe_save_highscores(self.save)

    # --------------- Bucle principal ------------------

    def run(self) -> None:
        while True:
            if self.state == "menu":
                if not self.menu_loop():
                    break
            elif self.state == "playing":
                if not self.play_loop():
                    break
            elif self.state == "paused":
                if not self.pause_loop():
                    break
            elif self.state == "gameover":
                if not self.gameover_loop():
                    break

        # Al salir
        self.persist()
        try:
            if self.sound.ok:
                pygame.mixer.quit()
        except Exception:
            pass
        pygame.quit()

    # --------------- Entradas -------------------------

    def handle_turn_keys(self, key: int) -> None:
        """Mapea teclas a direcciones."""
        if key in (pygame.K_UP, pygame.K_w):
            self.snake.turn(DIRS["UP"])
        elif key in (pygame.K_DOWN, pygame.K_s):
            self.snake.turn(DIRS["DOWN"])
        elif key in (pygame.K_LEFT, pygame.K_a):
            self.snake.turn(DIRS["LEFT"])
        elif key in (pygame.K_RIGHT, pygame.K_d):
            self.snake.turn(DIRS["RIGHT"])

    # --------------- Lógica por estado ----------------

    def play_loop(self) -> bool:
        dt = self.clock.tick(60) / 1000.0
        # Eventos
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return False
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    self.state = "menu"
                    return True
                elif e.key == pygame.K_p:
                    self.state = "paused"
                    return True
                elif e.key == pygame.K_r:
                    self.reset_run(full_reset=False)
                elif e.key == pygame.K_m:
                    self.sound.toggle()
                    self.save["sound"] = bool(self.sound.enabled)
                    self.persist()
                else:
                    self.handle_turn_keys(e.key)

        # Ticks lógicos discretos según current_fps
        self.logic_acc += dt
        step = 1.0 / self.current_fps
        while self.logic_acc >= step:
            self.logic_acc -= step
            self.step_logic()

        # Render
        self.draw_game()
        return True

    def pause_loop(self) -> bool:
        dt = self.clock.tick(60) / 1000.0
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return False
            elif e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_ESCAPE, pygame.K_p):
                    self.state = "playing"
                    return True
                elif e.key == pygame.K_m:
                    self.sound.toggle()
                    self.save["sound"] = bool(self.sound.enabled)
                    self.persist()
        # Dibujar último frame + overlay
        self.draw_game(overlay_paused=True)
        return True

    def gameover_loop(self) -> bool:
        self.clock.tick(60)
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return False
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    self.state = "menu"
                    return True
                elif e.key == pygame.K_r:
                    self.reset_run(full_reset=False)
                    self.state = "playing"
                    return True
        # Dibujar pantalla de juego con modal de Game Over
        self.draw_game(overlay_gameover=True)
        return True

    def menu_loop(self) -> bool:
        self.clock.tick(60)
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return False
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    return False
                elif e.key == pygame.K_UP:
                    self.menu_index = (self.menu_index - 1) % len(self.menu_items)
                elif e.key == pygame.K_DOWN:
                    self.menu_index = (self.menu_index + 1) % len(self.menu_items)
                elif e.key in (pygame.K_LEFT, pygame.K_RIGHT):
                    self.menu_change_value(e.key == pygame.K_RIGHT)
                elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    if self.menu_items[self.menu_index][0] == "Start":
                        self.reset_run(full_reset=True)
                        self.state = "playing"
                        return True
                    elif self.menu_items[self.menu_index][0] == "Quit":
                        return False

        self.draw_menu()
        return True

    def menu_change_value(self, forward: bool) -> None:
        """Cambia valor del item activo (modo, wrap, sonido)."""
        label, values = self.menu_items[self.menu_index]
        if not values:
            return
        if label == "Mode":
            idx = values.index(self.mode)
            idx = (idx + (1 if forward else -1)) % len(values)
            self.mode = values[idx]
            self.current_fps = BASE_FPS[self.mode]
            self.best = int(self.records.get(key_for_record(self.mode, self.wrap_on), 0))
        elif label == "Wrap":
            wrap_values = ["off", "on"]
            idx = wrap_values.index("on" if self.wrap_on else "off")
            idx = (idx + (1 if forward else -1)) % len(wrap_values)
            self.wrap_on = wrap_values[idx] == "on"
            self.best = int(self.records.get(key_for_record(self.mode, self.wrap_on), 0))
        elif label == "Sound":
            s_values = ["off", "on"]
            idx = s_values.index("on" if (self.sound.enabled and self.sound.ok) else "off")
            idx = (idx + (1 if forward else -1)) % len(s_values)
            desired_on = s_values[idx] == "on"
            if desired_on and not (self.sound.enabled and self.sound.ok):
                # Intentar habilitar
                self.sound.enabled = True
                self.sound.ok = True  # el mixer ya estaba init si se creó; si falló, quedará mute
            elif not desired_on:
                self.sound.enabled = False
            self.save["sound"] = bool(self.sound.enabled and self.sound.ok)
            self.persist()

    # --------------- Paso lógico ----------------------

    def step_logic(self) -> None:
        """Un paso de la simulación: mover, gestionar comida y colisiones."""
        # Calcular nueva posición de la cabeza
        nx, ny = self.snake.next_head()

        # Gestión de bordes (wrap o game over)
        if self.wrap_on:
            nx %= GRID_W
            ny %= GRID_H
        else:
            if nx < 0 or nx >= GRID_W or ny < 0 or ny >= GRID_H:
                self.game_over_reason = "wall"
                self.to_game_over()
                return

        # ¿Comer?
        grow = False
        ate_kind = None
        if self.food and (nx, ny) == self.food.pos:
            if self.food.kind == "gold":
                self.score += SCORE_GOLD
                grow = True
                # crecer +2 → mover dos veces con grow=True
                ate_kind = "gold"
            else:
                self.score += SCORE_NORMAL
                grow = True
                ate_kind = "normal"

        # Mover (si gold, creceremos 2 en total)
        self.snake.move(grow=grow)
        if ate_kind == "gold":
            # segundo crecimiento inmediato
            self.snake.move(grow=True)

        # Colisión con el propio cuerpo
        if self.snake.hits_self():
            self.game_over_reason = "self"
            self.to_game_over()
            return

        # Tras mover, gestionar comida (aparición/desaparición)
        now = time.time()
        if ate_kind is not None:
            # reproducir sonido
            if ate_kind == "gold":
                self.sound.play("eat_gold")
            else:
                self.sound.play("eat")
            # decidir próxima comida
            if ate_kind == "normal" and random.random() < GOLD_CHANCE:
                self.spawn_food(force_normal=False)  # intenta oro
                if self.food and self.food.kind == "gold":
                    self.food.spawn_time = now
                else:
                    self.spawn_food(force_normal=True)
            else:
                self.spawn_food(force_normal=True)
        else:
            # si hay oro y se agota su vida, reemplazar por comida normal
            if self.food and self.food.kind == "gold":
                if now - self.food.spawn_time > GOLD_LIFETIME:
                    self.spawn_food(force_normal=True)

        # Aumentar velocidad por puntuación
        target_cap = MAX_FPS_CAP[self.mode]
        inc_steps = self.score // SPEED_STEP_EVERY_SCORE
        self.current_fps = clamp(BASE_FPS[self.mode] + inc_steps * SPEED_INCREMENT, BASE_FPS[self.mode], target_cap)

        # Actualizar récord en vivo
        if self.score > self.best:
            self.best = self.score
            self.records[key_for_record(self.mode, self.wrap_on)] = self.best

    def to_game_over(self) -> None:
        """Transición a Game Over y sonido."""
        self.state = "gameover"
        self.sound.play("over")
        # Guardar récords inmediatamente
        self.persist()

    # --------------- Dibujo ---------------------------

    def draw_grid(self) -> None:
        if not SHOW_GRID:
            return
        surf = self.screen
        for x in range(0, WIDTH, CELL):
            pygame.draw.line(surf, COLOR_GRID, (x, 0), (x, HEIGHT), 1)
        for y in range(0, HEIGHT, CELL):
            pygame.draw.line(surf, COLOR_GRID, (0, y), (WIDTH, y), 1)

    def draw_game(self, overlay_paused: bool = False, overlay_gameover: bool = False) -> None:
        self.screen.fill(COLOR_BG)
        self.draw_grid()

        # Comida
        if self.food:
            fx, fy = self.food.pos
            px, py = grid_to_px(fx, fy)
            color = COLOR_GOLD if self.food.kind == "gold" else COLOR_FOOD
            rect = pygame.Rect(px, py, CELL, CELL)
            pygame.draw.rect(self.screen, color, rect)

            # Si es oro y le quedan <2s, hacer parpadeo simple
            if self.food.kind == "gold":
                remain = max(0.0, GOLD_LIFETIME - (time.time() - self.food.spawn_time))
                if remain < 2.0 and int(time.time() * 6) % 2 == 0:
                    pygame.draw.rect(self.screen, COLOR_BG, rect.inflate(-6, -6))

        # Serpiente
        for i, (sx, sy) in enumerate(self.snake.body):
            px, py = grid_to_px(sx, sy)
            rect = pygame.Rect(px, py, CELL, CELL)
            if i == 0:
                color = COLOR_SNAKE_HEAD
            else:
                # pequeño "skin": alternar tono del cuerpo
                tone = 0 if (i % 2 == 0) else 20
                color = (max(0, COLOR_SNAKE[0]-tone), min(255, COLOR_SNAKE[1]+tone), max(0, COLOR_SNAKE[2]-tone))
            pygame.draw.rect(self.screen, color, rect)

        # HUD (Score / Best)
        hud_left = self.font_hud.render(f"Score: {self.score}", True, COLOR_TEXT)
        self.screen.blit(hud_left, (10, 8))
        hud_right = self.font_hud.render(f"Best: {self.best}", True, COLOR_TEXT)
        self.screen.blit(hud_right, (WIDTH - hud_right.get_width() - 10, 8))

        if SHOW_DEBUG:
            dbg = self.font_hud.render(f"{self.mode.upper()} | FPS: {self.current_fps:.1f} | Wrap: {'ON' if self.wrap_on else 'OFF'}", True, COLOR_TEXT)
            self.screen.blit(dbg, ((WIDTH - dbg.get_width()) // 2, 8))

        # Overlays
        if overlay_paused:
            self.draw_center_overlay("PAUSADO", "Pulsa P o ESC para continuar")
        if overlay_gameover:
            reason = "¡Chocaste con la pared!" if self.game_over_reason == "wall" else "¡Te mordiste!"
            self.draw_center_overlay("GAME OVER", f"{reason}\nR — reiniciar  |  ESC — menú")

        pygame.display.flip()

    def draw_center_overlay(self, title: str, subtitle: str) -> None:
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill(COLOR_OVERLAY)
        self.screen.blit(overlay, (0, 0))

        t = self.font_title.render(title, True, COLOR_TEXT)
        s_lines = subtitle.split("\n")
        s_surfs = [self.font_menu.render(line, True, COLOR_TEXT) for line in s_lines]

        total_h = t.get_height() + 12 + sum(s.get_height() for s in s_surfs) + (6 * (len(s_surfs) - 1))
        y = (HEIGHT - total_h) // 2
        self.screen.blit(t, ((WIDTH - t.get_width()) // 2, y))
        y += t.get_height() + 12
        for s in s_surfs:
            self.screen.blit(s, ((WIDTH - s.get_width()) // 2, y))
            y += s.get_height() + 6

    def draw_menu(self) -> None:
        self.screen.fill(COLOR_BG)
        self.draw_grid()

        title = self.font_title.render("SNAKE", True, COLOR_TEXT)
        self.screen.blit(title, ((WIDTH - title.get_width()) // 2, 60))

        # Lista de items
        base_y = 160
        spacing = 44
        for i, (label, values) in enumerate(self.menu_items):
            y = base_y + i * spacing
            if label == "Mode":
                val = self.mode
                text = f"Mode: {val}"
            elif label == "Wrap":
                val = "on" if self.wrap_on else "off"
                text = f"Wrap: {val}"
            elif label == "Sound":
                val = "on" if (self.sound.enabled and self.sound.ok) else "off"
                text = f"Sound: {val}"
            else:
                text = label

            surf = self.font_menu.render(text, True, COLOR_TEXT)
            x = (WIDTH - surf.get_width()) // 2
            if i == self.menu_index:
                # indicador simple de selección
                pygame.draw.rect(self.screen, COLOR_GRID, pygame.Rect(x - 16, y - 6, surf.get_width() + 32, surf.get_height() + 12), border_radius=10)
            self.screen.blit(surf, (x, y))

        # Instrucciones
        hint = self.font_hud.render("↑/↓ seleccionar  |  ←/→ cambiar  |  ENTER aceptar  |  ESC salir", True, COLOR_TEXT)
        self.screen.blit(hint, ((WIDTH - hint.get_width()) // 2, HEIGHT - 36))

        # Info breve
        info = self.font_hud.render("Modos: easy/normal/hard. Wrap: atraviesa bordes en ON.", True, COLOR_TEXT)
        self.screen.blit(info, ((WIDTH - info.get_width()) // 2, HEIGHT - 60))

        pygame.display.flip()


# =========================
# == CLI y arranque      ==
# =========================

def parse_args() -> tuple[str, bool]:
    """Parsea argumentos CLI con valores por defecto razonables."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--mode", choices=["easy", "normal", "hard"], default="normal")
    parser.add_argument("--wrap", choices=["on", "off"], default="off")
    parser.add_argument("-h", "--help", action="store_true")
    args, _ = parser.parse_known_args()

    if args.help:
        print("Uso: python snake.py [--mode easy|normal|hard] [--wrap on|off]")
        print("Por defecto: --mode normal --wrap off")
    return args.mode, (args.wrap == "on")


def main() -> None:
    mode, wrap_on = parse_args()
    cfg = safe_load_highscores()

    # Si el archivo tiene flags guardados, solo afectan al sonido (modo/wrap respetan CLI)
    game = Game(mode=mode, wrap_on=wrap_on, cfg_loaded=cfg)
    game.run()


if __name__ == "__main__":
    main()