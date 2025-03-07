import sys
import paramiko
import time
from scp import SCPClient
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton,
    QLineEdit, QFileDialog, QTextEdit, QMessageBox, QHBoxLayout,
    QScrollArea, QFrame, QSizePolicy
)
from PyQt6.QtGui import QPixmap
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
            # 连接服务器
            self.ssh = self.connect_ssh()
            if not self.ssh:
                self.finished.emit(False)
                return

            # 上传图片
            if not self.upload_images():
                self.finished.emit(False)
                return

            # 处理变形并获取中间产物
            if not self.process_warp():
                self.finished.emit(False)
                return

            # 处理融合并获取中间产物
            if not self.process_composition():
                self.finished.emit(False)
                return

            # 下载最终结果
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
            self.progress.emit("清理工作空间...")
            self.progress.emit("删除 ~/autodl-tmp/UDIS-D/testing/warp1/*")
            self.ssh.exec_command("rm -rf ~/autodl-tmp/UDIS-D/testing/warp1/*")
            self.progress.emit("删除 ~/autodl-tmp/UDIS-D/testing/warp1/*")
            self.ssh.exec_command("rm -rf ~/autodl-tmp/UDIS-D/testing/warp2/*")
            self.progress.emit("删除 ~/autodl-tmp/UDIS-D/testing/mask1/*")
            self.ssh.exec_command("rm -rf ~/autodl-tmp/UDIS-D/testing/mask1/*")
            self.progress.emit("删除 ~/autodl-tmp/UDIS-D/testing/mask2/*")
            self.ssh.exec_command("rm -rf ~/autodl-tmp/UDIS-D/testing/mask2/*")

            self.progress.emit("开始图像变形处理...")
            _, stdout, stderr = self.ssh.exec_command(
                "/root/miniconda3/bin/python ~/autodl-tmp/UDIS2-main/Warp/Codes/test_output.py"
            )
            if stdout.channel.recv_exit_status() != 0:
                raise Exception(stderr.read().decode())

            # 下载变形中间产物
            intermediates = [
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
            self.progress.emit("清理工作空间...")
            self.progress.emit("删除 ~/autodl-tmp/UDIS2-main/Composition/learn_mask1/*")
            self.ssh.exec_command("rm -rf ~/autodl-tmp/UDIS2-main/Composition/learn_mask1/*")
            self.progress.emit("删除 ~/autodl-tmp/UDIS2-main/Composition/learn_mask2/*")
            self.ssh.exec_command("rm -rf ~/autodl-tmp/UDIS2-main/Composition/learn_mask2/*")

            self.progress.emit("开始图像融合处理...")
            _, stdout, stderr = self.ssh.exec_command(
                "/root/miniconda3/bin/python ~/autodl-tmp/UDIS2-main/Composition/Codes/test.py"
            )
            if stdout.channel.recv_exit_status() != 0:
                raise Exception(stderr.read().decode())

            # 下载融合中间产物
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
        """初始化界面"""
        self.setWindowTitle("图像融合系统")
        self.setGeometry(100, 100, 900, 500)

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

        # 图片选择区域
        img_layout = QHBoxLayout()
        self.lbl_img1 = self.create_input_box("input1", "点击选择图片1")
        self.lbl_img2 = self.create_input_box("input2", "点击选择图片2")
        img_layout.addWidget(self.lbl_img1)
        img_layout.addWidget(self.lbl_img2)
        main_layout.addLayout(img_layout)

        # 操作按钮
        self.btn_start = QPushButton("开始融合处理")
        self.btn_start.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                padding: 15px 30px;
                font-size: 14px;
                border-radius: 8px;
                margin: 10px;
            }
            QPushButton:disabled {
                background-color: #BBDEFB;
            }
        """)
        main_layout.addWidget(self.btn_start, alignment=Qt.AlignmentFlag.AlignCenter)

        # 中间产物展示区
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(200)
        scroll.setStyleSheet("border: none;")

        content = QWidget()
        self.intermediate_layout = QVBoxLayout(content)

        # 变形处理产物
        self.warp_group = self.create_intermediate_group("变形处理中间产物",
                                                         ["warp1", "warp2"], 220)

        # 融合处理产物
        self.comp_group = self.create_intermediate_group("融合处理中间产物",
                                                         ["learn_mask1", "learn_mask2"], 110)

        # 最终结果
        self.final_group = self.create_intermediate_group("最终结果", ["final_result"], 175)
        self.final_label = self.findChild(QLabel, "final_result")

        self.intermediate_layout.addWidget(self.warp_group)
        self.intermediate_layout.addWidget(self.comp_group)
        self.intermediate_layout.addWidget(self.final_group)

        scroll.setWidget(content)
        main_layout.addWidget(scroll)

        # 日志区域
        self.log_area = QTextEdit()
        self.log_area.setStyleSheet("""
            QTextEdit {
                background-color: #FAFAFA;
                border: 1px solid #EEE;
                padding: 10px;
                font-family: monospace;
            }
        """)
        self.log_area.setReadOnly(True)
        main_layout.addWidget(self.log_area)

        self.setLayout(main_layout)

    def create_input_box(self, name, prompt):
        """创建输入图片框"""
        frame = QFrame()
        frame.setObjectName(f"frame_{name}")
        frame.setFrameStyle(QFrame.Shape.Box)
        frame.setLineWidth(2)
        frame.setStyleSheet("""
            QFrame {
                border: 2px dashed #999;
                border-radius: 10px;
                background-color: #F8F8F8;
            }
        """)
        layout = QVBoxLayout(frame)

        label = QLabel(prompt)
        label.setObjectName(name)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setMinimumSize(120, 120)
        label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                color: #666;
                qproperty-alignment: AlignCenter;
            }
        """)

        layout.addWidget(label)
        return frame

    def create_intermediate_group(self, title, items, size):
        """创建中间产物分组框"""
        group = QFrame()
        group.setFrameStyle(QFrame.Shape.StyledPanel)
        layout = QHBoxLayout(group)
        layout.setContentsMargins(10, 10, 10, 10)

        title_label = QLabel(title)
        title_label.setStyleSheet("""
            QLabel {
                font-weight: bold;
                font-size: 16px;
                color: #444;
                padding: 5px;
            }
        """)
        layout.addWidget(title_label)

        for item in items:
            frame = QFrame()
            frame.setFrameStyle(QFrame.Shape.Panel)
            vbox = QVBoxLayout(frame)
            vbox.setSpacing(5)

            # 图片标签
            img_label = QLabel("等待生成...")
            img_label.setObjectName(item)
            img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            img_label.setMinimumSize(size, size)
            img_label.setStyleSheet(f"""
                QLabel {{
                    background-color: #FFF;
                    border: 2px solid #DDD;
                    border-radius: 8px;
                    min-width: {size}px;
                    min-height: {size}px;
                }}
            """)

            # 标题标签
            title_label = QLabel(item.replace("_", " ").title())
            title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            title_label.setStyleSheet("""
                QLabel {
                    color: #666;
                    font-size: 14px;
                }
            """)

            vbox.addWidget(title_label)
            vbox.addWidget(img_label)
            layout.addWidget(frame)

        return group

    def setup_connections(self):
        """设置信号连接"""
        self.lbl_img1.mousePressEvent = lambda e: self.select_image(1)
        self.lbl_img2.mousePressEvent = lambda e: self.select_image(2)
        self.btn_start.clicked.connect(self.start_process)

    def select_image(self, index):
        """选择图片"""
        path, _ = QFileDialog.getOpenFileName(
            self, "选择图片", "",
            "图片文件 (*.jpg *.jpeg *.png)"
        )
        if path:
            self.image_paths[index] = path
            label = self.findChild(QLabel, "input1" if index == 1 else "input2")
            pixmap = QPixmap(path).scaled(
                150, 150,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            label.setPixmap(pixmap)
            label.setText("")
            self.log(f"已选择图片{index}: {path.split('/')[-1]}")

    def start_process(self):
        """启动处理流程"""
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

        self.thread.start()

    def update_intermediate(self, img_type, path):
        """更新中间产物显示"""
        target_label = self.findChild(QLabel, img_type)
        if target_label:
            pixmap = QPixmap(path).scaled(
                target_label.width(),
                target_label.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            target_label.setPixmap(pixmap)
            target_label.setStyleSheet("background-color: #FFF;")

    def show_final_result(self, path):
        """显示最终结果"""
        self.final_label = self.findChild(QLabel, "final_result")
        if self.final_label:
            pixmap = QPixmap(path).scaled(
                150, 150,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.final_label.setPixmap(pixmap)
            self.final_label.setStyleSheet("""
                QLabel {
                    background-color: #FFF;
                    border: 2px solid #2196F3;
                    border-radius: 10px;
                }
            """)

    def handle_process_finished(self, success):
        """处理完成回调"""
        self.btn_start.setEnabled(True)
        self.btn_start.setText("开始融合处理")
        if not success:
            QMessageBox.critical(self, "错误", "处理过程中发生错误，请查看日志")

    def log(self, message):
        """记录日志"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_area.append(f"[{timestamp}] {message}")
        self.log_area.verticalScrollBar().setValue(
            self.log_area.verticalScrollBar().maximum()
        )

    def closeEvent(self, event):
        """关闭窗口事件"""
        if self.thread and self.thread.isRunning():
            self.thread.terminate()
            self.thread.wait()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FusionApp()
    window.show()
    sys.exit(app.exec())
