"""Proje kökünü pytest'in import yoluna sokar.

Kök dizinde bir conftest.py bulunması, pytest'in (prepend import modunda) bu
dizini sys.path'e eklemesini sağlar; testler `from core import ...` diyebilir.
Başka bir işlevi yoktur — bilerek boş bırakılmıştır.
"""
