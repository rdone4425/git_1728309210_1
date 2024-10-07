import sys
import os
import asyncio
import json
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTableWidget, QTableWidgetItem, 
                             QVBoxLayout, QWidget, QHeaderView, QAbstractItemView, QTabWidget,
                             QLineEdit, QPushButton, QHBoxLayout, QMessageBox, QLabel, QProgressBar,
                             QStyleFactory, QFileDialog, QTreeView, QTextEdit, QDialog)  # 添加 QTextEdit 和 QDialog
from PyQt5.QtCore import Qt, QUrl, QRunnable, QThreadPool, QObject, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QDesktopServices, QColor, QFont, QIcon
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db import get_all_repos, get_starred_repos, get_followed_users, init_database
from app.github import get_github_repos
from app.upload import upload_repo

class AsyncWorker(QRunnable):
    class Signals(QObject):
        result = pyqtSignal(object)
        error = pyqtSignal(Exception)

    def __init__(self, coro):
        super().__init__()
        self.coro = coro
        self.signals = self.Signals()

    @pyqtSlot()
    def run(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self.coro)
            self.signals.result.emit(result)
        except Exception as e:
            self.signals.error.emit(e)
        finally:
            loop.close()

class ErrorDialog(QDialog):
    def __init__(self, error_message, parent=None):
        super().__init__(parent)
        self.setWindowTitle("错误")
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)
        
        error_text = QTextEdit(self)
        error_text.setPlainText(error_message)
        error_text.setReadOnly(True)
        layout.addWidget(error_text)
        
        copy_button = QPushButton("复制错误信息", self)
        copy_button.clicked.connect(lambda: QApplication.clipboard().setText(error_message))
        layout.addWidget(copy_button)
        
        close_button = QPushButton("关闭", self)
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)

class HyperlinkItem(QTableWidgetItem):
    def __init__(self, text, url):
        super().__init__(text)
        self.url = url
        self.setForeground(QColor('blue'))
        self.setFlags(self.flags() | Qt.ItemIsSelectable)

class RepoViewer(QMainWindow):
    def __init__(self, db_path):
        super().__init__()
        self.db_path = db_path
        self.threadpool = QThreadPool()
        self.token = None
        self.token_file = os.path.join(os.path.dirname(db_path), 'github_token.json')
        self.load_token()
        self.initUI()
        self.load_data()

    def initUI(self):
        self.setWindowTitle('GitHub 信息查看器')
        self.setGeometry(100, 100, 1000, 600)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f0f0;
            }
            QTableWidget {
                background-color: white;
                gridline-color: #d0d0d0;
            }
            QTableWidget::item:selected {
                background-color: #a8d8ea;
            }
            QHeaderView::section {
                background-color: #e0e0e0;
                padding: 4px;
                border: 1px solid #d0d0d0;
                font-weight: bold;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 5px 15px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QLineEdit {
                padding: 5px;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
            }
        """)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()
        central_widget.setLayout(layout)

        # 添加标题
        title_label = QLabel("GitHub 仓库管理器")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setFont(QFont("Arial", 18, QFont.Bold))
        layout.addWidget(title_label)

        # 修改 Token 输入框和保存按钮
        token_layout = QHBoxLayout()
        token_label = QLabel("GitHub Token:")
        self.token_input = QLineEdit()
        self.token_input.setPlaceholderText("输入您的GitHub个人访问令牌")
        if self.token:
            self.token_input.setText(self.token)
            self.token_input.setEnabled(False)
        save_token_button = QPushButton("保存 Token")
        save_token_button.clicked.connect(self.save_token)
        token_layout.addWidget(token_label)
        token_layout.addWidget(self.token_input)
        token_layout.addWidget(save_token_button)
        layout.addLayout(token_layout)

        # 添加单独的更新数据按钮
        update_button = QPushButton("更新数据")
        update_button.clicked.connect(self.update_data)
        layout.addWidget(update_button)

        # 添加上传按钮
        upload_button = QPushButton("上传到GitHub")
        upload_button.clicked.connect(self.upload_repo)
        layout.addWidget(upload_button)

        # 添加文件和文件夹选择功能
        self.add_file_folder_selection_ui(layout)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self.original_repos_table = self.create_table()
        self.fork_repos_table = self.create_table()
        self.starred_table = self.create_table()
        self.followed_table = self.create_table()

        self.tabs.addTab(self.original_repos_table, "原创仓库")
        self.tabs.addTab(self.fork_repos_table, "Fork 仓库")
        self.tabs.addTab(self.starred_table, "标星的仓库")
        self.tabs.addTab(self.followed_table, "关注的作者")

    def create_table(self):
        table = QTableWidget()
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setAlternatingRowColors(True)
        table.cellClicked.connect(self.open_url)
        return table

    def load_token(self):
        if os.path.exists(self.token_file):
            with open(self.token_file, 'r') as f:
                data = json.load(f)
                self.token = data.get('token')

    def save_token(self):
        token = self.token_input.text()
        if not token:
            QMessageBox.warning(self, "错误", "请输入GitHub个人访问令牌")
            return
        self.token = token
        self.token_input.setEnabled(False)
        with open(self.token_file, 'w') as f:
            json.dump({'token': token}, f)
        QMessageBox.information(self, "成功", "Token 已保存")

    def update_data(self):
        if not self.token:
            QMessageBox.warning(self, "错误", "请先保存 GitHub Token")
            return

        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # 设置为忙碌状态

        worker = AsyncWorker(self.update_github_data(self.token))
        worker.signals.result.connect(self.on_update_complete)
        worker.signals.error.connect(self.on_error)
        self.threadpool.start(worker)

    async def update_github_data(self, token):
        await init_database(self.db_path)
        await get_github_repos(token, self.db_path)

    def on_update_complete(self):
        self.progress_bar.setVisible(False)
        QMessageBox.information(self, "更新完成", "GitHub数据已更新")
        self.load_data()

    def on_error(self, error):
        self.progress_bar.setVisible(False)
        error_message = f"发生错误: {str(error)}"
        error_dialog = ErrorDialog(error_message, self)
        error_dialog.exec_()

    def load_data(self):
        self.load_repos_data()
        self.load_starred_data()
        self.load_followed_data()

    def load_repos_data(self):
        worker = AsyncWorker(get_all_repos(self.db_path))
        worker.signals.result.connect(self.on_repos_loaded)
        worker.signals.error.connect(self.on_error)
        self.threadpool.start(worker)

    def on_repos_loaded(self, repos):
        if not repos:
            QMessageBox.information(self, "无数据", "数据库中没有仓库信息，请更新数据")
            return

        original_repos = [repo for repo in repos if not repo['is_fork']]
        fork_repos = [repo for repo in repos if repo['is_fork']]

        self.populate_repos_table(self.original_repos_table, original_repos, include_fork_info=False)
        self.populate_repos_table(self.fork_repos_table, fork_repos, include_fork_info=True)

    def populate_repos_table(self, table, repos, include_fork_info=False):
        table.setRowCount(len(repos))
        if include_fork_info:
            table.setColumnCount(6)
            table.setHorizontalHeaderLabels(['名称', '描述', '星标数', '原仓库', '原仓库URL', '更新时间'])
        else:
            table.setColumnCount(4)
            table.setHorizontalHeaderLabels(['名称', '描述', '星标数', '更新时间'])

        for row, repo in enumerate(repos):
            table.setItem(row, 0, HyperlinkItem(repo['name'], repo['html_url']))
            table.setItem(row, 1, QTableWidgetItem(self.truncate_text(repo.get('description', '') or '', 30)))
            table.setItem(row, 2, QTableWidgetItem(str(repo.get('stargazers_count', 0))))  # 删除多余的右括号
            
            if include_fork_info:
                table.setItem(row, 3, QTableWidgetItem(repo.get('parent_full_name', '') or ''))
                if repo.get('parent_html_url'):
                    table.setItem(row, 4, HyperlinkItem('链接', repo['parent_html_url']))
                else:
                    table.setItem(row, 4, QTableWidgetItem(''))
                table.setItem(row, 5, QTableWidgetItem(repo.get('updated_at', 'N/A')))
            else:
                table.setItem(row, 3, QTableWidgetItem(repo.get('updated_at', 'N/A')))

            table.item(row, 1).setToolTip(repo.get('description', '') or '')

        table.resizeColumnsToContents()
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)

    def load_starred_data(self):
        worker = AsyncWorker(get_starred_repos(self.db_path))
        worker.signals.result.connect(self.on_starred_loaded)
        worker.signals.error.connect(self.on_error)
        self.threadpool.start(worker)

    def on_starred_loaded(self, repos):
        if not repos:
            return  # 如果没有标星的仓库，不显示任何内容

        self.starred_table.setRowCount(len(repos))
        self.starred_table.setColumnCount(4)
        self.starred_table.setHorizontalHeaderLabels(['名称', '描述', '星标数', '所有者'])

        for row, repo in enumerate(repos):
            self.starred_table.setItem(row, 0, HyperlinkItem(repo['name'], repo['html_url']))
            self.starred_table.setItem(row, 1, QTableWidgetItem(self.truncate_text(repo['description'] or '', 30)))
            self.starred_table.setItem(row, 2, QTableWidgetItem(str(repo['stargazers_count'])))
            self.starred_table.setItem(row, 3, QTableWidgetItem(repo['owner_login']))

            self.starred_table.item(row, 1).setToolTip(repo['description'] or '')

        self.starred_table.resizeColumnsToContents()
        self.starred_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)

    def load_followed_data(self):
        worker = AsyncWorker(get_followed_users(self.db_path))
        worker.signals.result.connect(self.on_followed_loaded)
        worker.signals.error.connect(self.on_error)
        self.threadpool.start(worker)

    def on_followed_loaded(self, users):
        if not users:
            return  # 如果没有关注的用户，不显示任何内容

        self.followed_table.setRowCount(len(users))
        self.followed_table.setColumnCount(2)
        self.followed_table.setHorizontalHeaderLabels(['用户名', '主页'])

        for row, user in enumerate(users):
            self.followed_table.setItem(row, 0, QTableWidgetItem(user['login']))
            self.followed_table.setItem(row, 1, HyperlinkItem('GitHub主页', user['html_url']))

        self.followed_table.resizeColumnsToContents()
        self.followed_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)

    def truncate_text(self, text, max_length):
        return (text[:max_length] + '...') if len(text) > max_length else text

    def open_url(self, row, column):
        item = self.tabs.currentWidget().item(row, column)
        if isinstance(item, HyperlinkItem):
            QDesktopServices.openUrl(QUrl(item.url))

    def add_file_folder_selection_ui(self, layout):
        file_folder_layout = QHBoxLayout()
        
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("选择文件或文件夹路径")
        select_file_button = QPushButton("选择文件")
        select_file_button.clicked.connect(self.select_file)
        select_folder_button = QPushButton("选择文件夹")
        select_folder_button.clicked.connect(self.select_folder)
        
        file_folder_layout.addWidget(self.path_input)
        file_folder_layout.addWidget(select_file_button)
        file_folder_layout.addWidget(select_folder_button)
        
        layout.addLayout(file_folder_layout)

    def select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择文件")
        if file_path:
            current_paths = self.path_input.text().split(", ") if self.path_input.text() else []
            current_paths.append(file_path)
            self.path_input.setText(", ".join(current_paths))

    def select_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if folder_path:
            current_paths = self.path_input.text().split(", ") if self.path_input.text() else []
            current_paths.append(folder_path)
            self.path_input.setText(", ".join(current_paths))

    def upload_repo(self):
        if not self.token:
            QMessageBox.warning(self, "错误", "请先保存 GitHub Token")
            return

        paths = [path.strip() for path in self.path_input.text().split(",") if path.strip()]
        
        if not paths:
            QMessageBox.warning(self, "错误", "请选择至少一个文件或文件夹")
            return
        
        # 获取选择的文件或文件夹的名称作为仓库名
        repo_name = os.path.basename(paths[0])
        description = f"Uploaded from local path: {paths[0]}"
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # 设置为忙碌状态
        
        worker = AsyncWorker(upload_repo(self.token, repo_name, description, self.db_path, paths))
        worker.signals.result.connect(self.on_upload_complete)
        worker.signals.error.connect(self.on_upload_error)
        self.threadpool.start(worker)
    
    def on_upload_complete(self, result):
        self.progress_bar.setVisible(False)
        success, message = result
        if success:
            QMessageBox.information(self, "上传成功", message)
            self.load_data()  # 刷新数据
        else:
            error_dialog = ErrorDialog(message, self)
            error_dialog.exec_()

    def on_upload_error(self, error):
        self.progress_bar.setVisible(False)
        error_message = f"上传过程中发生错误: {str(error)}"
        error_dialog = ErrorDialog(error_message, self)
        error_dialog.exec_()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create('Fusion'))  # 使用 Fusion 风格
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(script_dir, 'output', 'github_repos.db')
    viewer = RepoViewer(db_path)
    viewer.show()
    sys.exit(app.exec_())