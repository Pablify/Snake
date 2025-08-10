# 🐍 Snake — Juego clásico en Python

Este proyecto es una implementación del juego clásico **"Snake"** desarrollada en **Python** usando la librería `pygame`.  
Todo el juego está contenido en un único archivo: [`snake.py`](snake.py).  

El objetivo es controlar una serpiente que crece al comer comida, evitando chocar contra las paredes (según configuración) o contra sí misma.  
Incluye un sistema de **puntuaciones máximas**, **niveles de dificultad**, **sonidos opcionales** y **modo de juego con o sin atravesar bordes (wrap)**.

---

## 🎮 Características

- **Modos de dificultad:** `easy`, `normal`, `hard` (velocidad base distinta y límites de FPS diferentes).
- **Modo wrap:** ON para atravesar bordes y aparecer al lado opuesto; OFF para colisionar con paredes.
- **Comida normal** (+10 puntos, +1 longitud) y **comida dorada** (+30 puntos, +2 longitud, tiempo limitado).
- **Aumento progresivo de velocidad** cada cierto número de puntos.
- **Sistema de récords persistente** guardado en `snake_highscores.json` (se crea automáticamente).
- **Menú interactivo** con navegación por teclado.
- **Sonidos simples integrados** sin necesidad de archivos externos (pueden activarse/desactivarse).
- **Todo en un solo script `.py`** para facilidad de uso y portabilidad.

---

## 📦 Requisitos

- **Python** 3.10 o superior  
- Librería **pygame** instalada:
```bash
pip install pygame
````

---

## 🚀 Ejecución

Clonar el repositorio:

```bash
git clone https://github.com/Pablify/Snake.git
cd Snake
```

Ejecutar el juego:

```bash
python snake.py [--mode easy|normal|hard] [--wrap on|off]
```

### Parámetros opcionales:

* `--mode`: dificultad inicial (`easy`, `normal`, `hard`). Por defecto: `normal`.
* `--wrap`: `on` para atravesar bordes, `off` para paredes sólidas. Por defecto: `off`.

Ejemplo:

```bash
python snake.py --mode hard --wrap on
```

---

## ⌨️ Controles

**En juego:**

* `↑` / `↓` / `←` / `→` o `W` / `A` / `S` / `D`: mover.
* `P`: pausar / reanudar.
* `R`: reiniciar la partida.
* `M`: activar/desactivar sonido.
* `ESC`: volver al menú principal.

**En el menú:**

* `↑` / `↓`: seleccionar opción.
* `←` / `→`: cambiar valor.
* `ENTER`: confirmar.
* `ESC`: salir del juego.

---

## 🖥️ Archivos generados

* `snake_highscores.json` — guarda los récords y el estado del sonido.

  ```json
  {
    "sound": true,
    "records": {
      "easy_on": 120,
      "easy_off": 95,
      "normal_on": 150,
      "normal_off": 130,
      "hard_on": 110,
      "hard_off": 100
    }
  }
  ```

---

## 📂 Estructura del repositorio

```
Snake/
├── snake.py               # Script principal del juego
├── README.md              # Este archivo
└── LICENSE                # Licencia MIT
```

---

## 📝 Licencia

Este proyecto está licenciado bajo la licencia **MIT**.
Consulta el archivo [LICENSE](LICENSE) para más información.
