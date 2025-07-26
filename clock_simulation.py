import sys
import math
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QPainter, QPen, QBrush, QFont
from PyQt6.QtCore import QPointF

class ClockWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.current_minutes = 0  # 从6:00开始经过的分钟数
        self.start_hour = 6  # 起始时间6点
        self.setMinimumSize(400, 400)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 获取窗口中心和半径
        center = QPointF(self.width() / 2, self.height() / 2)
        radius = min(self.width(), self.height()) / 2 - 20
        
        # 绘制时钟外圈
        painter.setPen(QPen(Qt.GlobalColor.black, 3))
        painter.drawEllipse(center, radius, radius)
        
        # 绘制时钟刻度
        painter.setPen(QPen(Qt.GlobalColor.black, 2))
        for i in range(12):
            angle = i * 30 * math.pi / 180  # 每小时30度
            x1 = center.x() + (radius - 20) * math.sin(angle)
            y1 = center.y() - (radius - 20) * math.cos(angle)
            x2 = center.x() + radius * math.sin(angle)
            y2 = center.y() - radius * math.cos(angle)
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
            
            # 绘制数字
            painter.setFont(QFont("Arial", 12, QFont.Weight.Bold))
            text_x = center.x() + (radius - 35) * math.sin(angle) - 8
            text_y = center.y() - (radius - 35) * math.cos(angle) + 5
            hour_num = 12 if i == 0 else i
            painter.drawText(QPointF(text_x, text_y), str(hour_num))
        
        # 计算当前时间
        total_minutes = self.start_hour * 60 + self.current_minutes
        current_hour = (total_minutes // 60) % 12
        current_minute = total_minutes % 60
        
        # 计算指针角度
        # 分针：每分钟6度
        minute_angle = current_minute * 6 * math.pi / 180
        
        # 时针：每小时30度，每分钟0.5度
        hour_angle = (current_hour * 30 + current_minute * 0.5) * math.pi / 180
        
        # 绘制时针
        painter.setPen(QPen(Qt.GlobalColor.red, 6))
        hour_length = radius * 0.5
        hour_x = center.x() + hour_length * math.sin(hour_angle)
        hour_y = center.y() - hour_length * math.cos(hour_angle)
        painter.drawLine(center, QPointF(hour_x, hour_y))
        
        # 绘制分针
        painter.setPen(QPen(Qt.GlobalColor.blue, 4))
        minute_length = radius * 0.7
        minute_x = center.x() + minute_length * math.sin(minute_angle)
        minute_y = center.y() - minute_length * math.cos(minute_angle)
        painter.drawLine(center, QPointF(minute_x, minute_y))
        
        # 绘制中心点
        painter.setBrush(QBrush(Qt.GlobalColor.black))
        painter.drawEllipse(center, 8, 8)
        
        # 检查是否重合（角度差小于1度）
        angle_diff = abs(hour_angle - minute_angle)
        if angle_diff > math.pi:
            angle_diff = 2 * math.pi - angle_diff
        
        if angle_diff < math.pi / 180:  # 小于1度认为重合
            painter.setPen(QPen(Qt.GlobalColor.green, 8))
            painter.setFont(QFont("Arial", 16, QFont.Weight.Bold))
            painter.drawText(QPointF(center.x() - 50, center.y() + radius + 30), "指针重合!")

class ClockSimulation(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("时钟指针重合模拟")
        self.setGeometry(100, 100, 600, 700)
        
        # 创建主窗口部件
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        # 创建时钟部件
        self.clock_widget = ClockWidget()
        layout.addWidget(self.clock_widget)
        
        # 创建控制面板
        control_layout = QHBoxLayout()
        
        self.start_button = QPushButton("开始模拟")
        self.start_button.clicked.connect(self.start_simulation)
        control_layout.addWidget(self.start_button)
        
        self.stop_button = QPushButton("停止")
        self.stop_button.clicked.connect(self.stop_simulation)
        control_layout.addWidget(self.stop_button)
        
        self.reset_button = QPushButton("重置")
        self.reset_button.clicked.connect(self.reset_simulation)
        control_layout.addWidget(self.reset_button)
        
        layout.addLayout(control_layout)
        
        # 创建信息显示
        info_layout = QVBoxLayout()
        
        self.time_label = QLabel("当前时间: 6:00:00")
        self.time_label.setFont(QFont("Arial", 14))
        info_layout.addWidget(self.time_label)
        
        self.elapsed_label = QLabel("经过时间: 0 分钟")
        self.elapsed_label.setFont(QFont("Arial", 14))
        info_layout.addWidget(self.elapsed_label)
        
        self.result_label = QLabel("理论计算结果: 32.727... 分钟")
        self.result_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.result_label.setStyleSheet("color: red;")
        info_layout.addWidget(self.result_label)
        
        self.explanation_label = QLabel(self.get_explanation())
        self.explanation_label.setFont(QFont("Arial", 10))
        self.explanation_label.setWordWrap(True)
        info_layout.addWidget(self.explanation_label)
        
        layout.addLayout(info_layout)
        
        # 创建定时器
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_clock)
        
        # 计算理论结果
        self.calculate_result()
        
    def get_explanation(self):
        return """
计算原理：
设从6点开始经过t分钟后指针首次重合。
• 分针速度：6°/分钟
• 时针速度：0.5°/分钟
• 6点时，时针指向6，分针指向12，相差180°

重合条件：分针追上时针
分针转过的角度 = 时针转过的角度 + 180°
6t = 0.5t + 180
5.5t = 180
t = 180/5.5 = 360/11 ≈ 32.727分钟
        """
    
    def calculate_result(self):
        # 计算精确结果
        result_minutes = 360 / 11  # 32.727...分钟
        result_seconds = (result_minutes % 1) * 60
        
        self.exact_result = result_minutes
        self.result_label.setText(f"理论计算结果: {result_minutes:.3f} 分钟 = 32分{result_seconds:.1f}秒")
    
    def start_simulation(self):
        self.timer.start(100)  # 每100毫秒更新一次
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
    
    def stop_simulation(self):
        self.timer.stop()
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
    
    def reset_simulation(self):
        self.timer.stop()
        self.clock_widget.current_minutes = 0
        self.clock_widget.update()
        self.update_labels()
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
    
    def update_clock(self):
        self.clock_widget.current_minutes += 0.1  # 每次增加0.1分钟
        self.clock_widget.update()
        self.update_labels()
        
        # 检查是否接近重合点
        if abs(self.clock_widget.current_minutes - self.exact_result) < 0.1:
            self.timer.stop()
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
    
    def update_labels(self):
        total_minutes = 6 * 60 + self.clock_widget.current_minutes
        hours = int(total_minutes // 60)
        minutes = int(total_minutes % 60)
        seconds = int((total_minutes % 1) * 60)
        
        self.time_label.setText(f"当前时间: {hours}:{minutes:02d}:{seconds:02d}")
        self.elapsed_label.setText(f"经过时间: {self.clock_widget.current_minutes:.1f} 分钟")

def main():
    app = QApplication(sys.argv)
    window = ClockSimulation()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()