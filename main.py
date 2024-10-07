import os
import sys
from PyQt5.QtWidgets import QApplication

# 添加当前目录到 Python 路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

# 使用相对导入
from ui.ui import RepoViewer

def main():
    app = QApplication(sys.argv)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(script_dir, 'output', 'github_repos.db')
    
    print(f"数据库路径: {db_path}")
    
    viewer = RepoViewer(db_path)
    viewer.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()