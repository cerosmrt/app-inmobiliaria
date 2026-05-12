import os
import secrets


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = 'static/uploads'
    ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png'}
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB

    CONTACTO_TELEFONO = os.environ.get('CONTACTO_TELEFONO', '')
    CONTACTO_WA       = os.environ.get('CONTACTO_WA', '')
    CONTACTO_EMAIL    = os.environ.get('CONTACTO_EMAIL', '')

    MAIL_SMTP = os.environ.get('MAIL_SMTP', '')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USER = os.environ.get('MAIL_USER', '')
    MAIL_PASS = os.environ.get('MAIL_PASS', '')
    MAIL_TO   = os.environ.get('MAIL_TO', '')


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get('DATABASE_URL') or 'sqlite:///inmobiliaria.db'
    )


class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get('DATABASE_URL') or 'sqlite:///inmobiliaria.db'
    )
    SESSION_COOKIE_SECURE   = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'


config = {
    'development': DevelopmentConfig,
    'production':  ProductionConfig,
    'default':     DevelopmentConfig,
}
