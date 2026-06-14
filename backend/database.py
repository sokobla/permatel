# This file is kept for backward compatibility
# All database configuration is now in app/__init__.py
# The db instance is created and initialized there

from app import db

__all__ = ['db']