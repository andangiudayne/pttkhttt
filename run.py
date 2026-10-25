"""Chạy web Pop-up Market:  python run.py  → http://127.0.0.1:5000"""
from chobay import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=False, port=5000)
