import sys
import paramiko
import time
from scp import SCPClient
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton,
    QLineEdit, QFileDialog, QTextEdit, QMessageBox, QStackedWidget, QHBoxLayout
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt, QThread, pyqtSignal


# ============================================================
#                        线程工作类（优化版）
# ============================================================

class OperationThread(QThread):
    """集成化操作线程"""
    progress = pyqtSignal(str)  # 进度信号
    finished = pyqtSignal(bool)  # 完成信号（True=成功，False=失败）
    result_ready = pyqtSignal(str)  # 结果文件路径

    def __init__(self, ssh_info, image_paths):
        super().__init__()
        self.ssh_info = ssh_info  # 服务器连接信息
        self.image_paths = image_paths
        self.ssh = None
        self.should_stop = False  # 异常终止标志

    def run(self):
        try:
            # 步骤1：建立SSH连接
            self.progress.emit("正在连接服务器...")
            self.ssh = self.connect_ssh()
            if not self.ssh: return

            # 步骤2：上传图片
            if not self.upload_images():
                self.finished.emit(False)
                return

            # 步骤3：执行处理
            if not self.process_images():
                self.finished.emit(False)
                return

            # 步骤4：下载结果
            result_path = self.download_result()
            if result_path:
                self.result_ready.emit(result_path)
                self.finished.emit(True)
            else:
                self.finished.emit(False)

        except Exception as e:
            self.progress.emit(f"❌ 发生错误: {str(e)}")
            self.finished.emit(False)

    def connect_ssh(self):
        """建立SSH连接"""
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(**self.ssh_info, timeout=15)
            self.progress.emit("✅ 服务器连接成功")
            return ssh
        except Exception as e:
            self.progress.emit(f"❌ 连接失败: {str(e)}")
            return None

    def upload_images(self):
        """上传图片"""
        try:
            with SCPClient(self.ssh.get_transport()) as scp:
                # 上传input1
                self.progress.emit("上传input1图片...")
                self.ssh.exec_command("rm -rf ~/autodl-tmp/UDIS-D/testing/input1/*")
                scp.put(self.image_paths[1], "~/autodl-tmp/UDIS-D/testing/input1/000001.jpg")

                # 上传input2
                self.progress.emit("上传input2图片...")
                self.ssh.exec_command("rm -rf ~/autodl-tmp/UDIS-D/testing/input2/*")
                scp.put(self.image_paths[2], "~/autodl-tmp/UDIS-D/testing/input2/000001.jpg")

            self.progress.emit("✅ 图片上传完成")
            return True
        except Exception as e:
            self.progress.emit(f"❌ 上传失败: {str(e)}")
            return False

    def process_images(self):
        """执行处理"""
        try:
            self.progress.emit("开始图像变形处理...")
            _, stdout, stderr = self.ssh.exec_command(
                "/root/miniconda3/bin/python ~/autodl-tmp/UDIS2-main/Warp/Codes/test_output.py"
            )
            if stdout.channel.recv_exit_status() != 0:
                raise Exception(stderr.read().decode())

            self.progress.emit("开始图像融合处理...")
            _, stdout, stderr = self.ssh.exec_command(
                "/root/miniconda3/bin/python ~/autodl-tmp/UDIS2-main/Composition/Codes/test.py"
            )
            if stdout.channel.recv_exit_status() != 0:
                raise Exception(stderr.read().decode())

            self.progress.emit("✅ 图像处理完成")
            return True
        except Exception as e:
            self.progress.emit(f"❌ 处理失败: {str(e)}")
            return False

    def download_result(self):
        """下载结果"""
        try:
            local_path = "fusion_result.jpg"
            with SCPClient(self.ssh.get_transport()) as scp:
                scp.get("~/autodl-tmp/UDIS2-main/Composition/composition/000001.jpg", local_path)
            self.progress.emit("✅ 结果下载完成")
            return local_path
        except Exception as e:
            self.progress.emit(f"❌ 下载失败: {str(e)}")
            return None

    def stop(self):
        """终止操作"""
        self.should_stop = True
        if self.ssh:
            self.ssh.close()


# ============================================================
#                        主界面类（简化版）
# ============================================================

class FusionApp(QWidget):
    def __init__(self):
        super().__init__()
        self.operation_thread = None  # 操作线程实例
        self.image_paths = {1: None, 2: None}  # 图片路径存储

        # 初始化界面
        self.init_ui()
        self.setup_connections()

    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("一键图像融合系统")
        self.setGeometry(100, 100, 800, 600)

        # 主布局
        main_layout = QVBoxLayout()

        # 图片选择区域
        img_layout = QHBoxLayout()

        # input1 图片显示
        self.lbl_img1 = QLabel("点击选择第一张图片")
        self.lbl_img1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_img1.setStyleSheet("border: 2px dashed #666; font-size: 14px;")
        img_layout.addWidget(self.lbl_img1)

        # input2 图片显示
        self.lbl_img2 = QLabel("点击选择第二张图片")
        self.lbl_img2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_img2.setStyleSheet("border: 2px dashed #666; font-size: 14px;")
        img_layout.addWidget(self.lbl_img2)

        main_layout.addLayout(img_layout)

        # 操作按钮
        self.btn_start = QPushButton("开 始 融 合")
        self.btn_start.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 15px 32px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        main_layout.addWidget(self.btn_start)

        # 日志区域
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        main_layout.addWidget(self.log_area)

        # 结果显示区域
        self.lbl_result = QLabel()
        self.lbl_result.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.lbl_result)

        # 服务器设置区域
        server_layout = QHBoxLayout()
        self.txt_host = QLineEdit("connect.cqa1.seetacloud.com")
        self.txt_port = QLineEdit("31041")
        self.txt_pwd = QLineEdit()
        self.txt_pwd.setPlaceholderText("输入服务器密码")
        self.txt_pwd.setEchoMode(QLineEdit.EchoMode.Password)

        server_layout.addWidget(QLabel("地址:"))
        server_layout.addWidget(self.txt_host)
        server_layout.addWidget(QLabel("端口:"))
        server_layout.addWidget(self.txt_port)
        server_layout.addWidget(QLabel("密码:"))
        server_layout.addWidget(self.txt_pwd)

        main_layout.addLayout(server_layout)

        self.setLayout(main_layout)

    def setup_connections(self):
        """设置信号连接"""
        # 图片选择点击事件
        self.lbl_img1.mousePressEvent = lambda e: self.select_image(1)
        self.lbl_img2.mousePressEvent = lambda e: self.select_image(2)

        # 开始按钮点击事件
        self.btn_start.clicked.connect(self.start_process)

    def select_image(self, index):
        """选择图片"""
        path, _ = QFileDialog.getOpenFileName(
            self, "选择图片", "", "图片文件 (*.jpg *.jpeg *.png)")
        if path:
            self.image_paths[index] = path
            label = self.lbl_img1 if index == 1 else self.lbl_img2
            pixmap = QPixmap(path).scaled(300, 300, Qt.AspectRatioMode.KeepAspectRatio)
            label.setPixmap(pixmap)
            self.log(f"已选择图片{index}: {path.split('/')[-1]}")

    def start_process(self):
        """启动完整流程"""
        # 验证输入
        if not all(self.image_paths.values()):
            QMessageBox.warning(self, "提示", "请先选择两张图片")
            return

        if not all([self.txt_host.text(), self.txt_port.text(), self.txt_pwd.text()]):
            QMessageBox.warning(self, "提示", "请填写完整的服务器信息")
            return

        # 准备连接信息
        ssh_info = {
            "hostname": self.txt_host.text().strip(),
            "port": int(self.txt_port.text().strip()),
            "username": "root",
            "password": self.txt_pwd.text().strip()
        }

        # 初始化线程
        self.operation_thread = OperationThread(ssh_info, self.image_paths)
        self.operation_thread.progress.connect(self.log)
        self.operation_thread.finished.connect(self.handle_process_finished)
        self.operation_thread.result_ready.connect(self.show_result)

        # 更新界面状态
        self.btn_start.setEnabled(False)
        self.btn_start.setText("处理中...")
        self.lbl_result.clear()
        self.log_area.clear()

        # 启动线程
        self.operation_thread.start()

    def handle_process_finished(self, success):
        """处理完成后的回调"""
        self.btn_start.setEnabled(True)
        self.btn_start.setText("开 始 融 合")
        if not success:
            QMessageBox.critical(self, "错误", "处理流程未完成，请检查日志")

    def show_result(self, file_path):
        """显示结果图片"""
        pixmap = QPixmap(file_path).scaled(400, 400, Qt.AspectRatioMode.KeepAspectRatio)
        self.lbl_result.setPixmap(pixmap)
        self.log("✅ 结果已显示")

    def log(self, message):
        """记录日志"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_area.append(f"[{timestamp}] {message}")
        QApplication.processEvents()  # 强制刷新界面

    def closeEvent(self, event):
        """窗口关闭时确保终止线程"""
        if self.operation_thread and self.operation_thread.isRunning():
            self.operation_thread.stop()
            self.operation_thread.wait()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FusionApp()
    window.show()
    sys.exit(app.exec())
