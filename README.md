# README

Extractor de fotogramas (PNG) desde un video de YouTube, compatible con **Windows** y **Linux**.  
El script:
- Solicita el **URL** del video de YouTube.
- Pide/crea la **carpeta de salida** donde se guardan las imágenes PNG.
- Descarga el video con **yt-dlp** (apoyándose en FFmpeg).
- Extrae **cada fotograma** a **PNG** con **FFmpeg**.
- Muestra **barra de progreso** tanto en la **descarga** como en la **extracción**.

---

## Características

- ✅ Soporta Windows y Linux
- ✅ Descarga el mejor `mp4` disponible (`bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best`)
- ✅ Barra de progreso durante la descarga (hook de **yt-dlp**)
- ✅ Barra de progreso durante la extracción de frames (estimación con **ffprobe** y `-progress` de **ffmpeg**)
- ✅ Permite extraer **todos** los frames o **1 de cada N** (`every_n`)
- ✅ Permite definir un **rango de tiempo** (`start_ts` / `end_ts`)
- ✅ Nombres de salida: `frame_000001.png`, `frame_000002.png`, …

---

## Requisitos

- **Python** 3.9+
- **yt-dlp** y **tqdm** (vía `pip`)
- **FFmpeg** (incluye `ffmpeg` y `ffprobe`) instalado y disponible en el `PATH`

### Instalar dependencias Python
```bash
pip install yt-dlp tqdm
```

### Instalar FFmpeg

- **Windows (PowerShell)**  
  Opción rápida:  
  ```powershell
  winget install Gyan.FFmpeg
  ```
  Luego **cierra y reabre** la terminal.

- **Debian/Ubuntu**  
  ```bash
  sudo apt-get update && sudo apt-get install -y ffmpeg
  ```

- **Fedora / RHEL / Oracle Linux**  
  ```bash
  sudo dnf install -y ffmpeg
  ```

- **Arch Linux**  
  ```bash
  sudo pacman -S ffmpeg
  ```

### Verificar instalación
```bash
ffmpeg -version
ffprobe -version
```
Si ambos comandos responden con versión, están en el `PATH`.

---

## Archivo principal

- **Nombre sugerido:** `youtube_frames_to_png.py`

---

## Ejecución

### Windows (PowerShell)
```powershell
python .\youtube_frames_to_png.py
```

### Linux
```bash
python3 ./youtube_frames_to_png.py
```

Al ejecutar, el script te pedirá:
1) **URL** del video de YouTube.  
2) **Carpeta de salida** (se crea si no existe).  
3) **Every N** frames (escribe `1` para **todos**).  
4) **Tiempo de inicio** `HH:MM:SS` (opcional).  
5) **Tiempo de fin** `HH:MM:SS` (opcional).  

> Ejemplo de tiempos: `00:01:00` a `00:02:30` para extraer del minuto 1 al 2:30.

---

## Ejemplos de uso

- **Extraer todos los frames** del video completo a la carpeta por defecto:
  - Every N = `1`
  - Inicio/Fin vacíos

- **Extraer 1 de cada 10 frames** entre 00:05:00 y 00:10:00:
  - Every N = `10`
  - Inicio = `00:05:00`
  - Fin = `00:10:00`

---

## ¿Cómo funciona internamente?

1. **Detección de FFmpeg**  
   La función `find_ffmpeg_tools()` verifica que `ffmpeg` y `ffprobe` existan en el `PATH`. Si faltan, el script se detiene con un mensaje claro.  
   Además, pasa la carpeta detectada a `yt-dlp` mediante `ffmpeg_location` (útil en Windows).

2. **Descarga con yt-dlp**  
   `download_youtube()` configura `yt-dlp` para descargar el mejor MP4 disponible y fusionar audio+video si es necesario.  
   Un **hook de progreso** actualiza una barra **tqdm** durante la descarga.

3. **Cálculo de duración y FPS**  
   `probe_video_info()` ejecuta `ffprobe -of json` para leer **duración** y **fps**. Con esto se calcula una **estimación** del número de frames a extraer.

4. **Extracción de frames**  
   `ffmpeg_extract_frames()` ejecuta `ffmpeg` con:
   - `-progress pipe:1` para leer avances
   - `-vf select='not(mod(n\,{every_n}))'` (si `every_n > 1`)
   - `-vsync vfr` cuando hay filtro `select`, de lo contrario `-vsync 0`
   - salida con patrón `frame_%06d.png`  
   Muestra una barra de progreso **determinada** si se pudo estimar la cantidad de frames, o **indeterminada** si no.

---

## API del script (funciones principales)

- `ask(prompt, default=None) -> str`  
  Utilidad para entradas por consola con valor por defecto.

- `find_ffmpeg_tools() -> (ffmpeg_path, ffprobe_path, ff_dir)`  
  Verifica que `ffmpeg` y `ffprobe` estén instalados y devuelve sus rutas.

- `to_sec(ts: str) -> float`  
  Convierte `HH:MM:SS(.ms)` a segundos `float`.

- `download_youtube(url: str, tmpdir: Path, ff_dir: Optional[str]) -> Path`  
  Descarga el video con **yt-dlp** (barra de progreso) y devuelve la ruta del `.mp4` final.

- `probe_video_info(video_path: Path) -> (duration_sec: float, fps: float)`  
  Interroga con **ffprobe** para obtener duración y FPS.

- `ffmpeg_extract_frames(video_path: Path, output_dir: Path, every_n: int = 1, start_ts: Optional[str] = None, end_ts: Optional[str] = None)`  
  Ejecuta **ffmpeg** para extraer los PNG; muestra barra de progreso.

- `main()`  
  Orquesta el flujo: inputs → verificación → descarga → extracción.

> **Comentarios en el código**: cada sección/función contiene comentarios explicativos del porqué y cómo se hacen las cosas (formato “bloque” arriba de cada sección y comentarios en línea en los puntos importantes).

---

## Nombrado de archivos de salida

Las imágenes se generan como:
```
frame_000001.png
frame_000002.png
...
```
Dentro de la carpeta de salida que indiques.

---

## Sugerencias de rendimiento

- Extraer **todos los frames** de videos largos puede generar **miles** de imágenes y consumir mucho espacio en disco. Considera:
  - Usar `every_n` = 2, 5, 10, 30…
  - Limitar el rango de tiempo con `start_ts`/`end_ts`
- Utiliza un disco rápido (SSD) para acelerar I/O.
- Evita rutas con espacios/caracteres extraños si tienes problemas en Windows.
- Cierra antivirus que inspeccionan en tiempo real si notas lentitud extrema al crear miles de archivos.

---

## Solución de problemas (FAQ)

**[WinError 2] El sistema no puede encontrar el archivo especificado**  
> Casi siempre indica que **yt-dlp** no pudo invocar `ffmpeg` o `ffprobe`.  
**Solución**: Instala FFmpeg e **incluye** `ffmpeg` y `ffprobe` en el `PATH`. Cierra/reabre la terminal.  
- Windows: `winget install Gyan.FFmpeg`  
- Verifica: `ffmpeg -version` y `ffprobe -version`

**No se descargó el MP4**  
- Asegúrate de que hay espacio en disco y conexión de red.
- Verifica que no haya bloqueos por proxy/firewall.
- Prueba actualizar yt-dlp: `python -m pip install -U yt-dlp`

**Se crean demasiadas imágenes / poco espacio**  
- Sube `every_n` (por ejemplo, 10 o 30).
- Limita el rango `start_ts`/`end_ts`.

**Rutas con tildes/espacios** (Windows)  
- Usa rutas cortas sin espacios o entrecomilla en consola si llamas manualmente a comandos.

**ffmpeg devuelve error en extracción**  
- Revisa que `start_ts` < `end_ts` y que ambos existan dentro de la duración.
- Verifica permisos de escritura en la carpeta destino.

---

## Compatibilidad

- **Windows 10/11** (PowerShell / CMD)
- **Linux** (Debian/Ubuntu, Fedora/RHEL/Oracle, Arch, etc.)
- **Python** 3.9 o superior

---

## Cambios recientes

- Verificación de `ffmpeg` y `ffprobe` al inicio.
- Barra de progreso en descarga (yt-dlp) y extracción (ffmpeg/ffprobe).
- Fixes de indentación y cálculos de tiempos.

---

## Roadmap (ideas futuras)

- Opción para **limitar FPS** (e.g., 1 fps)
- Exportar **CSV** con `frame_index` y `timestamp`
- Comprimir automáticamente las imágenes en `.zip`

---

## Créditos / Licencias

- **yt-dlp**: Licencia Unlicense/MIT-like (ver repo oficial).
- **FFmpeg**: Licencias LGPL/GPL según componentes habilitados.  
---
