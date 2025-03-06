import sys
import paramiko
import time
from scp import SCPClient
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton,
    QLineEdit, QFileDialog, QTextEdit, QMessageBox, QHBoxLayout,
    QScrollArea, QFrame, QSizePolicy
)
from PyQt6.QtGui import QPixmap, QScreen
from PyQt6.QtCore import Qt, QThread, pyqtSignal


# ============================================================
#                        线程工作类
# ============================================================

class FusionThread(QThread):
    progress = pyqtSignal(str)
    result_ready = pyqtSignal(str)
    intermediate_ready = pyqtSignal(str, str)
    finished = pyqtSignal(bool)

    def __init__(self, ssh_info, image_paths):
        super().__init__()
        self.ssh_info = ssh_info
        self.image_paths = image_paths
        self.ssh = None

    def run(self):
        try:
            self.ssh = self.connect_ssh()
            if not self.ssh:
                self.finished.emit(False)
                return

            if not self.upload_images():
                self.finished.emit(False)
                return

            if not self.process_warp():
                self.finished.emit(False)
                return

            if not self.process_composition():
                self.finished.emit(False)
                return

            final_path = self.download_result()
            if final_path:
                self.result_ready.emit(final_path)
                self.finished.emit(True)
            else:
                self.finished.emit(False)

        except Exception as e:
            self.progress.emit(f"❌ 发生错误: {str(e)}")
            self.finished.emit(False)
        finally:
            if self.ssh:
                self.ssh.close()

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
        """上传原始图片"""
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

    def process_warp(self):
        """执行变形处理"""
        try:
            self.progress.emit("开始图像变形处理...")
            _, stdout, stderr = self.ssh.exec_command(
                "/root/miniconda3/bin/python ~/autodl-tmp/UDIS2-main/Warp/Codes/test_output.py"
            )
            if stdout.channel.recv_exit_status() != 0:
                raise Exception(stderr.read().decode())

            # 下载变形处理中间产物
            intermediates = [
                ("mask1", "autodl-tmp/UDIS-D/testing/mask1/000001.jpg"),
                ("mask2", "autodl-tmp/UDIS-D/testing/mask2/000001.jpg"),
                ("warp1", "autodl-tmp/UDIS-D/testing/warp1/000001.jpg"),
                ("warp2", "autodl-tmp/UDIS-D/testing/warp2/000001.jpg")
            ]
            self.download_intermediates(intermediates)
            return True
        except Exception as e:
            self.progress.emit(f"❌ 变形处理失败: {str(e)}")
            return False

    def process_composition(self):
        """执行融合处理"""
        try:
            self.progress.emit("开始图像融合处理...")
            _, stdout, stderr = self.ssh.exec_command(
                "/root/miniconda3/bin/python ~/autodl-tmp/UDIS2-main/Composition/Codes/test.py"
            )
            if stdout.channel.recv_exit_status() != 0:
                raise Exception(stderr.read().decode())

            # 下载融合处理中间产物
            intermediates = [
                ("learn_mask1", "autodl-tmp/UDIS2-main/Composition/learn_mask1/000001.jpg"),
                ("learn_mask2", "autodl-tmp/UDIS2-main/Composition/learn_mask2/000001.jpg")
            ]
            self.download_intermediates(intermediates)
            return True
        except Exception as e:
            self.progress.emit(f"❌ 融合处理失败: {str(e)}")
            return False

    def download_intermediates(self, files):
        """下载中间产物"""
        try:
            with SCPClient(self.ssh.get_transport()) as scp:
                for file_type, remote_path in files:
                    local_path = f"{file_type}.jpg"
                    scp.get(f"~/{remote_path}", local_path)
                    self.intermediate_ready.emit(file_type, local_path)
                    self.progress.emit(f"下载 {file_type} 成功")
            return True
        except Exception as e:
            self.progress.emit(f"❌ 下载中间产物失败: {str(e)}")
            return False

    def download_result(self):
        """下载最终结果"""
        try:
            local_path = "final_result.jpg"
            with SCPClient(self.ssh.get_transport()) as scp:
                scp.get("~/autodl-tmp/UDIS2-main/Composition/composition/000001.jpg", local_path)
            self.progress.emit("✅ 最终结果下载完成")
            return local_path
        except Exception as e:
            self.progress.emit(f"❌ 下载最终结果失败: {str(e)}")
            return None


# ============================================================
#                        主界面类
# ============================================================
class FusionApp(QWidget):
    def __init__(self):
        super().__init__()
        self.thread = None
        self.image_paths = {1: None, 2: None}
        self.init_ui()
        self.setup_connections()

    def init_ui(self):
        self.setWindowTitle("图像融合系统")
        self.setGeometry(100, 100, 1000, 800)
        self.center_window()

        main_layout = QVBoxLayout()

        # 服务器信息输入
        server_layout = QHBoxLayout()
        self.txt_host = QLineEdit("connect.cqa1.seetacloud.com")
        self.txt_port = QLineEdit("31041")
        self.txt_pwd = QLineEdit()
        self.txt_pwd.setPlaceholderText("服务器密码")
        self.txt_pwd.setEchoMode(QLineEdit.EchoMode.Password)

        server_layout.addWidget(QLabel("地址:"))
        server_layout.addWidget(self.txt_host)
        server_layout.addWidget(QLabel("端口:"))
        server_layout.addWidget(self.txt_port)
        server_layout.addWidget(QLabel("密码:"))
        server_layout.addWidget(self.txt_pwd)
        main_layout.addLayout(server_layout)

        # 图片选择区域（修复1：添加对象名称）
        img_layout = QHBoxLayout()
        self.lbl_img1 = self.create_image_box("input1", "点击选择图片1")
        self.lbl_img2 = self.create_image_box("input2", "点击选择图片2")
        img_layout.addWidget(self.lbl_img1)
        img_layout.addWidget(self.lbl_img2)
        main_layout.addLayout(img_layout)

        # 操作按钮
        self.btn_start = QPushButton("开始融合处理")
        self.btn_start.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                padding: 12px;
                font-size: 16px;
                border-radius: 5px;
            }
            QPushButton:disabled {
                background-color: #BBDEFB;
            }
        """)
        main_layout.addWidget(self.btn_start)

        # 中间产物展示区（修复2：明确命名）
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        self.intermediate_layout = QVBoxLayout(content)

        # 变形处理产物
        self.warp_group = self.create_group_box("变形处理中间产物",
                                                ["mask1", "mask2", "warp1", "warp2"])
        # 融合处理产物
        self.comp_group = self.create_group_box("融合处理中间产物",
                                                ["learn_mask1", "learn_mask2"])
        # 最终结果（修复3：单独命名结果区域）
        self.final_group = self.create_group_box("最终结果", ["final_result"])
        self.final_label = self.final_group.findChild(QLabel, "final_result")

        self.intermediate_layout.addWidget(self.warp_group)
        self.intermediate_layout.addWidget(self.comp_group)
        self.intermediate_layout.addWidget(self.final_group)
        scroll.setWidget(content)
        main_layout.addWidget(scroll)

        # 日志区域
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        main_layout.addWidget(self.log_area)

        self.setLayout(main_layout)

    def center_window(self):
        screen = QScreen.availableGeometry(QApplication.primaryScreen())  # 获取主屏幕几何信息
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

    def create_image_box(self, name, text):
        """创建带名称的图片框"""
        frame = QFrame()
        frame.setObjectName(f"frame_{name}")
        frame.setFrameStyle(QFrame.Shape.Box)
        frame.setLineWidth(1)
        frame.setStyleSheet("border: 2px dashed #666;")
        layout = QVBoxLayout(frame)

        label = QLabel(text)
        label.setObjectName(name)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setMinimumSize(300, 300)

        layout.addWidget(label)
        return frame

    def create_group_box(self, title, items):
        """创建带明确命名的分组框"""
        group = QFrame()
        group.setFrameStyle(QFrame.Shape.Box)
        layout = QHBoxLayout(group)

        layout.addWidget(QLabel(title + ":"))
        for item in items:
            frame = QFrame()
            frame.setFrameStyle(QFrame.Shape.Box)
            vbox = QVBoxLayout(frame)

            label = QLabel("等待生成...")
            label.setObjectName(item)  # 设置对象名称
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setMinimumSize(150, 150)
            label.setStyleSheet("background-color: #F5F5F5;")

            title_label = QLabel(item)
            title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

            vbox.addWidget(title_label)
            vbox.addWidget(label)
            layout.addWidget(frame)

        return group

    def setup_connections(self):
        self.lbl_img1.mousePressEvent = lambda e: self.select_image(1)
        self.lbl_img2.mousePressEvent = lambda e: self.select_image(2)
        self.btn_start.clicked.connect(self.start_process)

    def select_image(self, index):
        path, _ = QFileDialog.getOpenFileName(self, "选择图片", "", "图片文件 (*.jpg *.png)")
        if path:
            self.image_paths[index] = path
            label = self.findChild(QLabel, "input1" if index == 1 else "input2")
            pixmap = QPixmap(path).scaled(300, 300, Qt.AspectRatioMode.KeepAspectRatio)
            label.setPixmap(pixmap)
            label.setText("")
            self.log(f"已选择图片{index}: {path.split('/')[-1]}")

    def start_process(self):
        if not all(self.image_paths.values()):
            QMessageBox.warning(self, "提示", "请先选择两张图片")
            return
        if not all([self.txt_host.text(), self.txt_port.text(), self.txt_pwd.text()]):
            QMessageBox.warning(self, "提示", "请填写完整的服务器信息")
            return

        ssh_info = {
            "hostname": self.txt_host.text().strip(),
            "port": int(self.txt_port.text().strip()),
            "username": "root",
            "password": self.txt_pwd.text().strip()
        }

        self.thread = FusionThread(ssh_info, self.image_paths)
        self.thread.progress.connect(self.log)
        self.thread.intermediate_ready.connect(self.update_intermediate)
        self.thread.result_ready.connect(self.show_final_result)
        self.thread.finished.connect(self.handle_process_finished)

        self.btn_start.setEnabled(False)
        self.btn_start.setText("处理中...")
        self.clear_display()

        self.thread.start()

    def update_intermediate(self, img_type, path):
        """修复中间产物更新逻辑"""
        target_label = self.findChild(QLabel, img_type)
        if target_label:
            pixmap = QPixmap(path).scaled(150, 150, Qt.AspectRatioMode.KeepAspectRatio)
            target_label.setPixmap(pixmap)
            target_label.setText("")

    def show_final_result(self, path):
        """修复最终结果展示"""
        if self.final_label:
            pixmap = QPixmap(path).scaled(300, 300, Qt.AspectRatioMode.KeepAspectRatio)
            self.final_label.setPixmap(pixmap)
            self.final_label.setText("")

    def handle_process_finished(self, success):
        self.btn_start.setEnabled(True)
        self.btn_start.setText("开始融合处理")
        if not success:
            QMessageBox.critical(self, "错误", "处理过程中发生错误，请查看日志")

    def log(self, message):
        timestamp = time.strftime("%H:%M:%S")
        self.log_area.append(f"[{timestamp}] {message}")

    def clear_display(self):
        """修复：只清空中间产物和最终结果"""
        # 清空中间产物
        for name in ["mask1", "mask2", "warp1", "warp2", "learn_mask1", "learn_mask2"]:
            label = self.findChild(QLabel, name)
            if label:
                label.setPixmap(QPixmap())
                label.setText("等待生成...")

        # 清空最终结果
        if self.final_label:
            self.final_label.setPixmap(QPixmap())
            self.final_label.setText("等待生成...")

    def closeEvent(self, event):
        if self.thread and self.thread.isRunning():
            self.thread.terminate()
            self.thread.wait()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FusionApp()
    window.show()
    sys.exit(app.exec())