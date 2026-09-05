import whisper
from loguru import logger
from pathlib import Path
from app.config import settings


def load_whisper_model():
    model_path = Path(settings.whisper_model_path)

    # Si el modelo local existe, cargarlo directamente
    if model_path.exists():
        logger.info(f"🎙️ Cargando Whisper desde {model_path}")
        model = whisper.load_model(str(model_path))
        logger.success("✅ Whisper cargado correctamente")
        return model

    # Si no existe, intentar descargar por nombre del modelo
    logger.warning(f"⚠️  Modelo local no encontrado: {model_path}")
    logger.info(f"🔄 Descargando Whisper '{settings.whisper_model_size}'...")

    try:
        model = whisper.load_model(settings.whisper_model_size)
        # Guardar para futuras ejecuciones
        model_path.parent.mkdir(parents=True, exist_ok=True)
        model.save(str(model_path))
        logger.success(f"✅ Whisper descargado y guardado en {model_path}")
        return model
    except Exception as e:
        logger.error(f"❌ Error descargando Whisper: {e}")
        raise FileNotFoundError(
            f"No se pudo cargar ni descargar el modelo Whisper.\n"
            f"Ruta intentada: {model_path}\n"
            f"Modelo solicitado: {settings.whisper_model_size}"
        )
