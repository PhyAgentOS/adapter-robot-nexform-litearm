"""PyInstaller 入口：main.py 使用相对导入，不能直接作为脚本打包。"""

from litearm_robot.main import main

if __name__ == "__main__":
    raise SystemExit(main())
