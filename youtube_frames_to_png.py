#!/usr/bin/env python3
import os
import sys
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Tuple

# ---- Dependencias de Python -------------------------------------------------
try:
    from yt_dlp import YoutubeDL
except ImportError:
    print("Falta 'yt-dlp'. Instala con: pip install yt-dlp", file=sys.stderr)
    sys.exit(1)

try:
    from tqdm import tqdm
except ImportError:
    print("Falta 'tqdm'. Instala con: pip install tqdm", file=sys.stderr)
    sys.exit(1)


# ---- Utilidades --------------------------------------------------------------
def ask(prompt: str, default: Optional[str] = None) -> str:
    s = input(f"{prompt}" + (f" [{default}]" if default else "") + ": ").strip()
    return s or (default or "")


def find_ffmpeg_tools() -> Tuple[str, str, Optional[str]]:
    """Devuelve (ffmpeg_path, ffprobe_path, ff_dir or None). Lanza si faltan."""
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise FileNotFoundError(
            "No se encontraron 'ffmpeg' y/o 'ffprobe' en el PATH.\n"
            "→ Instala FFmpeg (incluye ambos) y reinicia la terminal.\n"
            "   Windows: winget install Gyan.FFmpeg\n"
            "   Linux:   apt-get install ffmpeg  |  dnf install ffmpeg"
        )
    ff_dir = str(Path(ffmpeg).parent)
    return ffmpeg, ffprobe, ff_dir


def to_sec(ts: str) -> float:
    """Convierte HH:MM:SS(.ms) a segundos (float)."""
    if not ts:
        return 0.0
    parts = ts.split(":")
    parts = [float(p) for p in parts]
    while len(parts) < 3:
        parts.insert(0, 0.0)
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


# ---- Descarga con yt-dlp -----------------------------------------------------
def download_youtube(url: str, tmpdir: Path, ff_dir: Optional[str]) -> Path:
    """Descarga el video con progreso y devuelve la ruta del MP4 resultante."""
    outtmpl = str(tmpdir / "%(title).200B.%(ext)s")

    pbar = None

    def hook(d):
        nonlocal pbar
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            downloaded = d.get("downloaded_bytes", 0)
            if pbar is None:
                # Si conocemos el total, barra normal; si no, barra indeterminada (total=None)
                pbar = tqdm(total=total if total else None, unit="B", unit_scale=True,
                            desc="Descargando", leave=False)
            if total and pbar.total != total:
                pbar.total = total
            if downloaded is not None:
                # Actualizamos en base a diferencia
                inc = downloaded - (pbar.n or 0)
                if inc > 0:
                    pbar.update(inc)
        elif d["status"] == "finished":
            if pbar:
                pbar.close()

    ydl_opts = {
        "outtmpl": outtmpl,
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [hook],
    }
    if ff_dir:
        # Ayuda a yt-dlp a encontrar ffmpeg/ffprobe en Windows
        ydl_opts["ffmpeg_location"] = ff_dir

    with YoutubeDL(ydl_opts) as ydl:
        ydl.extract_info(url, download=True)

    mp4s = sorted(tmpdir.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not mp4s:
        raise FileNotFoundError(
            "No se encontró el MP4 descargado. Verifica que FFmpeg (ffmpeg y ffprobe) esté instalado y accesible."
        )
    return mp4s[0]


# ---- Probe de video con ffprobe ----------------------------------------------
def probe_video_info(video_path: Path) -> Tuple[float, float]:
    """Devuelve (duración_seg, fps) usando ffprobe."""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=r_frame_rate",
        "-show_entries", "format=duration",
        "-of", "json",
        str(video_path),
    ]
    out = subprocess.check_output(cmd, text=True)
    data = json.loads(out)
    duration = float(data.get("format", {}).get("duration", 0.0))
    fps_str = data.get("streams", [{}])[0].get("r_frame_rate", "0/0")
    try:
        num, den = fps_str.split("/")
        fps = float(num) / float(den) if float(den) != 0 else 0.0
    except Exception:
        fps = 0.0
    return duration, fps


# ---- Extracción de frames con progreso ---------------------------------------
def ffmpeg_extract_frames(video_path: Path, output_dir: Path, every_n: int = 1,
                          start_ts: Optional[str] = None, end_ts: Optional[str] = None) -> None:
    """Extrae frames a PNG con barra de progreso estimada o indeterminada."""
    output_dir.mkdir(parents=True, exist_ok=True)
    out_pattern = str(output_dir / "frame_%06d.png")

    # Estimación (si es posible)
    dur, fps = probe_video_info(video_path)
    start_s = to_sec(start_ts) if start_ts else 0.0
    if end_ts:
        end_s = to_sec(end_ts)
    else:
        end_s = dur if dur > 0 else 0.0

    effective_duration = max(0.0, (end_s - start_s) if end_ts else (dur - start_s if dur > 0 else 0.0))
    est_frames = int((effective_duration * fps) / max(1, every_n)) if fps > 0 and effective_duration > 0 else 0

    # Filtro para extraer 1 de cada N
    vf = []
    if every_n > 1:
        vf.append(f"select='not(mod(n\\,{every_n}))',setpts=N/FRAME_RATE/TB")

    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-progress", "pipe:1"]
    if start_ts:
        cmd += ["-ss", start_ts]
    cmd += ["-i", str(video_path)]
    if end_ts:
        cmd += ["-to", end_ts]
    if vf:
        cmd += ["-vf", ",".join(vf), "-vsync", "vfr"]
    else:
        cmd += ["-vsync", "0"]
    cmd += ["-start_number", "1", out_pattern]

    # Barra de progreso
    if est_frames > 0:
        pbar = tqdm(total=est_frames, unit="frame", desc="Extrayendo")
    else:
        # Desconocido: barra indeterminada + conteo de frames
        pbar = tqdm(total=None, unit="frame", desc="Extrayendo")

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    last_frames_counted = 0
    last_out_time = 0.0

    try:
        for line in proc.stdout:
            line = line.strip()
            # ffmpeg -progress emite pares key=value, p.ej.:
            # frame=123
            # out_time_ms=1234567
            # progress=continue|end
            if line.startswith("frame="):
                try:
                    cur = int(line.split("=", 1)[1])
                    if est_frames == 0:
                        # Barra indeterminada: actualizamos por diferencia
                        inc = cur - last_frames_counted
                        if inc > 0:
                            pbar.update(inc)
                            last_frames_counted = cur
                except:
                    pass
            elif line.startswith("out_time_ms=") and est_frames > 0:
                try:
                    ms = int(line.split("=", 1)[1])
                    seconds = ms / 1_000_000.0
                    # Aproximamos frames procesados por tiempo
                    est_now = int((seconds - last_out_time) * (fps / max(1, every_n)))
                    if est_now > 0:
                        pbar.update(est_now)
                        last_out_time = seconds
                except:
                    pass
    finally:
        proc.wait()
        # Completar si quedó corto por redondeos
        if est_frames > 0 and pbar.n < est_frames:
            pbar.update(est_frames - pbar.n)
        pbar.close()

    if proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, cmd)


# ---- Main --------------------------------------------------------------------
def main():
    print("=== Extraer fotogramas PNG desde un video de YouTube ===\n")

    # Verifica ffmpeg + ffprobe
    try:
        _, _, ff_dir = find_ffmpeg_tools()
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        sys.exit(2)

    url = ask("Pega el URL del video de YouTube")
    if not url:
        print("URL vacío. Saliendo.", file=sys.stderr)
        sys.exit(1)

    out_dir = Path(ask("Carpeta de salida para las imágenes PNG",
                       default=str(Path.cwd() / "frames_output"))).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        every_n = int(ask("Extraer 1 de cada N frames (1 = todos)", default="1"))
        if every_n < 1:
            every_n = 1
    except ValueError:
        every_n = 1

    start_ts = ask("Tiempo de inicio (HH:MM:SS o vacío para todo)", default="").strip() or None
    end_ts = ask("Tiempo de fin (HH:MM:SS o vacío para todo)", default="").strip() or None

    with tempfile.TemporaryDirectory() as td:
        tmpdir = Path(td)
        print("\nDescargando video con yt-dlp (puede tardar un poco)...")
        try:
            video_path = download_youtube(url, tmpdir, ff_dir)
        except FileNotFoundError as e:
            print(f"Error al descargar el video: {e}", file=sys.stderr)
            sys.exit(3)
        except Exception as e:
            print("Error al descargar el video:", file=sys.stderr)
            print(str(e), file=sys.stderr)
            print("\nSugerencias:", file=sys.stderr)
            print("  1) En Windows, instala FFmpeg: winget install Gyan.FFmpeg", file=sys.stderr)
            print("  2) Asegúrate de que 'ffmpeg' y 'ffprobe' estén en el PATH y reinicia la terminal.", file=sys.stderr)
            print("  3) Verifica que puedas ejecutar: ffmpeg -version  y  ffprobe -version", file=sys.stderr)
            sys.exit(3)

        print(f"Video descargado: {video_path.name}")
        print("Extrayendo fotogramas a PNG...")
        try:
            ffmpeg_extract_frames(video_path, out_dir, every_n=every_n, start_ts=start_ts, end_ts=end_ts)
        except subprocess.CalledProcessError:
            print("FFmpeg reportó un error al extraer los frames.", file=sys.stderr)
            sys.exit(4)

    print(f"\nListo. Imágenes PNG en: {out_dir}")
    print("Ejemplos: frame_000001.png, frame_000002.png, ...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelado por el usuario.")
