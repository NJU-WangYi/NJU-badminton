"""兼容旧的启动方式：python wy.py（等同于 python -m booking）。"""
from booking.__main__ import main

if __name__ == "__main__":
    main()
