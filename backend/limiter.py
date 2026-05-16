"""
Module isolé pour le rate limiter slowapi.
Importé depuis main.py ET les routers sans créer de circular import.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
