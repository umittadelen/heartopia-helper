import sys
import json
import time
import os
import ctypes
import pyautogui
import numpy as np
import mss
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QPushButton, 
                             QFileDialog, QLabel, QComboBox, QHBoxLayout, QDoubleSpinBox, QSpinBox)
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QImage

# Fix for 1:1 Pixel Mapping
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except:
    pass

pyautogui.FAILSAFE = True

class HeartopiaTool(QWidget):
    def __init__(self):
        super().__init__()
        self.data = None
        self.cell_size = 11.8 # Estimated default
        
        # Overlay Setup
        self.overlay = QWidget()
        self.overlay.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.overlay.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.overlay.paintEvent = self.paint_overlay
        
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Heartopia Guarded Painter")
        self.setFixedWidth(380)
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)
        layout = QVBoxLayout()

        self.lbl_status = QLabel("<b>Status:</b> Load JSON and Align.")
        layout.addWidget(self.lbl_status)

        btn_load = QPushButton("📂 Load JSON Plan")
        btn_load.clicked.connect(self.load_json)
        layout.addWidget(btn_load)

        # 1. AUTO ALIGN
        self.btn_scan = QPushButton("🎯 AUTO-DETECT RULER")
        self.btn_scan.setStyleSheet("background-color: #3498db; color: white; font-weight: bold; height: 35px;")
        self.btn_scan.clicked.connect(self.detect_corner)
        layout.addWidget(self.btn_scan)

        # 2. MANUAL OFFSETS (Using your requested numbers)
        layout.addWidget(QLabel("<br><b>Origin (Top-Left of Art):</b>"))
        n_layout = QHBoxLayout()
        self.sb_ox = QDoubleSpinBox(); self.sb_oy = QDoubleSpinBox()
        self.sb_ox.setRange(0, 5000); self.sb_ox.setValue(437.0) 
        self.sb_oy.setRange(0, 5000); self.sb_oy.setValue(306.5)
        self.sb_ox.setDecimals(1); self.sb_oy.setDecimals(1)
        self.sb_ox.valueChanged.connect(self.sync)
        self.sb_oy.valueChanged.connect(self.sync)
        n_layout.addWidget(QLabel("X:")); n_layout.addWidget(self.sb_ox)
        n_layout.addWidget(QLabel("Y:")); n_layout.addWidget(self.sb_oy)
        layout.addLayout(n_layout)

        # 3. SCALE
        s_layout = QHBoxLayout()
        self.sb_scale = QDoubleSpinBox()
        self.sb_scale.setRange(1.0, 100.0); self.sb_scale.setValue(11.8); self.sb_scale.setDecimals(4)
        self.sb_scale.valueChanged.connect(self.sync)
        s_layout.addWidget(QLabel("Cell Size:")); s_layout.addWidget(self.sb_scale)
        layout.addLayout(s_layout)

        # 4. CANVAS GUARD (SAFETY)
        layout.addWidget(QLabel("<br><b>Canvas Guard (Don't click outside this area):</b>"))
        g_layout = QHBoxLayout()
        self.sb_gw = QSpinBox(); self.sb_gh = QSpinBox()
        self.sb_gw.setRange(10, 2000); self.sb_gw.setValue(150) # Set to 150 cells
        self.sb_gh.setRange(10, 2000); self.sb_gh.setValue(150)
        g_layout.addWidget(QLabel("Width (Cells):")); g_layout.addWidget(self.sb_gw)
        g_layout.addWidget(QLabel("Height (Cells):")); g_layout.addWidget(self.sb_gh)
        layout.addLayout(g_layout)

        # 5. PAINT
        self.combo_color = QComboBox()
        self.combo_color.currentIndexChanged.connect(self.overlay.update)
        layout.addWidget(self.combo_color)

        btn_start = QPushButton("🚀 START PAINTING")
        btn_start.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; height: 50px;")
        btn_start.clicked.connect(self.start_painting)
        layout.addWidget(btn_start)

        self.setLayout(layout)

    def load_json(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Plan", "", "JSON Files (*.json)")
        if path:
            with open(path, 'r') as f: self.data = json.load(f)
            self.combo_color.clear()
            for i, c in enumerate(self.data['colors']):
                self.combo_color.addItem(f"Color {i} ({c['hex']})", i)

    def is_black(self, bgr): return bgr[2] < 30 and bgr[1] < 30 and bgr[0] < 30
    def is_yellow(self, bgr): return bgr[2] > 200 and bgr[1] > 180 and bgr[0] < 100

    def detect_corner(self):
        self.hide(); time.sleep(1.0)
        with mss.MSS() as sct:
            img = np.array(sct.grab(sct.monitors[1]))
            h, w, _ = img.shape
            found_x, found_y = -1, -1
            # Scan top-left area only
            for y in range(0, int(h*0.5), 2):
                for x in range(0, int(w*0.5), 2):
                    if self.is_black(img[y, x]):
                        cx, cy = x, y
                        while cy > 0 and self.is_black(img[cy-1, cx]): cy -= 1
                        while cx > 0 and self.is_black(img[cy, cx-1]): cx -= 1
                        found_x, found_y = cx, cy
                        break
                if found_x != -1: break

            if found_x != -1:
                # Measure ruler to get scale
                edges = [found_x]
                look_blk = False
                for tx in range(found_x, found_x + 600):
                    px = img[found_y + 5, tx]
                    if (self.is_black(px) if look_blk else self.is_yellow(px)):
                        edges.append(tx); look_blk = not look_blk
                    if len(edges) >= 11: break
                
                if len(edges) >= 11:
                    self.sb_scale.setValue((edges[10] - edges[0]) / 10.0)
                    self.sb_ox.setValue(float(found_x))
                    self.sb_oy.setValue(float(found_y))
                    self.overlay.setGeometry(0, 0, w, h)
                    self.overlay.show()
        self.show()

    def sync(self):
        self.overlay.update()

    def paint_overlay(self, event):
        if not self.data: return
        painter = QPainter(self.overlay)
        idx = self.combo_color.currentIndex()
        if idx < 0: return
        
        color_data = self.data['colors'][idx]
        cell_size = self.sb_scale.value()
        ox, oy = self.sb_ox.value(), self.sb_oy.value()
        
        painter.setBrush(QColor(color_data['hex']))
        painter.setPen(QPen(Qt.GlobalColor.white, 0.5))

        # Respect Canvas Guard bounds in display
        max_w, max_h = self.sb_gw.value(), self.sb_gh.value()

        for px in color_data['pixels']:
            if px[0] >= max_w or px[1] >= max_h: continue # Guard
            
            tx = ox + (px[0] * cell_size)
            ty = oy + (px[1] * cell_size)
            if -10 < tx < self.overlay.width() and -10 < ty < self.overlay.height():
                painter.drawRect(QRectF(tx, ty, cell_size, cell_size))

    def start_painting(self):
        if not self.data: return
        self.overlay.hide()
        time.sleep(1)
        
        pixels = self.data['colors'][self.combo_color.currentIndex()]['pixels']
        cell_size = self.sb_scale.value()
        ox, oy = self.sb_ox.value(), self.sb_oy.value()
        max_w, max_h = self.sb_gw.value(), self.sb_gh.value()

        pyautogui.PAUSE = 0.001 
        for px in pixels:
            # CANVAS GUARD CHECK
            if px[0] >= max_w or px[1] >= max_h: continue

            tx = int(ox + (px[0] * cell_size) + (cell_size / 2.0))
            ty = int(oy + (px[1] * cell_size) + (cell_size / 2.0))
            
            pyautogui.mouseDown(tx, ty)
            time.sleep(0.005)
            pyautogui.mouseUp(tx, ty)

        self.overlay.show()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    tool = HeartopiaTool()
    tool.show()
    sys.exit(app.exec())