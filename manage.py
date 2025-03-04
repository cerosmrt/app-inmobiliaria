# manage.py
import sys
from app import app, db
from flask_migrate import Migrate, init, migrate, upgrade

# Configura Flask-Migrate
migrate_obj = Migrate(app, db)  # Renombré a migrate_obj para evitar confusión

if __name__ == "__main__":
    with app.app_context():
        if len(sys.argv) > 1 and sys.argv[1] == "db":
            if len(sys.argv) > 2:
                command = sys.argv[2]
                if command == "init":
                    init()
                elif command == "migrate":
                    migrate()
                elif command == "upgrade":
                    upgrade()
                else:
                    print("Comando no reconocido. Usa: init, migrate, upgrade")
            else:
                print("Uso: python manage.py db [init|migrate|upgrade]")
        else:
            print("Uso: python manage.py db [init|migrate|upgrade]")