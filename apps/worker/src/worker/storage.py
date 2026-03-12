"""Worker 使用的原始檔儲存讀取抽象。"""

from abc import ABC, abstractmethod
from pathlib import Path

from minio import Minio
from minio.error import S3Error

from worker.core.settings import WorkerSettings


class StorageError(RuntimeError):
    """代表儲存讀取失敗。"""


class ObjectStorageReader(ABC):
    """提供 worker 讀取文件原始檔的最小介面。"""

    @abstractmethod
    def get_object(self, *, object_key: str) -> bytes:
        """讀取指定物件內容。

        參數：
        - `object_key`：物件儲存中的鍵值。

        回傳：
        - `bytes`：讀取出的原始位元組內容。
        """


class MinioObjectStorageReader(ObjectStorageReader):
    """從 MinIO/S3 API 讀取文件內容。"""

    def __init__(self, settings: WorkerSettings) -> None:
        """初始化 MinIO client。

        參數：
        - `settings`：包含 MinIO endpoint、bucket 與憑證設定的 worker 設定。

        回傳：
        - `None`：此建構子只負責初始化儲存 client。
        """

        endpoint = settings.minio_endpoint.removeprefix("http://").removeprefix("https://")
        self._bucket = settings.minio_bucket
        self._client = Minio(
            endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )

    def get_object(self, *, object_key: str) -> bytes:
        """讀取既有物件。

        參數：
        - `object_key`：物件儲存中的鍵值。

        回傳：
        - `bytes`：讀取出的原始位元組內容。
        """

        try:
            response = self._client.get_object(self._bucket, object_key)
            try:
                return response.read()
            finally:
                response.close()
                response.release_conn()
        except S3Error as exc:
            raise StorageError("無法讀取物件儲存。") from exc


class FilesystemObjectStorageReader(ObjectStorageReader):
    """從本機檔案系統讀取文件內容。"""

    def __init__(self, settings: WorkerSettings) -> None:
        """初始化檔案系統儲存根目錄。

        參數：
        - `settings`：包含本機儲存路徑的 worker 設定。

        回傳：
        - `None`：此建構子只負責初始化儲存根目錄。
        """

        self._base_path = Path(settings.local_storage_path)

    def get_object(self, *, object_key: str) -> bytes:
        """讀取指定物件內容。

        參數：
        - `object_key`：檔案系統儲存中的相對鍵值。

        回傳：
        - `bytes`：讀取出的原始位元組內容。
        """

        return (self._base_path / object_key).read_bytes()


def build_object_storage_reader(settings: WorkerSettings) -> ObjectStorageReader:
    """依設定建立 worker 使用的物件讀取器。

    參數：
    - `settings`：包含 storage backend 與儲存設定的 worker 設定。

    回傳：
    - `ObjectStorageReader`：符合目前執行模式的物件讀取器。
    """

    if settings.storage_backend == "filesystem":
        return FilesystemObjectStorageReader(settings=settings)
    return MinioObjectStorageReader(settings=settings)
