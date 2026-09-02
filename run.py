import eventlet
eventlet.monkey_patch()  # Must be the first thing executed

from app import create_app, socketio

app = create_app()

if __name__ == '__main__':
    print("\n" + "=" * 50)
    print(" MediCore Pro Server Listening at: http://127.0.0.1:5000")
    print(" Press CTRL+C to quit")
    print("=" * 50 + "\n")
    socketio.run(
        app,
        host='127.0.0.1',
        port=5000,
        debug=True,
        use_reloader=False
    )