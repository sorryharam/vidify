"""
Общие виджеты для использования во всем приложении.
"""
from PyQt5.QtWidgets import QPushButton, QLabel
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap, QPainter, QColor, QPen


class Switch(QPushButton):
    """Переключатель в виде кнопки (выкл/вкл)."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setText('Выкл')
        self.setObjectName('switchBtn')
        self.setCheckable(True)
        self.setMinimumWidth(60)
        self.setMaximumWidth(60)
        self.toggled.connect(self._on_toggled)

    def _on_toggled(self, checked):
        self.setText('Вкл' if checked else 'Выкл')


class AspectFrameLabel(QLabel):
    """Виджет для отображения превью с сохранением пропорций."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._pixmap = None

    def setPixmap(self, pixmap):
        self._pixmap = pixmap
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Центрированное отображение превью
        if self._pixmap:
            widget_w, widget_h = self.width(), self.height()
            pm_w, pm_h = self._pixmap.width(), self._pixmap.height()
            scale = min(widget_w / pm_w, widget_h / pm_h)
            scaled_w, scaled_h = int(pm_w * scale), int(pm_h * scale)
            x = (widget_w - scaled_w) // 2
            y = (widget_h - scaled_h) // 2
            painter.drawPixmap(x, y, self._pixmap.scaled(scaled_w, scaled_h, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        
        painter.end() 