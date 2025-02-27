# Importa la instancia de la aplicación y la base de datos desde el módulo 'app'
from app import app, db

# Importa el comando para migrar la base de datos
from flask_migrate import MigrateCommand

# Importa el gestor de comandos para ejecutar tareas desde la terminal
from flask_script import Manager

# Crea una instancia de Manager asociada a la aplicación Flask
manager = Manager(app)

# Añade el comando 'db' para permitir migraciones (inicializar, migrar, actualizar base de datos)
manager.add_command('db', MigrateCommand)

# Ejecuta el gestor de comandos si el script se ejecuta directamente
if __name__ == "__main__":
    manager.run()
