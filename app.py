"""Development entry point for the F=ma Trainer."""

from app import create_app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
