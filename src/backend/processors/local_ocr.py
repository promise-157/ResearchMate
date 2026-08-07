"""Optional local Tesseract OCR adapter; never sends an image externally."""
import shutil
import subprocess


PROCESSOR_NAME = "local_tesseract"
PROCESSOR_VERSION = "1"


class LocalOCRProcessor:
    def extract(self, image_path: str) -> str:
        executable = shutil.which("tesseract")
        if not executable:
            raise RuntimeError("未找到本地 tesseract；请安装后重试，图片不会发送到外部服务")
        result = subprocess.run(
            [executable, image_path, "stdout"], capture_output=True, text=True,
            timeout=120, check=False,
        )
        if result.returncode != 0:
            raise RuntimeError((result.stderr or "本地 OCR 失败").strip()[:1000])
        return result.stdout.strip()
