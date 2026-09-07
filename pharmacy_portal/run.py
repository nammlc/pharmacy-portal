from app import create_app

app = create_app()

if __name__ == "__main__":
    # debug=True chỉ dùng khi phát triển, KHÔNG bật khi deploy thật lên server
    app.run(debug=True, host="0.0.0.0", port=5000)
