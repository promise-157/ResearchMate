"""Optional local Tesseract OCR adapter; never sends an image externally."""
import shutil
import subprocess


PROCESSOR_NAME = "local_tesseract"
PROCESSOR_VERSION = "2"
PREFERRED_LANGUAGES = ("eng", "chi_sim")


class LocalOCRProcessor:
    def extract(self, image_path: str) -> str:
        executable = shutil.which("tesseract")
        if not executable:
            raise RuntimeError("未找到本地 tesseract；请安装后重试，图片不会发送到外部服务")
        languages = self._available_languages(executable)
        selected = [language for language in PREFERRED_LANGUAGES if language in languages]
        language_args = ["-l", "+".join(selected)] if selected else []
        result = subprocess.run(
            [executable, image_path, "stdout", *language_args], capture_output=True, text=True,
            timeout=120, check=False,
        )
        if result.returncode != 0:
            raise RuntimeError((result.stderr or "本地 OCR 失败").strip()[:1000])
        return result.stdout.strip()

    @staticmethod
    def _available_languages(executable: str) -> set[str]:
        try:
            result = subprocess.run(
                [executable, "--list-langs"], capture_output=True, text=True,
                timeout=10, check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return set()
        if result.returncode != 0:
            return set()
        return {
            line.strip() for line in result.stdout.splitlines()
            if line.strip() and not line.startswith("List of available languages")
        }
