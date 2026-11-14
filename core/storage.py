from django.core.exceptions import ImproperlyConfigured
from django.core.files.storage import FileSystemStorage


class ExternalMediaRequiredStorage(FileSystemStorage):
    """Evita aceitar uploads que seriam perdidos no disco efêmero de produção."""

    def _save(self, name, content):
        raise ImproperlyConfigured(
            "Uploads de produção exigem armazenamento externo. "
            "Configure MEDIA_STORAGE_BACKEND e MEDIA_STORAGE_OPTIONS antes de enviar arquivos."
        )
