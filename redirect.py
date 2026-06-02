"""Port 80 redirect to 8088"""
from flask import Flask, redirect

app = Flask(__name__)

@app.route('/')
@app.route('/<path:path>')
def catch_all(path=''):
    return redirect(f'http://ip.local:8088/{path}')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)
