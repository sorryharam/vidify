class Helper:
    @staticmethod
    def validate_filename(filename: str) -> str:
        """Очищает имя файла от недопустимых символов."""
        invalid_chars = '<>:\":/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        return filename

    @staticmethod
    def get_file_extension(filename: str) -> str:
        """Возвращает расширение файла."""
        return filename.split('.')[-1] if '.' in filename else ''
