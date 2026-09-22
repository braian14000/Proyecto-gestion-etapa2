#!/usr/bin/env python3
"""
Script para procesar recordatorios de eventos de forma automática.
Puede ser ejecutado cada 1-5 minutos mediante un cron job o scheduler.

Ejemplo de cron (procesar cada minuto):
* * * * * cd /ruta/al/proyecto && python3 src/process_reminders.py

O cada 5 minutos:
*/5 * * * * cd /ruta/al/proyecto && python3 src/process_reminders.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, process_pending_event_reminders
from datetime import datetime

def main():
    """Función principal para procesar recordatorios"""
    print(f"[{datetime.now()}] Iniciando procesamiento de recordatorios...")
    
    try:
        with app.app_context():
            cantidad = process_pending_event_reminders()
            if cantidad > 0:
                print(f"[{datetime.now()}] ✓ Se procesaron {cantidad} recordatorios")
            else:
                print(f"[{datetime.now()}] No hay recordatorios pendientes")
    except Exception as ex:
        print(f"[{datetime.now()}] ✗ Error: {ex}")
        sys.exit(1)

if __name__ == '__main__':
    main()
