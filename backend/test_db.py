from app import create_app, db

app = create_app()

with app.app_context():
    try:
        # Tester la connexion
        db.engine.connect()
        print("✅ Connexion à PostgreSQL réussie !")
        print(f"📊 Database URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
    except Exception as e:
        print(f"❌ Erreur de connexion : {e}")