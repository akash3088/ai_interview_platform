from flask import Flask, render_template
from config import Config
from routes.auth_routes import auth_bp
from routes.dashboard_routes import dashboard_bp
from routes.interview_routes import interview_bp
from routes.game_routes import game_bp
from routes.about_routes import about_bp




app = Flask(__name__)
app.config.from_object(Config)

app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(interview_bp)
app.register_blueprint(game_bp)
app.register_blueprint(about_bp)

@app.route("/")
def home():
    return render_template("index.html")


if __name__ == "__main__":
    app.run()
