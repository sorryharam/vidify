class Helper:
    @staticmethod
    def validate_filename(filename: str) -> str:
        """Очищает имя файла от недопустимых символов."""
        invalid_chars = '<>:\":/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        return filename