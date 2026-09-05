from sentence_transformers import SentenceTransformer
from loguru import logger
from pathlib import Path
from app.config import settings


def load_embedding_model():
    model_path = Path(settings.embedding_model_path)
    model_name = settings.embedding_model_name

    # Si el modelo local existe, cargarlo directamente
    if model_path.exists():
        logger.info(f"🧠 Cargando embeddings desde {model_path}")
        try:
            model = SentenceTransformer(str(model_path))
            logger.success("✅ Embeddings cargados desde ruta local")
            return model
        except Exception as e:
            logger.warning(f"⚠️  Falló carga local: {e}")

    # Si no existe localmente o falló, descargar por nombre
    logger.info(f"🔄 Descargando embeddings '{model_name}'...")
    try:
        model = SentenceTransformer(model_name)
        model_path.parent.mkdir(parents=True, exist_ok=True)
        model.save(str(model_path))
        logger.success(f"✅ Embeddings descargados y guardados en {model_path}")
        return model
    except Exception as e:
        logger.error(f"❌ Error cargando embeddings: {e}")
        raise