import sys
import time

import paramiko
from scp import SCPClient
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton,
    QLineEdit, QFileDialog, QTextEdit, QMessageBox, QStackedWidget, QHBoxLayout
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt, QThread, pyqtSignal


# ============================================================
#                        线程工作类
# ============================================================

class SSHLoginThread(QThread):
    """SSH登录线程"""
    login_success = pyqtSignal(paramiko.SSHClient)  # 登录成功信号（携带SSH客户端）
    login_failed = pyqtSignal(str)  # 登录失败信号（携带错误信息）

    def __init__(self, host, port, username, password):
        super().__init__()
        self.host = host
        self.port = port
        self.username = username
        self.password = password

    def run(self):
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=15
            )
            self.login_success.emit(ssh)
        except Exception as e:
            self.login_failed.emit(str(e))


class FileUploadThread(QThread):
    """文件上传线程"""
    progress = pyqtSignal(str)  # 进度更新信号
    finished = pyqtSignal()  # 完成信号
    error = pyqtSignal(str)  # 错误信号

    def __init__(self, ssh_client, image_paths):
        super().__init__()
        self.ssh = ssh_client
        self.image_paths = image_paths

    def run(self):
        try:
            # 上传input1
            self.progress.emit("正在清理服务器input1目录...")
            stdin, stdout, stderr = self.ssh.exec_command("rm -rf ~/autodl-tmp/UDIS-D/testing/input1/*")
            self.progress.emit(stdout.read().decode())

            self.progress.emit("开始上传input1图片...")
            with SCPClient(self.ssh.get_transport()) as scp:
                scp.put(self.image_paths[1], "~/autodl-tmp/UDIS-D/testing/input1/000001.jpg")

            # 上传input2
            self.progress.emit("正在清理服务器input2目录...")
            stdin, stdout, stderr = self.ssh.exec_command("rm -rf ~/autodl-tmp/UDIS-D/testing/input2/*")
            self.progress.emit(stdout.read().decode())

            self.progress.emit("开始上传input2图片...")
            with SCPClient(self.ssh.get_transport()) as scp:
                scp.put(self.image_paths[2], "~/autodl-tmp/UDIS-D/testing/input2/000001.jpg")

            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))


class FusionProcessThread(QThread):
    """融合处理线程"""
    output = pyqtSignal(str)  # 输出信息信号
    finished = pyqtSignal()  # 处理完成信号
    error = pyqtSignal(str)  # 错误信号

    def __init__(self, ssh_client):
        super().__init__()
        self.ssh = ssh_client

    def run(self):
        try:
            # 执行第一个处理脚本
            self.output.emit("开始图像变形处理...")
            stdin, stdout, stderr = self.ssh.exec_command(
                "/root/miniconda3/bin/python ~/autodl-tmp/UDIS2-main/Warp/Codes/test_output.py"
            )
            self.output.emit(stdout.read().decode())

            # 执行第二个处理脚本
            self.output.emit("开始图像融合处理...")
            stdin, stdout, stderr = self.ssh.exec_command(
                "/root/miniconda3/bin/python ~/autodl-tmp/UDIS2-main/Composition/Codes/test.py"
            )
            self.output.emit(stdout.read().decode())

            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))


# ============================================================
#                        主界面类
# ============================================================

class UDIS2GUI(QWidget):
    def __init__(self):
        super().__init__()
        self.ssh_client = None  # SSH客户端实例
        self.image_paths = {1: None, 2: None}  # 存储图片路径

        # 初始化界面
        self.init_ui()
        # 设置信号连接
        self.setup_connections()

    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("UDIS2 图像融合系统")
        self.setGeometry(100, 100, 800, 600)

        # 使用堆叠布局实现页面切换
        self.stacked_layout = QStackedWidget()

        # 创建登录页面
        self.login_page = self.create_login_page()
        # 创建操作页面
        self.operation_page = self.create_operation_page()

        # 添加页面到堆叠布局
        self.stacked_layout.addWidget(self.login_page)
        self.stacked_layout.addWidget(self.operation_page)

        # 设置主布局
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.stacked_layout)
        self.setLayout(main_layout)

    def create_login_page(self):
        """创建登录页面"""
        page = QWidget()
        layout = QVBoxLayout()

        # 服务器地址输入
        lbl_host = QLabel("服务器地址:")
        self.txt_host = QLineEdit("connect.cqa1.seetacloud.com")
        layout.addWidget(lbl_host)
        layout.addWidget(self.txt_host)

        # 端口输入
        lbl_port = QLabel("端口号:")
        self.txt_port = QLineEdit("31041")
        layout.addWidget(lbl_port)
        layout.addWidget(self.txt_port)

        # 密码输入
        lbl_pwd = QLabel("密码:")
        self.txt_pwd = QLineEdit()
        self.txt_pwd.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(lbl_pwd)
        layout.addWidget(self.txt_pwd)

        # 登录按钮
        self.btn_login = QPushButton("登 录")
        layout.addWidget(self.btn_login)

        # 错误提示标签
        self.lbl_login_error = QLabel()
        self.lbl_login_error.setStyleSheet("color: red;")
        layout.addWidget(self.lbl_login_error)

        page.setLayout(layout)
        return page

    def create_operation_page(self):
        """创建操作页面"""
        page = QWidget()
        layout = QVBoxLayout()

        # 图片选择区域
        img_layout = QHBoxLayout()

        # input1 图片
        self.lbl_img1 = QLabel("点击选择第一张图片")
        self.lbl_img1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_img1.setStyleSheet("border: 2px dashed #aaa;")
        img_layout.addWidget(self.lbl_img1)

        # input2 图片
        self.lbl_img2 = QLabel("点击选择第二张图片")
        self.lbl_img2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_img2.setStyleSheet("border: 2px dashed #aaa;")
        img_layout.addWidget(self.lbl_img2)

        layout.addLayout(img_layout)

        # 操作按钮
        btn_layout = QHBoxLayout()
        self.btn_upload = QPushButton("上传图片")
        self.btn_process = QPushButton("开始融合")
        self.btn_show = QPushButton("查看结果")
        btn_layout.addWidget(self.btn_upload)
        btn_layout.addWidget(self.btn_process)
        btn_layout.addWidget(self.btn_show)
        layout.addLayout(btn_layout)

        # 日志显示
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        layout.addWidget(self.log_area)

        # 结果显示
        self.lbl_result = QLabel()
        self.lbl_result.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_result)

        page.setLayout(layout)
        return page

    def setup_connections(self):
        """设置信号和槽连接"""
        # 登录按钮
        self.btn_login.clicked.connect(self.start_login)

        # 图片选择（通过标签点击事件）
        self.lbl_img1.mousePressEvent = lambda e: self.select_image(1)
        self.lbl_img2.mousePressEvent = lambda e: self.select_image(2)

        # 操作按钮
        self.btn_upload.clicked.connect(self.start_upload)
        self.btn_process.clicked.connect(self.start_process)
        self.btn_show.clicked.connect(self.show_result)

    # ================== 核心功能方法 ==================
    def start_login(self):
        """启动登录流程"""
        host = self.txt_host.text().strip()
        port = int(self.txt_port.text().strip())
        username = "root"
        password = self.txt_pwd.text().strip()

        # 禁用登录按钮
        self.btn_login.setEnabled(False)
        self.btn_login.setText("连接中...")

        # 创建并启动登录线程
        self.login_thread = SSHLoginThread(host, port, username, password)
        self.login_thread.login_success.connect(self.handle_login_success)
        self.login_thread.login_failed.connect(self.handle_login_failed)
        self.login_thread.start()

    def handle_login_success(self, ssh_client):
        """登录成功处理"""
        self.ssh_client = ssh_client
        self.stacked_layout.setCurrentIndex(1)  # 切换到操作页面
        self.log("✅ 服务器连接成功！")
        self.btn_login.setEnabled(True)
        self.btn_login.setText("登 录")

    def handle_login_failed(self, error_msg):
        """登录失败处理"""
        self.lbl_login_error.setText(f"连接失败: {error_msg}")
        self.btn_login.setEnabled(True)
        self.btn_login.setText("重 试")
        self.log(f"❌ 连接失败: {error_msg}")

    def select_image(self, index):
        """选择本地图片"""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择图片",
            "",
            "图片文件 (*.jpg *.jpeg *.png)"
        )
        if path:
            self.image_paths[index] = path
            label = self.lbl_img1 if index == 1 else self.lbl_img2
            pixmap = QPixmap(path).scaled(300, 300, Qt.AspectRatioMode.KeepAspectRatio)
            label.setPixmap(pixmap)
            self.log(f"已选择图片{index}: {path.split('/')[-1]}")

    def start_upload(self):
        """启动文件上传"""
        if not all(self.image_paths.values()):
            QMessageBox.warning(self, "提示", "请先选择两张图片")
            return

        # 创建上传线程
        self.upload_thread = FileUploadThread(self.ssh_client, self.image_paths)
        self.upload_thread.progress.connect(self.log)
        self.upload_thread.finished.connect(lambda: (
            self.log("✅ 图片上传完成！"),
            self.btn_upload.setEnabled(True)
        ))
        self.upload_thread.error.connect(lambda e: (
            self.log(f"❌ 上传失败: {e}"),
            QMessageBox.critical(self, "错误", f"上传失败: {e}"),
            self.btn_upload.setEnabled(True)
        ))
        self.btn_upload.setEnabled(False)
        self.upload_thread.start()

    def start_process(self):
        """启动融合处理"""
        self.process_thread = FusionProcessThread(self.ssh_client)
        self.process_thread.output.connect(self.log)
        self.process_thread.finished.connect(lambda: (
            self.log("✅ 图像融合完成！"),
            self.btn_process.setEnabled(True)
        ))
        self.process_thread.error.connect(lambda e: (
            self.log(f"❌ 处理失败: {e}"),
            QMessageBox.critical(self, "错误", f"处理失败: {e}"),
            self.btn_process.setEnabled(True)
        ))
        self.btn_process.setEnabled(False)
        self.process_thread.start()

    def show_result(self):
        """显示处理结果"""
        try:
            # 从服务器下载结果
            local_path = "result.jpg"
            with SCPClient(self.ssh_client.get_transport()) as scp:
                scp.get("~/autodl-tmp/UDIS2-main/Composition/composition/000001.jpg", local_path)

            # 显示结果
            pixmap = QPixmap(local_path).scaled(400, 400, Qt.AspectRatioMode.KeepAspectRatio)
            self.lbl_result.setPixmap(pixmap)
            self.log("✅ 结果图像已加载")
        except Exception as e:
            self.log(f"❌ 结果获取失败: {e}")
            QMessageBox.critical(self, "错误", f"无法获取结果: {e}")

    def log(self, message):
        """记录日志"""
        self.log_area.append(f"[{time.strftime('%H:%M:%S')}] {message}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = UDIS2GUI()
    window.show()
    sys.exit(app.exec())
