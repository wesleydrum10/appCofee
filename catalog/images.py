from pathlib import PurePosixPath

from django.conf import settings
from django.core.files.storage import default_storage
from django.templatetags.static import static


def product_image_url(name):
    """Imagens fixas do catálogo são servidas com static, uploads usam storage."""
    if not name:
        return ""
    name = str(name)
    path = PurePosixPath(name)
    if len(path.parts) == 2 and path.parts[0] == "products":
        bundled = settings.BASE_DIR / "static" / "catalog" / path
        if bundled.is_file():
            return static(f"catalog/{name}")
    return default_storage.url(name)
