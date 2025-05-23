"""
Файл настройки для установки пакета vidify.
"""
from setuptools import setup, find_packages

setup(
    name="vidify",
    version="1.0.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,
    install_requires=[
        "PyQt5>=5.15.0",
        "yt-dlp>=2025.3.31",
    ],
    entry_points={
        'console_scripts': [
            'vidify=vidify.ui.app:run_app',
        ],
    },
    python_requires=">=3.7",
    author="vidify Team",
    author_email="example@example.com",
    description="Приложение для скачивания, уникализации и загрузки видео",
    keywords="video, download, processing, youtube",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: End Users/Desktop",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
) 