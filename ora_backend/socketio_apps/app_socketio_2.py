import sys
from os.path import abspath, dirname

root_dir = dirname(dirname(dirname(abspath(__file__))))
sys.path.append(root_dir)

from ora_backend.views.chat_socketio import app

# from factory import app
from ora_backend.config import SOCKETIO_RUN_CONFIG

if __name__ == "__main__":
    config = {**SOCKETIO_RUN_CONFIG, "port": 8081}
    app.run(**config)
