"""Worker ingest 流程使用的最小 parser router。"""


# 本 phase 真正支援解析的副檔名。
SUPPORTED_TEXT_EXTENSIONS = {".txt", ".md"}


def parse_document(*, file_name: str, payload: bytes) -> str:
    """依副檔名選擇 parser，並回傳最小文字內容。

    參數：
    - `file_name`：使用者上傳時的原始檔名。
    - `payload`：從物件儲存讀出的原始位元組內容。

    回傳：
    - `str`：解析後的最小文字內容。
    """

    lower_name = file_name.lower()
    if any(lower_name.endswith(extension) for extension in SUPPORTED_TEXT_EXTENSIONS):
        text = payload.decode("utf-8")
        if not text.strip():
            raise ValueError("文件內容不可為空白。")
        return text
    raise ValueError("目前尚未支援此檔案類型的解析。")
