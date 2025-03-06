import sys
import paramiko
import time
from scp import SCPClient
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QLineEdit, QFileDialog, QTextEdit, QMessageBox,
    QStackedWidget, QHBoxLayout, QSpacerItem, QSizePolicy
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt
import os


class UDIS2GUI(QWidget):
    def __init__(self):
        super().__init__()

        self.ssh_client = None
        self.sftp_client = None
        self.scp_client = None
        self.server_info = {}

        self.initUI()

    def initUI(self):
        """初始化 GUI 界面"""
        self.setWindowTitle("UDIS2 图像融合 GUI")
        self.setGeometry(100, 100, 600, 500)

        self.layout = QVBoxLayout()

        # 创建一个 QStackedWidget 用于页面切换
        self.stacked_widget = QStackedWidget(self)

        # 登录页面
        self.login_page = QWidget(self)
        self.login_layout = QVBoxLayout()

        self.label_server = QLabel("服务器地址（格式: root@connect.cqa1.seetacloud.com）:")
        self.input_server = QLineEdit("root@connect.cqa1.seetacloud.com")
        self.label_port = QLabel("端口号:")
        self.input_port = QLineEdit("31041")
        self.label_password = QLabel("密码:")
        self.input_password = QLineEdit()
        self.input_password.setEchoMode(QLineEdit.EchoMode.Password)

        self.btn_login = QPushButton("登录")
        self.btn_login.clicked.connect(self.ssh_login)

        self.login_layout.addWidget(self.label_server)
        self.login_layout.addWidget(self.input_server)
        self.login_layout.addWidget(self.label_port)
        self.login_layout.addWidget(self.input_port)
        self.login_layout.addWidget(self.label_password)
        self.login_layout.addWidget(self.input_password)
        self.login_layout.addWidget(self.btn_login)

        self.login_page.setLayout(self.login_layout)

        # 上传与融合页面
        self.upload_page = QWidget(self)
        self.upload_layout = QVBoxLayout()

        # 日志窗口
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.upload_layout.addWidget(self.log_output)

        # 按钮部分
        self.btn_select1 = QPushButton("选择 input1 图片")
        self.btn_select2 = QPushButton("选择 input2 图片")
        self.btn_upload = QPushButton("上传图片到服务器")
        self.btn_run = QPushButton("运行融合任务")
        self.btn_show_result = QPushButton("显示融合结果")

        self.btn_select1.clicked.connect(lambda: self.select_image(1))
        self.btn_select2.clicked.connect(lambda: self.select_image(2))
        self.btn_upload.clicked.connect(self.upload_images)
        self.btn_run.clicked.connect(self.run_fusion)
        self.btn_show_result.clicked.connect(self.show_result)

        # 图片显示部分
        self.label_input1 = QLabel("未选择 input1 图片")
        self.label_input1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_input2 = QLabel("未选择 input2 图片")
        self.label_input2.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 图片并排显示布局
        self.layout_images = QHBoxLayout()
        self.layout_images.addWidget(self.label_input1)
        self.layout_images.addWidget(self.label_input2)

        # 图片选择按钮布局
        self.layout_buttons = QHBoxLayout()
        self.layout_buttons.addWidget(self.btn_select1)
        self.layout_buttons.addWidget(self.btn_select2)

        self.upload_layout.addLayout(self.layout_buttons)
        self.upload_layout.addLayout(self.layout_images)
        self.upload_layout.addWidget(self.btn_upload)
        self.upload_layout.addWidget(self.btn_run)
        self.upload_layout.addWidget(self.btn_show_result)

        # 显示输出图片
        self.result_label = QLabel()
        self.result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.upload_layout.addWidget(self.result_label)

        self.upload_page.setLayout(self.upload_layout)

        # 将两个页面添加到 QStackedWidget
        self.stacked_widget.addWidget(self.login_page)
        self.stacked_widget.addWidget(self.upload_page)

        # 设置初始页面为登录页面
        self.layout.addWidget(self.stacked_widget)

        self.setLayout(self.layout)

        # 存储选定的图片路径
        self.image_paths = {1: None, 2: None}

    def log(self, message):
        """日志输出"""
        self.log_output.append(message)
        self.log_output.ensureCursorVisible()

    def ssh_login(self):
        """SSH 登录"""
        server = self.input_server.text().strip()
        port = int(self.input_port.text().strip())
        password = self.input_password.text().strip()

        if not server or not password:
            QMessageBox.warning(self, "错误", "请输入服务器信息")
            return

        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh_client.connect(hostname=server, port=port, username="root", password=password)

            self.sftp_client = self.ssh_client.open_sftp()
            self.scp_client = SCPClient(self.ssh_client.get_transport())

            self.server_info = {"server": server, "port": port, "password": password}

            self.log("✅ 登录成功！")

            # 登录成功后切换到上传与融合页面
            self.stacked_widget.setCurrentWidget(self.upload_page)
        except Exception as e:
            self.log(f"❌ 登录失败: {str(e)}")
            QMessageBox.critical(self, "登录失败", str(e))

    def select_image(self, index):
        """选择本地图片"""
        file_path, _ = QFileDialog.getOpenFileName(self, "选择图片", "", "Images (*.png *.jpg *.jpeg)")
        if file_path:
            self.image_paths[index] = file_path
            # 更新显示的图片
            if index == 1:
                self.label_input1.setText("")
                pixmap = QPixmap(file_path)
                self.label_input1.setPixmap(pixmap.scaled(150, 150, Qt.AspectRatioMode.KeepAspectRatio))
            elif index == 2:
                self.label_input2.setText("")
                pixmap = QPixmap(file_path)
                self.label_input2.setPixmap(pixmap.scaled(150, 150, Qt.AspectRatioMode.KeepAspectRatio))
            self.log(f"✅ 选择了 input{index} 图片: {file_path}")

    def upload_images(self):
        """上传图片"""
        if not self.ssh_client:
            QMessageBox.warning(self, "错误", "请先登录服务器！")
            return

        remote_dirs = {
            1: "autodl-tmp/UDIS-D/testing/input1/",
            2: "autodl-tmp/UDIS-D/testing/input2/"
        }

        for idx in [1, 2]:
            if not self.image_paths[idx]:
                self.log(f"❌ 请先选择 input{idx} 图片")
                return

            remote_path = remote_dirs[idx]
            local_path = self.image_paths[idx]

            try:
                # 清空目录
                self.ssh_client.exec_command(f"rm -rf {remote_path}*")
                time.sleep(1)  # 等待操作完成

                # 上传文件
                self.scp_client.put(local_path, f"{remote_path}000001.jpg")
                self.log(f"✅ input{idx} 上传完成: {local_path} -> {remote_path}000001.jpg")
            except Exception as e:
                self.log(f"❌ input{idx} 上传失败: {str(e)}")

    def run_fusion(self):
        """运行融合任务"""
        if not self.ssh_client:
            QMessageBox.warning(self, "错误", "请先登录服务器！")
            return

        commands = [
            "/root/miniconda3/bin/python autodl-tmp/UDIS2-main/Warp/Codes/test_output.py",
            "/root/miniconda3/bin/python autodl-tmp/UDIS2-main/Composition/Codes/test.py"
        ]

        for cmd in commands:
            self.log(f"⚙️ 运行: {cmd}")
            _, stdout, stderr = self.ssh_client.exec_command(cmd)
            stdout.channel.recv_exit_status()  # 等待完成
            self.log(stdout.read().decode())
            self.log(stderr.read().decode())

        self.log("✅ 图像融合完成！")

    def show_result(self):
        """显示融合结果"""
        remote_image_path = "autodl-tmp/UDIS2-main/Composition/composition/000001.jpg"
        local_image_path = "result.jpg"

        if not self.ssh_client:
            QMessageBox.warning(self, "错误", "请先登录服务器！")
            return

        try:
            self.sftp_client.get(remote_image_path, local_image_path)
            self.log("✅ 结果图像下载完成")

            pixmap = QPixmap(local_image_path)
            self.result_label.setPixmap(pixmap.scaled(400, 400, Qt.AspectRatioMode.KeepAspectRatio))
        except Exception as e:
            self.log(f"❌ 结果图像下载失败: {str(e)}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = UDIS2GUI()
    window.show()
    sys.exit(app.exec())
