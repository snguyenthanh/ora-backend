from ora_backend.views.chat_socketio import app
from ora_backend.config import SOCKETIO_RUN_CONFIG

if __name__ == "__main__":

    app.run(**SOCKETIO_RUN_CONFIG)
