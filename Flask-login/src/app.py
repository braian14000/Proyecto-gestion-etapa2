from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from flask_mysqldb import MySQL
from flask_wtf.csrf import CSRFProtect
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash

import qrcode
import json
import time
import os
import random
import math
from datetime import datetime, timedelta, date, time as time_obj
import re
import smtplib
from email.mime.text import MIMEText
import uuid
from email.mime.multipart import MIMEMultipart
from werkzeug.utils import secure_filename

from config import config
from models.ModeUsers import ModelUser
from models.entities.users import User
from certificates import generar_certificado

app = Flask(__name__)
app.config.from_object(config['development'])
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024
EVENT_IMAGES_DIR = os.path.join(app.static_folder, 'eventos')
os.makedirs(EVENT_IMAGES_DIR, exist_ok=True)

# Configuración de Gmail para soporte
GMAIL_USER = "gestioneventocontrasena12@gmail.com"
GMAIL_PASS = "lxbvaaiwjwnhtjni" 
SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL", GMAIL_USER)

db = MySQL(app)


def ensure_event_table_has_capacity():
    try:
        with app.app_context():
            cursor = db.connection.cursor()
            cursor.execute("SHOW TABLES LIKE 'event'")
            if cursor.fetchone() is None:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS `event` (
                      `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
                      `titulo` VARCHAR(200) NOT NULL,
                      `fecha` DATE NOT NULL,
                      `hora` TIME NOT NULL DEFAULT '09:00:00',
                      `descripcion` TEXT,
                      `lugar` VARCHAR(200),
                      `capacidad_maxima` INT NOT NULL DEFAULT 1,
                      `finalizado` TINYINT(1) NOT NULL DEFAULT 0,
                      `categoria` VARCHAR(100) DEFAULT 'General',
                      `latitud` DECIMAL(10, 7) NULL,
                      `longitud` DECIMAL(10, 7) NULL,
                      `imagen` VARCHAR(255) NULL,
                      `created_by` INT UNSIGNED NULL,
                      `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                      PRIMARY KEY (`id`)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                    """
                )
                db.connection.commit()
                print("[INFO] Se creó la tabla event con capacidad_maxima y finalizado.")
                return

            cursor.execute("SHOW COLUMNS FROM `event` LIKE 'capacidad_maxima'")
            if cursor.fetchone() is None:
                cursor.execute("ALTER TABLE `event` ADD COLUMN `capacidad_maxima` INT NOT NULL DEFAULT 1")
                db.connection.commit()
                print("[INFO] Se agregó la columna capacidad_maxima a la tabla event.")

            cursor.execute("SHOW COLUMNS FROM `event` LIKE 'hora'")
            if cursor.fetchone() is None:
                cursor.execute("ALTER TABLE `event` ADD COLUMN `hora` TIME NOT NULL DEFAULT '09:00:00'")
                db.connection.commit()
                print("[INFO] Se agregó la columna hora a la tabla event.")

            cursor.execute("SHOW COLUMNS FROM `event` LIKE 'finalizado'")
            if cursor.fetchone() is None:
                cursor.execute("ALTER TABLE `event` ADD COLUMN `finalizado` TINYINT(1) NOT NULL DEFAULT 0")
                db.connection.commit()
                print("[INFO] Se agregó la columna finalizado a la tabla event.")

            cursor.execute("SHOW COLUMNS FROM `event` LIKE 'categoria'")
            if cursor.fetchone() is None:
                cursor.execute("ALTER TABLE `event` ADD COLUMN `categoria` VARCHAR(100) DEFAULT 'General'")
                db.connection.commit()
                print("[INFO] Se agregó la columna categoria a la tabla event.")

            cursor.execute("SHOW COLUMNS FROM `event` LIKE 'latitud'")
            if cursor.fetchone() is None:
                cursor.execute("ALTER TABLE `event` ADD COLUMN `latitud` DECIMAL(10, 7) NULL")
                db.connection.commit()
                print("[INFO] Se agregó la columna latitud a la tabla event.")

            cursor.execute("SHOW COLUMNS FROM `event` LIKE 'longitud'")
            if cursor.fetchone() is None:
                cursor.execute("ALTER TABLE `event` ADD COLUMN `longitud` DECIMAL(10, 7) NULL")
                db.connection.commit()
                print("[INFO] Se agregó la columna longitud a la tabla event.")

            cursor.execute("SHOW COLUMNS FROM `event` LIKE 'imagen'")
            if cursor.fetchone() is None:
                cursor.execute("ALTER TABLE `event` ADD COLUMN `imagen` VARCHAR(255) NULL")
                db.connection.commit()
                print("[INFO] Se agregó la columna imagen a la tabla event.")
    except Exception as ex:
        print(f"[WARN] No se pudo asegurar la estructura de la tabla event: {ex}")


ensure_event_table_has_capacity()

def ensure_registration_confirmation_columns():
    try:
        with app.app_context():
            cursor = db.connection.cursor()
            cursor.execute("SHOW COLUMNS FROM `registrados` LIKE 'confirmado_at'")
            if cursor.fetchone() is None:
                cursor.execute("ALTER TABLE `registrados` ADD COLUMN `confirmado_at` DATETIME NULL")
            cursor.execute("SHOW COLUMNS FROM `registrados` LIKE 'metodo_confirmacion'")
            if cursor.fetchone() is None:
                cursor.execute("ALTER TABLE `registrados` ADD COLUMN `metodo_confirmacion` VARCHAR(10) NULL")
            db.connection.commit()
    except Exception as ex:
        print(f"[WARN] No se pudieron asegurar los datos de confirmación: {ex}")


ensure_registration_confirmation_columns()

def archive_event_history(event_id):
    cursor = db.connection.cursor()
    cursor.execute(
        """
        SELECT id, titulo, fecha, hora, descripcion, lugar,
               capacidad_maxima, finalizado, categoria, created_by, created_at
        FROM event
        WHERE id = %s
        """,
        (event_id,)
    )
    event = cursor.fetchone()
    if not event:
        raise ValueError(f'No se encontró el evento {event_id} para archivarlo.')

    cursor.execute(
        """
        SELECT r.nombre_usuario, u.email, r.confirmado_at, r.metodo_confirmacion
        FROM registrados r
        LEFT JOIN `user` u ON u.dni COLLATE utf8mb4_general_ci = r.dni_usuario COLLATE utf8mb4_general_ci
        WHERE r.evento_id = %s
        ORDER BY r.created_at, r.id
        """,
        (event_id,)
    )
    registrations = [
        {
            'nombre': registration[0],
            'gmail': registration[1],
            'confirmado_at': registration[2],
            'metodo_confirmacion': registration[3]
        }
        for registration in cursor.fetchall()
    ]
    archive = {
        'evento': {
            'id': event[0],
            'titulo': event[1],
            'fecha': event[2],
            'hora': event[3],
            'descripcion': event[4],
            'lugar': event[5],
            'capacidad_maxima': event[6],
            'finalizado': bool(event[7]),
            'categoria': event[8],
            'created_by': event[9],
            'created_at': event[10]
        },
        'inscriptos': registrations,
        'guardado_en': datetime.now().isoformat(timespec='seconds')
    }
    archive_dir = os.path.join(app.instance_path, 'historial_eventos')
    os.makedirs(archive_dir, exist_ok=True)
    archive_path = os.path.join(archive_dir, f'evento_{event_id}.json')
    temporary_path = f'{archive_path}.tmp'
    with open(temporary_path, 'w', encoding='utf-8') as archive_file:
        json.dump(archive, archive_file, ensure_ascii=False, indent=2, default=str)
    os.replace(temporary_path, archive_path)

def save_event_image(image_file):
    if not image_file or not image_file.filename:
        return None
    allowed_extensions = {'jpg', 'jpeg', 'png', 'webp'}
    original_name = secure_filename(image_file.filename)
    extension = original_name.rsplit('.', 1)[-1].lower() if '.' in original_name else ''
    if extension not in allowed_extensions:
        raise ValueError('La imagen debe ser JPG, PNG o WEBP.')
    filename = f'{uuid.uuid4().hex}.{extension}'
    image_file.save(os.path.join(EVENT_IMAGES_DIR, filename))
    return f'eventos/{filename}'

def ensure_organizer_requests_table():
    try:
        with app.app_context():
            cursor = db.connection.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS organizer_role_requests (
                  id INT UNSIGNED NOT NULL AUTO_INCREMENT,
                  user_id INT UNSIGNED NOT NULL,
                  status ENUM('pendiente', 'aprobada', 'rechazada') NOT NULL DEFAULT 'pendiente',
                  requested_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  reviewed_at DATETIME NULL,
                  reviewed_by INT UNSIGNED NULL,
                  PRIMARY KEY (id),
                  KEY idx_organizer_requests_user (user_id),
                  KEY idx_organizer_requests_status (status)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """
            )
            db.connection.commit()
    except Exception as ex:
        print(f"[WARN] No se pudo asegurar la tabla de solicitudes: {ex}")

def ensure_notifications_table():
    try:
        with app.app_context():
            cursor = db.connection.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS mensajes_organizador (
                  id INT UNSIGNED NOT NULL AUTO_INCREMENT,
                  organizador_id INT UNSIGNED NOT NULL,
                  remitente_id INT UNSIGNED,
                  evento_id INT UNSIGNED NOT NULL,
                  asunto VARCHAR(255) NOT NULL,
                  mensaje TEXT NOT NULL,
                  leido TINYINT(1) DEFAULT 0,
                  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  PRIMARY KEY (id),
                  KEY idx_organizador (organizador_id),
                  KEY idx_evento (evento_id),
                  KEY idx_leido (leido),
                  FOREIGN KEY (organizador_id) REFERENCES `user`(id),
                  FOREIGN KEY (remitente_id) REFERENCES `user`(id),
                  FOREIGN KEY (evento_id) REFERENCES event(id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """
            )
            db.connection.commit()
            print("[INFO] Tabla mensajes_organizador creada/verificada.")
    except Exception as ex:
        print(f"[WARN] No se pudo asegurar la tabla de notificaciones: {ex}")


def build_system_event_reminder_message(evento_fecha, evento_hora, evento_titulo, ahora=None):
    """Genera un recordatorio con el tiempo restante real hasta el evento."""
    ahora = ahora or datetime.now()

    if isinstance(evento_fecha, str):
        try:
            fecha_objetivo = datetime.strptime(evento_fecha, '%Y-%m-%d')
        except ValueError:
            fecha_objetivo = ahora
    else:
        fecha_objetivo = evento_fecha

    hora_objetivo = evento_hora or '00:00:00'
    if isinstance(hora_objetivo, str):
        try:
            hora_dt = datetime.strptime(hora_objetivo, '%H:%M:%S')
        except ValueError:
            try:
                hora_dt = datetime.strptime(hora_objetivo, '%H:%M')
            except ValueError:
                hora_dt = datetime.strptime('00:00', '%H:%M')
    elif isinstance(hora_objetivo, timedelta):
        total_seconds = int(hora_objetivo.total_seconds())
        hora_dt = datetime.min + timedelta(seconds=total_seconds)
    else:
        hora_dt = hora_objetivo

    fecha_evento = fecha_objetivo.date() if isinstance(fecha_objetivo, datetime) else fecha_objetivo
    fecha_hora_evento = datetime.combine(fecha_evento, hora_dt.time())
    delta = fecha_hora_evento - ahora

    if delta.total_seconds() <= 0:
        return f"Recordatorio: estás anotado al evento {evento_titulo}, que es el {fecha_objetivo.strftime('%d/%m/%Y')}"

    dias = delta.days
    horas = delta.seconds // 3600
    minutos = (delta.seconds % 3600) // 60

    if dias > 0:
        if horas > 0 and minutos > 0:
            restante = f"{dias} día(s), {horas} hora(s) y {minutos} minuto(s)"
        elif horas > 0:
            restante = f"{dias} día(s) y {horas} hora(s)"
        else:
            restante = f"{dias} día(s)"
    elif horas > 0:
        restante = f"{horas} hora(s)"
    elif minutos > 0:
        restante = f"{minutos} minuto(s)"
    else:
        restante = 'menos de 1 minuto'

    return f"Recordatorio: estás anotado al evento {evento_titulo}. Es el {fecha_objetivo.strftime('%d/%m/%Y')} y faltan {restante}"


def build_event_change_message(evento_titulo, fecha_anterior, hora_anterior, fecha_nueva, hora_nueva):
    """Crea el mensaje de cambio de fecha/horario para anotados."""
    mensaje = f"Se actualizó el evento {evento_titulo}."
    if fecha_anterior and fecha_nueva and fecha_anterior != fecha_nueva:
        mensaje += f" Fecha: {fecha_anterior} → {fecha_nueva}."
    if hora_anterior and hora_nueva and hora_anterior != hora_nueva:
        mensaje += f" Horario: {hora_anterior} → {hora_nueva}."
    if not (fecha_anterior and fecha_nueva and fecha_anterior != fecha_nueva) and not (hora_anterior and hora_nueva and hora_anterior != hora_nueva):
        mensaje += " Revisá los detalles del evento para confirmar el cambio."
    return mensaje


def get_recent_user_notifications(user_id, limit=6):
    """Devuelve solo cambios de eventos para el panel lateral."""
    try:
        cursor = db.connection.cursor()
        cursor.execute(
            """
            SELECT id, asunto, mensaje, created_at, leido
            FROM mensajes_organizador
            WHERE organizador_id = %s
              AND remitente_id IS NULL
                            AND asunto = 'Cambio de evento'
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (user_id, limit)
        )
        rows = cursor.fetchall()
        return [{
            'id': row[0],
            'asunto': row[1] or 'Sistema',
            'mensaje': row[2],
            'created_at': row[3].strftime('%d/%m/%Y %H:%M') if hasattr(row[3], 'strftime') else str(row[3]),
            'leido': bool(row[4])
        } for row in rows]
    except Exception as ex:
        print(f"[WARN] Error obteniendo notificaciones recientes del sistema: {ex}")
        return []


def get_unread_event_changes_count(user_id):
    """Cuenta cambios de eventos no leídos para la bolita del panel lateral."""
    try:
        cursor = db.connection.cursor()
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM mensajes_organizador
            WHERE organizador_id = %s
              AND remitente_id IS NULL
              AND asunto = 'Cambio de evento'
              AND leido = 0
            """,
            (user_id,)
        )
        return cursor.fetchone()[0]
    except Exception as ex:
        print(f"[WARN] Error contando cambios de eventos no leídos: {ex}")
        return 0


def notify_event_change_to_registered_users(evento_id, evento_titulo, fecha_anterior, hora_anterior, fecha_nueva, hora_nueva, organizador_id):
    """Notifica a todos los usuarios anotados cuando cambia fecha o horario del evento."""
    try:
        if not evento_id or not evento_titulo:
            return
        if not ((fecha_anterior and fecha_nueva and fecha_anterior != fecha_nueva) or (hora_anterior and hora_nueva and hora_anterior != hora_nueva)):
            return

        cursor = db.connection.cursor()
        cursor.execute(
            """
            SELECT DISTINCT u.id
            FROM registrados r
            JOIN `user` u ON u.dni COLLATE utf8mb4_general_ci = r.dni_usuario COLLATE utf8mb4_general_ci
            WHERE r.evento_id = %s AND u.id IS NOT NULL
            """,
            (evento_id,)
        )
        usuarios = cursor.fetchall()
        if not usuarios:
            return

        mensaje = build_event_change_message(evento_titulo, fecha_anterior, hora_anterior, fecha_nueva, hora_nueva)
        for (usuario_id,) in usuarios:
            cursor.execute(
                """
                SELECT id
                FROM mensajes_organizador
                WHERE organizador_id = %s AND evento_id = %s AND remitente_id IS NULL AND asunto = 'Cambio de evento' AND mensaje = %s
                LIMIT 1
                """,
                (usuario_id, evento_id, mensaje)
            )
            if cursor.fetchone() is None:
                cursor.execute(
                    """
                    INSERT INTO mensajes_organizador (organizador_id, remitente_id, evento_id, asunto, mensaje, leido)
                    VALUES (%s, NULL, %s, 'Cambio de evento', %s, 0)
                    """,
                    (usuario_id, evento_id, mensaje)
                )
        db.connection.commit()
        print(f"[INFO] Se enviaron cambios del evento {evento_id} a {len(usuarios)} usuarios anotados.")
    except Exception as ex:
        db.connection.rollback()
        print(f"[WARN] No se pudieron notificar cambios del evento {evento_id}: {ex}")


def ensure_system_event_reminders(usuario_id=None, evento_id=None):
    """Crea o actualiza recordatorios del sistema para eventos futuros del usuario."""
    try:
        cursor = db.connection.cursor()

        if usuario_id is not None:
            if evento_id is not None:
                cursor.execute(
                    """
                                        SELECT e.id, e.titulo, e.fecha, e.hora
                                        FROM event e
                                        WHERE e.id = %s
                                            AND TIMESTAMP(e.fecha, e.hora) > NOW()
                                            AND TIMESTAMP(e.fecha, e.hora) <= DATE_ADD(NOW(), INTERVAL 24 HOUR)
                    """,
                                        (evento_id,)
                )
            else:
                cursor.execute(
                    """
                    SELECT r.evento_id, e.titulo, e.fecha, e.hora
                    FROM registrados r
                    JOIN event e ON e.id = r.evento_id
                    JOIN `user` u ON u.dni COLLATE utf8mb4_general_ci = r.dni_usuario COLLATE utf8mb4_general_ci
                                        WHERE u.id = %s
                                            AND TIMESTAMP(e.fecha, e.hora) > NOW()
                                            AND TIMESTAMP(e.fecha, e.hora) <= DATE_ADD(NOW(), INTERVAL 24 HOUR)
                    """,
                    (usuario_id,)
                )
        else:
            cursor.execute(
                """
                SELECT r.evento_id, e.titulo, e.fecha, e.hora, u.id AS usuario_id
                FROM registrados r
                JOIN event e ON e.id = r.evento_id
                JOIN `user` u ON u.dni COLLATE utf8mb4_general_ci = r.dni_usuario COLLATE utf8mb4_general_ci
                                WHERE TIMESTAMP(e.fecha, e.hora) > NOW()
                                    AND TIMESTAMP(e.fecha, e.hora) <= DATE_ADD(NOW(), INTERVAL 24 HOUR)
                """
            )
            rows = cursor.fetchall()
            for evento_id_row, titulo, fecha_evento, hora_evento, usuario_id_row in rows:
                if usuario_id_row is None:
                    continue
                mensaje = build_system_event_reminder_message(fecha_evento, hora_evento, titulo)
                cursor.execute(
                    """
                    SELECT id
                    FROM mensajes_organizador
                    WHERE organizador_id = %s AND evento_id = %s AND remitente_id IS NULL AND asunto = 'Sistema'
                    LIMIT 1
                    """,
                    (usuario_id_row, evento_id_row)
                )
                existente = cursor.fetchone()
                if existente:
                    cursor.execute(
                        "UPDATE mensajes_organizador SET mensaje = %s, leido = 0 WHERE id = %s",
                        (mensaje, existente[0])
                    )
                else:
                    cursor.execute(
                        """
                        INSERT INTO mensajes_organizador (organizador_id, remitente_id, evento_id, asunto, mensaje, leido)
                        VALUES (%s, NULL, %s, 'Sistema', %s, 0)
                        """,
                        (usuario_id_row, evento_id_row, mensaje)
                    )
            db.connection.commit()
            return

        rows = cursor.fetchall()
        for evento_id_row, titulo, fecha_evento, hora_evento in rows:
            mensaje = build_system_event_reminder_message(fecha_evento, hora_evento, titulo)
            cursor.execute(
                """
                SELECT id
                FROM mensajes_organizador
                WHERE organizador_id = %s AND evento_id = %s AND remitente_id IS NULL AND asunto = 'Sistema'
                LIMIT 1
                """,
                (usuario_id, evento_id_row)
            )
            existente = cursor.fetchone()
            if existente:
                cursor.execute(
                    "UPDATE mensajes_organizador SET mensaje = %s, leido = 0 WHERE id = %s",
                    (mensaje, existente[0])
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO mensajes_organizador (organizador_id, remitente_id, evento_id, asunto, mensaje, leido)
                    VALUES (%s, NULL, %s, 'Sistema', %s, 0)
                    """,
                    (usuario_id, evento_id_row, mensaje)
                )
        db.connection.commit()
    except Exception as ex:
        db.connection.rollback()
        print(f"[WARN] No se pudieron generar los recordatorios del sistema: {ex}")


def create_event_reminders(usuario_id, evento_id, evento_titulo, evento_fecha, evento_hora):
    """Crea 3 recordatorios automáticos para un evento: inmediato, 1 día antes y 1 hora antes"""
    try:
        cursor = db.connection.cursor()
        
        # Convertir fecha y hora a datetime
        if isinstance(evento_fecha, str):
            fecha_dt = datetime.strptime(evento_fecha, '%Y-%m-%d').date()
        else:
            fecha_dt = evento_fecha if hasattr(evento_fecha, 'date') is False else evento_fecha.date() if hasattr(evento_fecha, 'date') else evento_fecha
        
        if isinstance(evento_hora, str):
            try:
                hora_dt = datetime.strptime(evento_hora, '%H:%M:%S').time()
            except ValueError:
                hora_dt = datetime.strptime(evento_hora, '%H:%M').time()
        elif isinstance(evento_hora, timedelta):
            total_seconds = int(evento_hora.total_seconds())
            hora_dt = (datetime.min + timedelta(seconds=total_seconds)).time()
        else:
            hora_dt = evento_hora.time() if hasattr(evento_hora, 'time') else datetime.min.time()
        
        fecha_hora_evento = datetime.combine(fecha_dt, hora_dt)
        
        mensaje_inmediato = f"RECORDATORIO: El evento {evento_titulo} comienza en {fecha_dt.strftime('%d/%m/%Y')} a las {hora_dt.strftime('%H:%M')}"
        fecha_1dia_antes = fecha_hora_evento - timedelta(days=1)
        mensaje_1dia = f"RECORDATORIO: El evento {evento_titulo} comienza mañana {fecha_dt.strftime('%d/%m/%Y')} a las {hora_dt.strftime('%H:%M')}"
        fecha_1hora_antes = fecha_hora_evento - timedelta(hours=1)
        mensaje_1hora = f"RECORDATORIO: El evento {evento_titulo} comienza en 1 hora (a las {hora_dt.strftime('%H:%M')})"

        recordatorios = [
            ('inmediato', mensaje_inmediato, datetime.now()),
            ('1_dia_antes', mensaje_1dia, fecha_1dia_antes),
            ('1_hora_antes', mensaje_1hora, fecha_1hora_antes),
        ]
        ahora = datetime.now()
        for tipo, mensaje, fecha_programada in recordatorios:
            if tipo != 'inmediato' and fecha_programada <= ahora:
                continue
            cursor.execute(
                """
                SELECT id
                FROM recordatorios_eventos
                WHERE usuario_id = %s AND evento_id = %s AND tipo = %s
                LIMIT 1
                """,
                (usuario_id, evento_id, tipo)
            )
            if cursor.fetchone() is None:
                cursor.execute(
                    """
                    INSERT INTO recordatorios_eventos (usuario_id, evento_id, tipo, mensaje, fecha_programada, enviado)
                    VALUES (%s, %s, %s, %s, %s, 0)
                    """,
                    (usuario_id, evento_id, tipo, mensaje, fecha_programada)
                )
        
        db.connection.commit()
        print(f"[INFO] Se crearon 3 recordatorios para usuario {usuario_id}, evento {evento_id}")
    except Exception as ex:
        db.connection.rollback()
        print(f"[ERROR] Error creando recordatorios: {ex}")


def process_pending_event_reminders():
    """Procesa los recordatorios que han llegado su hora de envío"""
    try:
        cursor = db.connection.cursor()
        
        # Obtener todos los recordatorios que tienen que ser enviados
        cursor.execute(
            """
            SELECT r.id, r.usuario_id, r.evento_id, r.tipo, r.mensaje, e.titulo, e.fecha, e.hora
            FROM recordatorios_eventos r
            JOIN event e ON e.id = r.evento_id
            WHERE r.enviado = 0 AND r.fecha_programada <= NOW()
            ORDER BY r.fecha_programada ASC
            LIMIT 100
            """
        )
        recordatorios = cursor.fetchall()
        
        enviados = 0
        for recordatorio in recordatorios:
            recordatorio_id, usuario_id, evento_id, tipo, mensaje, titulo, fecha, hora = recordatorio
            
            try:
                # Crear la notificación en mensajes_organizador
                cursor.execute(
                    """
                    INSERT INTO mensajes_organizador (organizador_id, remitente_id, evento_id, asunto, mensaje, leido)
                    VALUES (%s, NULL, %s, 'RECORDATORIO', %s, 0)
                    """,
                    (usuario_id, evento_id, mensaje)
                )
                
                # Marcar el recordatorio como enviado
                cursor.execute("UPDATE recordatorios_eventos SET enviado = 1 WHERE id = %s", (recordatorio_id,))
                
                db.connection.commit()
                enviados += 1
                print(f"[INFO] Recordatorio enviado: usuario={usuario_id}, evento={evento_id}, tipo={tipo}")
            except Exception as ex:
                db.connection.rollback()
                print(f"[ERROR] Error procesando recordatorio {recordatorio_id}: {ex}")
        
        print(f"[INFO] Se procesaron {enviados} recordatorios")
        return enviados
    except Exception as ex:
        print(f"[ERROR] Error en process_pending_event_reminders: {ex}")
        return 0


def ensure_followers_table():
    try:
        with app.app_context():
            cursor = db.connection.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS seguidores (
                  id INT UNSIGNED NOT NULL AUTO_INCREMENT,
                  seguidor_id INT UNSIGNED NOT NULL,
                  seguido_id INT UNSIGNED NOT NULL,
                  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  PRIMARY KEY (id),
                  UNIQUE KEY unique_seguidor (seguidor_id, seguido_id),
                  KEY idx_seguido (seguido_id),
                  FOREIGN KEY (seguidor_id) REFERENCES `user`(id),
                  FOREIGN KEY (seguido_id) REFERENCES `user`(id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """
            )
            db.connection.commit()
            print("[INFO] Tabla seguidores creada/verificada.")
    except Exception as ex:
        print(f"[WARN] No se pudo asegurar la tabla de seguidores: {ex}")

def ensure_replies_table():
    try:
        with app.app_context():
            cursor = db.connection.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS respuestas_organizador (
                  id INT UNSIGNED NOT NULL AUTO_INCREMENT,
                  mensaje_id INT UNSIGNED NOT NULL,
                  organizador_id INT UNSIGNED NOT NULL,
                  destinatario_id INT UNSIGNED NULL,
                  autor_id INT UNSIGNED NULL,
                  respuesta TEXT NOT NULL,
                  leido_destinatario TINYINT(1) NOT NULL DEFAULT 0,
                  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  PRIMARY KEY (id),
                  KEY idx_mensaje (mensaje_id),
                  KEY idx_organizador (organizador_id),
                  KEY idx_destinatario (destinatario_id),
                  KEY idx_autor (autor_id),
                  FOREIGN KEY (mensaje_id) REFERENCES mensajes_organizador(id),
                  FOREIGN KEY (organizador_id) REFERENCES `user`(id),
                  FOREIGN KEY (destinatario_id) REFERENCES `user`(id) ON DELETE SET NULL,
                  FOREIGN KEY (autor_id) REFERENCES `user`(id) ON DELETE SET NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """
            )
            cursor.execute("SHOW COLUMNS FROM respuestas_organizador LIKE 'destinatario_id'")
            if cursor.fetchone() is None:
                cursor.execute("ALTER TABLE respuestas_organizador ADD COLUMN destinatario_id INT UNSIGNED NULL AFTER organizador_id")
                cursor.execute("ALTER TABLE respuestas_organizador ADD KEY idx_destinatario (destinatario_id)")
                cursor.execute("ALTER TABLE respuestas_organizador ADD CONSTRAINT fk_respuestas_destinatario FOREIGN KEY (destinatario_id) REFERENCES `user`(id) ON DELETE SET NULL")
            cursor.execute("SHOW COLUMNS FROM respuestas_organizador LIKE 'autor_id'")
            if cursor.fetchone() is None:
                cursor.execute("ALTER TABLE respuestas_organizador ADD COLUMN autor_id INT UNSIGNED NULL AFTER destinatario_id")
                cursor.execute("ALTER TABLE respuestas_organizador ADD KEY idx_autor (autor_id)")
                cursor.execute("ALTER TABLE respuestas_organizador ADD CONSTRAINT fk_respuestas_autor FOREIGN KEY (autor_id) REFERENCES `user`(id) ON DELETE SET NULL")
            cursor.execute("SHOW COLUMNS FROM respuestas_organizador LIKE 'leido_destinatario'")
            if cursor.fetchone() is None:
                cursor.execute("ALTER TABLE respuestas_organizador ADD COLUMN leido_destinatario TINYINT(1) NOT NULL DEFAULT 0")
            cursor.execute(
                """
                UPDATE respuestas_organizador r
                INNER JOIN mensajes_organizador m ON m.id = r.mensaje_id
                SET r.destinatario_id = m.remitente_id
                WHERE r.destinatario_id IS NULL
                """
            )
            cursor.execute(
                "UPDATE respuestas_organizador SET autor_id = organizador_id WHERE autor_id IS NULL"
            )
            db.connection.commit()
            print("[INFO] Tabla respuestas_organizador creada/verificada.")
    except Exception as ex:
        print(f"[WARN] No se pudo asegurar la tabla de respuestas: {ex}")

def ensure_chat_deletions_table():
    try:
        with app.app_context():
            cursor = db.connection.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS chats_eliminados (
                  id INT UNSIGNED NOT NULL AUTO_INCREMENT,
                  usuario_id INT UNSIGNED NOT NULL,
                  contacto_id INT UNSIGNED NOT NULL,
                  eliminado_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  PRIMARY KEY (id),
                  UNIQUE KEY unique_chat_usuario (usuario_id, contacto_id),
                  KEY idx_contacto (contacto_id),
                  FOREIGN KEY (usuario_id) REFERENCES `user`(id) ON DELETE CASCADE,
                  FOREIGN KEY (contacto_id) REFERENCES `user`(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """
            )
            db.connection.commit()
            print("[INFO] Tabla de eliminaciones de chats creada/verificada.")
    except Exception as ex:
        print(f"[WARN] No se pudo asegurar la tabla de eliminaciones de chats: {ex}")

def add_profile_photo_column():
    try:
        with app.app_context():
            cursor = db.connection.cursor()
            cursor.execute("SHOW COLUMNS FROM `user` LIKE 'foto_perfil'")
            if cursor.fetchone() is None:
                cursor.execute("ALTER TABLE `user` ADD COLUMN `foto_perfil` VARCHAR(255) NULL DEFAULT NULL")
                db.connection.commit()
                print("[INFO] Columna foto_perfil agregada a tabla user.")
    except Exception as ex:
        print(f"[WARN] No se pudo agregar columna foto_perfil: {ex}")

def ensure_event_reminders_table():
    """Crea la tabla para almacenar recordatorios programados de eventos"""
    try:
        with app.app_context():
            cursor = db.connection.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS recordatorios_eventos (
                  id INT UNSIGNED NOT NULL AUTO_INCREMENT,
                  usuario_id INT UNSIGNED NOT NULL,
                  evento_id INT UNSIGNED NOT NULL,
                  tipo VARCHAR(50) NOT NULL,
                  mensaje TEXT NOT NULL,
                  fecha_programada DATETIME NOT NULL,
                  enviado TINYINT(1) DEFAULT 0,
                  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  PRIMARY KEY (id),
                  KEY idx_usuario (usuario_id),
                  KEY idx_evento (evento_id),
                  KEY idx_fecha_programada (fecha_programada),
                  KEY idx_enviado (enviado),
                  FOREIGN KEY (usuario_id) REFERENCES `user`(id) ON DELETE CASCADE,
                  FOREIGN KEY (evento_id) REFERENCES event(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """
            )
            db.connection.commit()
            print("[INFO] Tabla recordatorios_eventos creada/verificada.")
    except Exception as ex:
        print(f"[WARN] No se pudo asegurar la tabla de recordatorios: {ex}")

ensure_organizer_requests_table()
ensure_notifications_table()
ensure_followers_table()
ensure_replies_table()
ensure_chat_deletions_table()
add_profile_photo_column()
ensure_event_reminders_table()
csrf = CSRFProtect(app)
login_manager_app = LoginManager(app)
login_manager_app.login_view = 'login'

@login_manager_app.user_loader
def load_user(id):
    try:
        if str(id) == '0' or str(id) == 'admin':
            # Crear usuario admin en memoria con rol 'admin' para que las plantillas lo detecten
            return User(0, 'admin', 'admin', None, '', '', 'admin')
        return ModelUser.get_by_id(db, id)
    except Exception:
        return None

# ============ FUNCIONES HELPER ============

def get_current_user_dni_username():
    """Obtiene DNI y username del usuario actual desde session o BD"""
    dni = getattr(current_user, 'dni', None)
    username = getattr(current_user, 'username', None)
    if not dni or not username:
        try:
            cursor = db.connection.cursor()
            cursor.execute("SELECT dni, username FROM `user` WHERE id = %s LIMIT 1", (current_user.id,))
            row = cursor.fetchone()
            if row:
                if not dni:
                    dni = row[0]
                if not username:
                    username = row[1]
        except Exception as ex:
            print(f"[ERROR] get_current_user_dni_username: {ex}")
    return dni, username

def get_organizer_request_status(user_id):
    try:
        cursor = db.connection.cursor()
        cursor.execute(
            "SELECT status FROM organizer_role_requests WHERE user_id = %s ORDER BY id DESC LIMIT 1",
            (user_id,)
        )
        row = cursor.fetchone()
        return row[0] if row else None
    except Exception as ex:
        print(f"[ERROR] get_organizer_request_status: {ex}")
        return None

def get_pending_organizer_requests():
    try:
        cursor = db.connection.cursor()
        cursor.execute(
            """
            SELECT r.id, r.user_id, u.username, u.email, u.dni, u.telefono, r.requested_at
            FROM organizer_role_requests r
            INNER JOIN `user` u ON u.id = r.user_id
            WHERE r.status = 'pendiente'
            ORDER BY r.requested_at ASC, r.id ASC
            """
        )
        rows = cursor.fetchall()
        return [
            {
                'id': row[0],
                'user_id': row[1],
                'username': row[2],
                'email': row[3],
                'dni': row[4],
                'telefono': row[5],
                'requested_at': row[6].strftime('%d/%m/%Y %H:%M') if hasattr(row[6], 'strftime') else str(row[6])
            }
            for row in rows
        ]
    except Exception as ex:
        print(f"[ERROR] get_pending_organizer_requests: {ex}")
        return []

def get_events_from_db():
    try:
        cursor = db.connection.cursor()
        cursor.execute("SELECT id, titulo, fecha, hora, descripcion, lugar, capacidad_maxima, finalizado, categoria, latitud, longitud, imagen FROM event WHERE finalizado = 0 AND fecha >= CURDATE() ORDER BY fecha, hora")
        rows = cursor.fetchall()
        events = []
        for r in rows:
            hora = r[3].strftime('%H:%M') if hasattr(r[3], 'strftime') else str(r[3] or '00:00')
            events.append({
                'id': r[0],
                'titulo': r[1],
                'fecha': r[2].strftime('%Y-%m-%d') if hasattr(r[2], 'strftime') else str(r[2]),
                'hora': hora,
                'descripcion': r[4],
                'lugar': r[5],
                'capacidad_maxima': int(r[6]) if r[6] is not None else 0,
                'finalizado': bool(r[7]),
                'categoria': r[8] or 'General',
                'latitud': float(r[9]) if r[9] is not None else None,
                'longitud': float(r[10]) if r[10] is not None else None,
                'imagen': r[11]
            })
        return events
    except Exception:
        return []

def distance_in_km(latitude_a, longitude_a, latitude_b, longitude_b):
    earth_radius_km = 6371
    latitude_a, longitude_a, latitude_b, longitude_b = map(
        math.radians, (latitude_a, longitude_a, latitude_b, longitude_b)
    )
    delta_latitude = latitude_b - latitude_a
    delta_longitude = longitude_b - longitude_a
    value = (
        math.sin(delta_latitude / 2) ** 2
        + math.cos(latitude_a) * math.cos(latitude_b) * math.sin(delta_longitude / 2) ** 2
    )
    return earth_radius_km * 2 * math.asin(math.sqrt(value))


def get_events_created_by_user(db_connection, user_id):
    try:
        cursor = db_connection.connection.cursor()
        cursor.execute(
            "SELECT id, titulo, fecha, hora, descripcion, lugar, capacidad_maxima, finalizado, categoria, imagen FROM event WHERE created_by = %s ORDER BY fecha DESC, hora DESC, id DESC",
            (user_id,)
        )
        rows = cursor.fetchall()
        events = []
        for r in rows:
            evento_id = r[0]
            cursor2 = db_connection.connection.cursor()
            cursor2.execute("SELECT COUNT(*) FROM registrados WHERE evento_id = %s", (evento_id,))
            inscritos_count = cursor2.fetchone()[0]
            hora = r[3].strftime('%H:%M') if hasattr(r[3], 'strftime') else str(r[3] or '00:00')
            events.append({
                'id': evento_id,
                'titulo': r[1],
                'fecha': r[2].strftime('%Y-%m-%d') if hasattr(r[2], 'strftime') else str(r[2]),
                'hora': hora,
                'descripcion': r[4],
                'lugar': r[5],
                'capacidad_maxima': int(r[6]) if r[6] is not None else 0,
                'finalizado': bool(r[7]),
                'categoria': r[8] or 'General',
                'imagen': r[9],
                'inscritos_count': inscritos_count
            })
        return events
    except Exception:
        return []

def get_event_from_db(event_id):
    try:
        cursor = db.connection.cursor()
        cursor.execute(
            """
            SELECT e.id, e.titulo, e.fecha, e.hora, e.descripcion, e.lugar, e.capacidad_maxima, e.finalizado, e.categoria, e.created_by, e.latitud, e.longitud, e.imagen,
                   (SELECT COUNT(*) FROM registrados r WHERE r.evento_id = e.id) AS inscritos_count
            FROM event e
            WHERE e.id = %s
            """,
            (event_id,)
        )
        r = cursor.fetchone()
        if not r:
            return None
        hora = r[3].strftime('%H:%M') if hasattr(r[3], 'strftime') else str(r[3] or '00:00')
        
        # Obtener información del organizador
        organizador = None
        created_by_id = r[9]
        if created_by_id:
            try:
                cursor.execute(
                    "SELECT id, username, email, telefono, foto_perfil FROM `user` WHERE id = %s LIMIT 1",
                    (created_by_id,)
                )
                org_row = cursor.fetchone()
                if org_row:
                    organizador = {
                        'id': org_row[0],
                        'nombre': org_row[1],
                        'email': org_row[2],
                        'telefono': org_row[3],
                        'foto_perfil': org_row[4]
                    }
            except Exception as ex:
                print(f"[WARN] No se pudo obtener info del organizador: {ex}")
        
        return {
            'id': r[0],
            'titulo': r[1],
            'fecha': r[2].strftime('%Y-%m-%d') if hasattr(r[2], 'strftime') else str(r[2]),
            'hora': hora,
            'descripcion': r[4],
            'lugar': r[5],
            'capacidad_maxima': int(r[6]) if r[6] is not None else 0,
            'finalizado': bool(r[7]),
            'categoria': r[8] or 'General',
            'created_by': r[9],
            'latitud': float(r[10]) if r[10] is not None else None,
            'longitud': float(r[11]) if r[11] is not None else None,
            'imagen': r[12],
            'inscritos_count': int(r[13]) if r[13] is not None else 0,
            'organizador': organizador
        }
    except Exception:
        return None

def is_user_registered(db, evento_id, dni):
    try:
        cursor = db.connection.cursor()
        cursor.execute(
            "SELECT 1 FROM registrados WHERE evento_id = %s AND dni_usuario = %s LIMIT 1",
            (evento_id, dni)
        )
        return cursor.fetchone() is not None
    except Exception:
        return False

def get_registered_users(db, evento_id):
    try:
        cursor = db.connection.cursor()
        cursor.execute(
            "SELECT id, dni_usuario, nombre_usuario, created_at, asistido FROM registrados WHERE evento_id = %s ORDER BY created_at",
            (evento_id,)
        )
        rows = cursor.fetchall()
        return [    
            {
                'id': r[0],
                'dni': r[1],
                'nombre': r[2],
                'created_at': r[3].strftime('%Y-%m-%d %H:%M') if hasattr(r[3], 'strftime') else str(r[3]),
                'asistido': bool(r[4])
            }
            for r in rows
        ]
    except Exception:
        return []

def get_user_registrations(db, dni_usuario):
    """Devuelve las inscripciones (registros) de un usuario junto con información del evento."""
    try:
        cursor = db.connection.cursor()
        cursor.execute(
            """
            SELECT r.id, r.evento_id, r.dni_usuario, r.nombre_usuario, r.qr_code, r.asistido, e.titulo, e.fecha, e.hora, e.descripcion, e.lugar, e.categoria, e.imagen
            FROM registrados r
            JOIN event e ON e.id = r.evento_id
            WHERE r.dni_usuario = %s
            ORDER BY e.fecha, e.hora
            """,
            (dni_usuario,)
        )
        rows = cursor.fetchall()
        regs = []
        for r in rows:
            qr_path = r[4]
            qr_filename = os.path.basename(str(qr_path or '').replace('\\', '/'))
            qr_exists = bool(qr_filename) and os.path.exists(os.path.join(app.static_folder, 'qr', qr_filename))
            if not qr_exists:
                qr_path = generate_qr_code(r[1], r[2], r[3], r[0])
                if qr_path:
                    cursor.execute(
                        "UPDATE registrados SET qr_code = %s WHERE id = %s",
                        (qr_path, r[0])
                    )
                    db.connection.commit()
            if hasattr(r[8], 'strftime'):
                hora = r[8].strftime('%H:%M')
            elif isinstance(r[8], timedelta):
                total_seconds = int(r[8].total_seconds())
                horas, resto = divmod(total_seconds, 3600)
                minutos = resto // 60
                hora = f'{horas:02d}:{minutos:02d}'
            else:
                hora = str(r[8] or '00:00')[:5].zfill(5)
            regs.append({
                'registro_id': r[0],
                'evento_id': r[1],
                'dni': r[2],
                'nombre': r[3],
                'qr_code': qr_path,
                'asistido': bool(r[5]),
                'titulo': r[6],
                'fecha': r[7].strftime('%Y-%m-%d') if hasattr(r[7], 'strftime') else str(r[7]),
                'hora': hora,
                'descripcion': r[9],
                'lugar': r[10],
                'categoria': r[11] or 'General',
                'imagen': r[12]
            })
        return regs
    except Exception as ex:
        print(f"[ERROR] get_user_registrations: {ex}")
        return []


def delete_finished_events_and_qr():
    """Guarda y elimina eventos finalizados, sus registros y sus QR asociados."""
    try:
        cursor = db.connection.cursor()
        cursor.execute(
            """
            SELECT id, titulo, fecha, hora, descripcion, lugar,
                   capacidad_maxima, finalizado, categoria, created_by, created_at
            FROM event
            WHERE finalizado = 1 OR fecha < CURDATE()
            ORDER BY id
            """
        )
        events = cursor.fetchall()

        if not events:
            return {'deleted_events': 0, 'deleted_registrations': 0, 'deleted_qr_files': 0}

        event_ids = [row[0] for row in events]

        for event_id in event_ids:
            archive_event_history(event_id)

        qr_paths_to_remove = []
        for event_id in event_ids:
            cursor2 = db.connection.cursor()
            cursor2.execute("SELECT qr_code FROM registrados WHERE evento_id = %s", (event_id,))
            for (qr_code,) in cursor2.fetchall():
                if qr_code:
                    qr_paths_to_remove.append(qr_code)

        seen_qr_paths = []
        for qr_path in qr_paths_to_remove:
            if qr_path in seen_qr_paths:
                continue
            seen_qr_paths.append(qr_path)
            try:
                normalized_path = qr_path.replace('/static/qr/', '').replace('static/qr/', '')
                filename = os.path.basename(normalized_path)
                if not filename:
                    continue
                full_path = os.path.join(app.static_folder, 'qr', filename)
                if os.path.exists(full_path):
                    os.remove(full_path)
            except Exception as ex:
                print(f"[WARN] No se pudo eliminar el QR {qr_path}: {ex}")

        placeholders = ', '.join(['%s'] * len(event_ids))
        cursor.execute(f"DELETE FROM registrados WHERE evento_id IN ({placeholders})", tuple(event_ids))
        deleted_registrations = cursor.rowcount
        cursor.execute(f"DELETE FROM event WHERE id IN ({placeholders})", tuple(event_ids))
        db.connection.commit()

        return {
            'deleted_events': len(event_ids),
            'deleted_registrations': deleted_registrations,
            'deleted_qr_files': len(seen_qr_paths)
        }
    except Exception as ex:
        db.connection.rollback()
        print(f"[ERROR] delete_finished_events_and_qr: {ex}")
        raise


def generate_qr_code(evento_id, dni_usuario, nombre_usuario, registro_id):
    """Genera un código QR para el registro de un usuario en un evento"""
    try:
        qr_folder = os.path.join(app.static_folder, 'qr')
        if not os.path.exists(qr_folder):
            os.makedirs(qr_folder)
        
        qr_data = f"Evento:{evento_id}|DNI:{dni_usuario}|Nombre:{nombre_usuario}|Registro:{registro_id}"
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        filename = f"qr_evento_{evento_id}_user_{dni_usuario}_{registro_id}.png"
        filepath = os.path.join(qr_folder, filename)
        img.save(filepath)
        
        return f"/static/qr/{filename}"
    except Exception as ex:
        print(f"Error generando QR: {ex}")
        return None


from flask_mail import Mail, Message

app.config.update({
    'MAIL_SERVER': 'smtp.gmail.com',
    'MAIL_PORT': 587,
    'MAIL_USE_TLS': True,
    'MAIL_USE_SSL': False,
    'MAIL_USERNAME': GMAIL_USER,
    'MAIL_PASSWORD': GMAIL_PASS,
    'MAIL_DEFAULT_SENDER': GMAIL_USER
})
mail = Mail(app)
print(f"[INFO] Mail configurado con usuario: {GMAIL_USER}")


@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    remembered_email = request.cookies.get('remembered_user', '')

    if request.method == 'POST':
        email = request.form.get('email') or request.form.get('usuario')
        password = request.form.get('password') or request.form.get('contraseña')
        remember_me = request.form.get('remember_me') == '1'

        if email == 'admin1' and password == 'admin1':
            admin_user = User(0, 'admin1', 'admin1', None, '', '', 'admin')
            login_user(admin_user)
            response = redirect(url_for('home'))
            if remember_me:
                response.set_cookie('remembered_user', email, max_age=60*60*24*30, httponly=True, samesite='Lax')
            else:
                response.delete_cookie('remembered_user')
            return response

        user = User(0, "", email, password)
        logged_user = ModelUser.login(db, user)

        if logged_user != None:
            if logged_user.password:
                login_user(logged_user)
                response = redirect(url_for('home'))
                if remember_me:
                    response.set_cookie('remembered_user', email, max_age=60*60*24*30, httponly=True, samesite='Lax')
                else:
                    response.delete_cookie('remembered_user')
                return response
            else:
                flash("La contraseña ingresada es incorrecta.")
                return render_template('auth/login.html', remembered_email=remembered_email)
        else:
            flash("El correo ingresado no existe.")
            return render_template('auth/login.html', remembered_email=remembered_email)
    else:
        return render_template('auth/login.html', remembered_email=remembered_email)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        telefono = request.form['telefono'].strip()
        email = request.form['email'].strip()
        dni = request.form.get('dni', '').strip()
        rol = request.form.get('rol', 'estudiante').strip().lower()

        if rol not in ('estudiante', 'organizador'):
            flash("Selecciona si deseas registrarte como usuario u organizador.")
            return render_template('auth/register.html')

        if rol == 'estudiante' and (not dni.isdigit() or len(dni) > 8):
            flash("El DNI debe contener solo números y como máximo 8 dígitos.")
            return render_template('auth/register.html')
        if rol == 'organizador':
            dni = f"ORG-{uuid.uuid4().hex[:12].upper()}"
        if len(telefono) > 10 or not re.fullmatch(r'[0-9+\-() ]+', telefono):
            flash("El Teléfono sólo puede contener números y los signos + - ( ) y espacios, con un máximo de 10 caracteres.")
            return render_template('auth/register.html')

        email = email.lower()
        hashed_password = generate_password_hash(password)

        try:
            cursor = db.connection.cursor()
            cursor.execute(
                "SELECT id FROM `user` WHERE LOWER(email) = LOWER(%s) OR dni = %s OR username = %s",
                (email, dni, username)
            )
            user_exists = cursor.fetchone()

            if user_exists:
                flash("Ya existe una cuenta con ese nombre de usuario, DNI o correo electrónico.")
                return render_template('auth/register.html')

            cursor.execute(
                "INSERT INTO `user` (username, password, telefono, email, dni, rol) VALUES (%s, %s, %s, %s, %s, %s)",
                (username, hashed_password, telefono, email, dni, 'estudiante')
            )
            user_id = cursor.lastrowid
            if rol == 'organizador':
                cursor.execute(
                    "INSERT INTO organizer_role_requests (user_id, status) VALUES (%s, 'pendiente')",
                    (user_id,)
                )
            db.connection.commit()

            if rol == 'organizador':
                flash("¡Registro exitoso! Tu solicitud para ser organizador quedó pendiente de aprobación.", "success")
            else:
                flash("¡Registro exitoso! Ya puedes iniciar sesión.", "success")
            return redirect(url_for('login'))

        except Exception:
            flash("Ocurrió un error durante el registro.")
            return render_template('auth/register.html')
            
    return render_template('auth/register.html')

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        identifier = request.form.get('identifier', request.form.get('dni', '')).strip()
        if not identifier:
            flash('Ingrese su correo, usuario o nombre de institución.')
            return render_template('auth/forgot.html')

        try:
            cursor = db.connection.cursor()
            cursor.execute(
                """
                SELECT id, email
                FROM `user`
                WHERE dni = %s OR username = %s OR LOWER(email) = LOWER(%s)
                LIMIT 1
                """,
                (identifier, identifier, identifier)
            )
            user = cursor.fetchone()
            if not user:
                flash('No se encontró una cuenta asociada a esos datos.')
                return render_template('auth/forgot.html')

            user_id, user_email = user[0], user[1]
            code = f"{random.randint(100000, 999999)}"
            expires = (datetime.utcnow() + timedelta(minutes=15)).isoformat()
            session[f'pw_reset_{user_id}'] = {'code': code, 'expires': expires}
            session['reset_request_user_id'] = user_id
            session['reset_request_identifier'] = identifier
            session['reset_request_email'] = user_email

            if user_email:
                try:
                    msg = MIMEMultipart()
                    msg['From'] = GMAIL_USER
                    msg['To'] = user_email
                    msg['Subject'] = 'Código de recuperación'
                    msg.attach(MIMEText(f'Tu código de recuperación es: {code} (válido 15 minutos).', 'plain'))

                    server = smtplib.SMTP('smtp.gmail.com', 587)
                    server.starttls()
                    server.login(GMAIL_USER, GMAIL_PASS)
                    server.send_message(msg)
                    server.quit()

                    flash('Se envió un nuevo código al correo asociado.')
                except Exception as ex:
                    print(f'Error SMTP al enviar correo: {ex}')
                    flash('No se pudo enviar el correo. Revisa la configuración SMTP y vuelve a intentarlo.')
            else:
                flash('No se encontró un correo electrónico válido asociado a ese DNI.')

            return redirect(url_for('reset_password'))
        except Exception:
            flash('Ocurrió un error procesando la solicitud.')
            return render_template('auth/forgot.html')

    return render_template('auth/forgot.html')

@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        user_id = session.get('reset_request_user_id')
        identifier = session.get('reset_request_identifier')
        if not user_id or not identifier:
            flash('Primero solicita un código en la página de recuperación.')
            return redirect(url_for('forgot_password'))

        if not code:
            flash('Ingrese el código enviado a su correo.')
            return render_template('auth/reset_password.html')

        reset_data = session.get(f'pw_reset_{user_id}')
        if not reset_data:
            flash('No hay solicitud de recuperación activa para esta cuenta.')
            return redirect(url_for('forgot_password'))

        expires = datetime.fromisoformat(reset_data['expires'])
        if datetime.utcnow() > expires:
            session.pop(f'pw_reset_{user_id}', None)
            session.pop('reset_request_user_id', None)
            session.pop('reset_request_identifier', None)
            flash('El código expiró. Solicita uno nuevo.')
            return redirect(url_for('forgot_password'))

        if reset_data['code'] != code:
            flash('Código incorrecto.')
            return render_template('auth/reset_password.html')

        session['reset_user_id'] = user_id
        return redirect(url_for('new_password'))

    return render_template('auth/reset_password.html')

@app.route('/new-password', methods=['GET', 'POST'])
def new_password():
    user_id = session.get('reset_user_id')
    if not user_id:
        flash('No tienes permiso para cambiar la contraseña.')
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        if not password or not confirm_password:
            flash('Completa ambos campos de contraseña.')
            return render_template('auth/new_password.html', reset_identifier=session.get('reset_identifier', ''))

        if password != confirm_password:
            flash('Las contraseñas no coinciden.')
            return render_template('auth/new_password.html', reset_identifier=session.get('reset_identifier', ''))

        hashed_password = generate_password_hash(password)
        try:
            cursor = db.connection.cursor()
            cursor.execute("UPDATE `user` SET password = %s WHERE id = %s", (hashed_password, user_id))
            db.connection.commit()
            session.pop('reset_user_id', None)
            flash('Contraseña cambiada correctamente. Ya puedes iniciar sesión.', 'success')
            return redirect(url_for('login'))
        except Exception:
            flash('Ocurrió un error al guardar la nueva contraseña.')
            return render_template('auth/new_password.html', reset_identifier=session.get('reset_identifier', ''))

    return render_template('auth/new_password.html', reset_identifier=session.get('reset_identifier', ''))

# ============ RUTAS PROTEGIDAS - ADMIN ============

@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin_dashboard():
    if (not current_user.is_authenticated) or (getattr(current_user, 'rol', '') not in ('admin', 'organizador')):
        return redirect(url_for('login'))

    if request.method == 'POST':
        titulo = request.form.get('titulo', '').strip()
        fecha = request.form.get('fecha', '').strip()
        hora = request.form.get('hora', '').strip()
        descripcion = request.form.get('descripcion', '').strip()
        lugar = request.form.get('lugar', '').strip()
        latitud = request.form.get('latitud', '').strip()
        longitud = request.form.get('longitud', '').strip()
        capacidad_maxima = request.form.get('capacidad_maxima', '').strip()
        categoria = request.form.get('categoria', 'General').strip()
        try:
            imagen = save_event_image(request.files.get('imagen'))
        except ValueError as ex:
            flash(str(ex), 'error')
            return render_template('admin.html')

        try:
            capacidad = int(capacidad_maxima)
            if not titulo or not fecha or not hora or not descripcion or not lugar or capacidad <= 0:
                raise ValueError
            latitud = float(latitud) if latitud else None
            longitud = float(longitud) if longitud else None
            if latitud is not None and not -90 <= latitud <= 90:
                raise ValueError
            if longitud is not None and not -180 <= longitud <= 180:
                raise ValueError
        except ValueError:
            flash('Completá fecha, horario, título, lugar, descripción y una capacidad máxima válida.', 'error')
            return render_template('admin.html')

        try:
            cursor = db.connection.cursor()
            user_id = getattr(current_user, 'id', None)
            if user_id in (None, 0):
                cursor.execute(
                    "INSERT INTO event (titulo, fecha, hora, descripcion, lugar, capacidad_maxima, categoria, latitud, longitud, imagen) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (titulo, fecha, hora, descripcion, lugar, capacidad, categoria, latitud, longitud, imagen)
                )
            else:
                try:
                    cursor.execute(
                        "INSERT INTO event (titulo, fecha, hora, descripcion, lugar, capacidad_maxima, categoria, latitud, longitud, imagen, created_by) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                        (titulo, fecha, hora, descripcion, lugar, capacidad, categoria, latitud, longitud, imagen, user_id)
                    )
                except Exception:
                    cursor.execute(
                        "INSERT INTO event (titulo, fecha, hora, descripcion, lugar, capacidad_maxima, categoria, latitud, longitud, imagen) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                        (titulo, fecha, hora, descripcion, lugar, capacidad, categoria, latitud, longitud, imagen)
                    )
            db.connection.commit()
        except Exception as ex:
            flash(f'No se pudo crear el evento: {ex}', 'error')
            return render_template('admin.html')

        return redirect(url_for('ver_eventos'))

    return render_template('admin.html')


@app.route('/crear-evento-organizador', methods=['GET', 'POST'])
@login_required
def crear_evento_organizador():
    if (not current_user.is_authenticated) or (getattr(current_user, 'rol', '') not in ('admin', 'organizador')):
        return redirect(url_for('login'))

    if request.method == 'POST':
        titulo = request.form.get('titulo', '').strip()
        fecha = request.form.get('fecha', '').strip()
        hora = request.form.get('hora', '').strip()
        descripcion = request.form.get('descripcion', '').strip()
        lugar = request.form.get('lugar', '').strip()
        latitud = request.form.get('latitud', '').strip()
        longitud = request.form.get('longitud', '').strip()
        capacidad_maxima = request.form.get('capacidad_maxima', '').strip()
        categoria = request.form.get('categoria', 'General').strip()
        try:
            imagen = save_event_image(request.files.get('imagen'))
        except ValueError as ex:
            flash(str(ex), 'error')
            return render_template('crear_evento_organizador.html')

        try:
            capacidad = int(capacidad_maxima)
            if not titulo or not fecha or not hora or not descripcion or not lugar or capacidad <= 0:
                raise ValueError
            latitud = float(latitud) if latitud else None
            longitud = float(longitud) if longitud else None
            if latitud is not None and not -90 <= latitud <= 90:
                raise ValueError
            if longitud is not None and not -180 <= longitud <= 180:
                raise ValueError
        except ValueError:
            flash('Completá fecha, horario, lugar, descripción y una capacidad máxima válida.', 'error')
            return render_template('crear_evento_organizador.html')

        try:
            cursor = db.connection.cursor()
            user_id = getattr(current_user, 'id', None)
            if user_id in (None, 0):
                cursor.execute(
                    "INSERT INTO event (titulo, fecha, hora, descripcion, lugar, capacidad_maxima, categoria, latitud, longitud, imagen) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (titulo, fecha, hora, descripcion, lugar, capacidad, categoria, latitud, longitud, imagen)
                )
            else:
                try:
                    cursor.execute(
                        "INSERT INTO event (titulo, fecha, hora, descripcion, lugar, capacidad_maxima, categoria, latitud, longitud, imagen, created_by) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                        (titulo, fecha, hora, descripcion, lugar, capacidad, categoria, latitud, longitud, imagen, user_id)
                    )
                except Exception:
                    cursor.execute(
                        "INSERT INTO event (titulo, fecha, hora, descripcion, lugar, capacidad_maxima, categoria, latitud, longitud, imagen) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                        (titulo, fecha, hora, descripcion, lugar, capacidad, categoria, latitud, longitud, imagen)
                    )
            db.connection.commit()
            flash('Evento creado correctamente.', 'success')
            return redirect(url_for('eventos_organizador'))
        except Exception as ex:
            flash(f'No se pudo crear el evento: {ex}', 'error')
            return render_template('crear_evento_organizador.html')

    return render_template('crear_evento_organizador.html')

@app.route('/gestionar-organizadores', methods=['GET', 'POST'])
@login_required
def gestionar_organizadores():
    if not current_user.is_authenticated or getattr(current_user, 'rol', '') != 'admin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        request_id = request.form.get('request_id')
        action = request.form.get('action')
        user_id = request.form.get('user_id')
        nuevo_rol = request.form.get('rol')

        try:
            cursor = db.connection.cursor()
            if request_id and action in ('aprobar', 'rechazar'):
                cursor.execute(
                    "SELECT user_id FROM organizer_role_requests WHERE id = %s AND status = 'pendiente' FOR UPDATE",
                    (request_id,)
                )
                request_row = cursor.fetchone()
                if not request_row:
                    db.connection.rollback()
                    flash('La solicitud ya fue procesada o no existe.', 'error')
                else:
                    requested_user_id = request_row[0]
                    new_status = 'aprobada' if action == 'aprobar' else 'rechazada'
                    new_role = 'organizador' if action == 'aprobar' else 'estudiante'
                    cursor.execute("UPDATE `user` SET rol = %s WHERE id = %s", (new_role, requested_user_id))
                    cursor.execute(
                        "UPDATE organizer_role_requests SET status = %s, reviewed_at = NOW(), reviewed_by = %s WHERE id = %s",
                        (new_status, current_user.id, request_id)
                    )
                    db.connection.commit()
                    flash(
                        'Solicitud aprobada. El usuario ya tiene privilegios de organizador.' if action == 'aprobar'
                        else 'Solicitud rechazada. El usuario conservará los privilegios de usuario.',
                        'success'
                    )
            elif user_id and action == 'eliminar':
                target_user_id = int(user_id)
                if target_user_id == current_user.id:
                    raise ValueError('No puedes eliminar tu propia cuenta de administrador.')

                cursor.execute("SELECT rol FROM `user` WHERE id = %s FOR UPDATE", (target_user_id,))
                target_user = cursor.fetchone()
                if not target_user:
                    raise ValueError('El usuario no existe.')
                if target_user[0] == 'admin':
                    raise ValueError('No se puede eliminar una cuenta de administrador.')

                cursor.execute(
                    """
                    DELETE FROM respuestas_organizador
                    WHERE organizador_id = %s OR destinatario_id = %s OR autor_id = %s
                       OR mensaje_id IN (
                           SELECT id FROM mensajes_organizador
                           WHERE organizador_id = %s OR remitente_id = %s
                       )
                    """,
                    (target_user_id, target_user_id, target_user_id, target_user_id, target_user_id)
                )
                cursor.execute("DELETE FROM mensajes_organizador WHERE organizador_id = %s OR remitente_id = %s", (target_user_id, target_user_id))
                cursor.execute("DELETE FROM seguidores WHERE seguidor_id = %s OR seguido_id = %s", (target_user_id, target_user_id))
                cursor.execute("DELETE FROM chats_eliminados WHERE usuario_id = %s OR contacto_id = %s", (target_user_id, target_user_id))
                cursor.execute("DELETE FROM organizer_role_requests WHERE user_id = %s OR reviewed_by = %s", (target_user_id, target_user_id))
                cursor.execute("DELETE FROM registrados WHERE evento_id IN (SELECT id FROM event WHERE created_by = %s)", (target_user_id,))
                cursor.execute("DELETE FROM event WHERE created_by = %s", (target_user_id,))
                cursor.execute("DELETE FROM `user` WHERE id = %s", (target_user_id,))
                db.connection.commit()
                flash('Cuenta eliminada correctamente.', 'success')
            elif user_id and nuevo_rol in ('organizador', 'estudiante'):
                ModelUser.update_rol(db, user_id, nuevo_rol)
                flash('Rol actualizado correctamente.', 'success')
            else:
                flash('No se recibió una acción válida.', 'error')
        except Exception as ex:
            db.connection.rollback()
            flash(f'No se pudo procesar la solicitud: {ex}', 'error')

        return redirect(url_for('gestionar_organizadores'))

    dni_busqueda = request.args.get('dni', '').strip()
    usuarios = ModelUser.get_all_users(db, dni_busqueda)
    solicitudes = get_pending_organizer_requests()
    return render_template('admin_organizadores.html', usuarios=usuarios, solicitudes=solicitudes, dni_busqueda=dni_busqueda)

@app.route('/admin/borrar-historial', methods=['POST'])
@login_required
def borrar_historial_admin():
    if not current_user.is_authenticated or getattr(current_user, 'rol', '') != 'admin':
        return redirect(url_for('login'))

    try:
        result = delete_finished_events_and_qr()
        flash(
            f"Historial limpiado. Se eliminaron {result['deleted_events']} eventos, {result['deleted_registrations']} inscripciones y {result['deleted_qr_files']} QR.",
            'success'
        )
    except Exception as ex:
        flash(f'No se pudo borrar el historial: {ex}', 'error')

    return redirect(url_for('admin_dashboard'))

@app.route('/evento/<int:evento_id>/usuarios')
@login_required
def ver_usuarios_evento(evento_id):
    if not current_user.is_authenticated or getattr(current_user, 'rol', '') not in ('admin', 'organizador'):
        return redirect(url_for('login'))

    evento = get_event_from_db(evento_id)
    if evento is None:
        return "Evento no encontrado", 404

    if evento.get('finalizado'):
        flash('Este evento ya finalizó, por lo que no se pueden hacer cambios sobre sus inscripciones.', 'warning')
        if getattr(current_user, 'rol', '') == 'admin':
            return redirect(url_for('ver_eventos'))
        return redirect(url_for('eventos_organizador'))

    usuarios = get_registered_users(db, evento_id)
    return render_template('usuarios_registrados.html', evento=evento, usuarios=usuarios)

@app.route('/evento/<int:evento_id>/usuarios/eliminar/<int:registro_id>', methods=['POST'])
@login_required
def eliminar_usuario_registrado(evento_id, registro_id):
    if not current_user.is_authenticated or getattr(current_user, 'rol', '') not in ('admin', 'organizador'):
        return redirect(url_for('login'))

    evento = get_event_from_db(evento_id)
    if evento is None:
        return "Evento no encontrado", 404
    if evento.get('finalizado'):
        flash('Este evento ya finalizó y no se pueden eliminar usuarios.', 'error')
        return redirect(url_for('ver_usuarios_evento', evento_id=evento_id))

    try:
        cursor = db.connection.cursor()
        cursor.execute("DELETE FROM registrados WHERE id = %s AND evento_id = %s", (registro_id, evento_id))
        db.connection.commit()
        flash("Usuario eliminado del evento.", "success")
    except Exception:
        flash("Ocurrió un error al eliminar al usuario.", "error")

    return redirect(url_for('ver_usuarios_evento', evento_id=evento_id))

@app.route('/evento/<int:evento_id>/editar-ubicacion', methods=['GET', 'POST'])
@login_required
def editar_ubicacion_evento(evento_id):
    if not current_user.is_authenticated:
        return redirect(url_for('login'))

    evento = get_event_from_db(evento_id)
    if evento is None:
        return "Evento no encontrado", 404

    es_admin = getattr(current_user, 'rol', '') == 'admin' or getattr(current_user, 'email', '') == 'admin'
    es_organizador = getattr(current_user, 'rol', '') == 'organizador'
    es_propietario = getattr(evento, 'get', lambda *args, **kwargs: None)('created_by') in (None, getattr(current_user, 'id', None))

    if not es_admin and not (es_organizador and es_propietario):
        flash('No tenés permiso para cambiar la ubicación de este evento.', 'error')
        return redirect(url_for('detalle_evento', evento_id=evento_id))

    if evento.get('finalizado'):
        flash('Este evento ya finalizó y no se puede modificar.', 'error')
        return redirect(url_for('detalle_evento', evento_id=evento_id))

    if request.method == 'POST':
        nuevo_lugar = request.form.get('lugar', '').strip()
        if not nuevo_lugar:
            flash('La nueva ubicación es obligatoria.', 'error')
            return render_template('editar_ubicacion.html', evento=evento)

        try:
            cursor = db.connection.cursor()
            cursor.execute("UPDATE event SET lugar = %s WHERE id = %s", (nuevo_lugar, evento_id))
            db.connection.commit()
            flash('La ubicación del evento se actualizó correctamente.', 'success')
            return redirect(url_for('detalle_evento', evento_id=evento_id))
        except Exception as ex:
            flash(f'No se pudo actualizar la ubicación: {ex}', 'error')
            return render_template('editar_ubicacion.html', evento=evento)

    return render_template('editar_ubicacion.html', evento=evento)

@app.route('/evento/editar/<int:evento_id>', methods=['GET', 'POST'])
@login_required
def editar_evento(evento_id):
    if not current_user.is_authenticated:
        return redirect(url_for('login'))

    evento = get_event_from_db(evento_id)
    if evento is None:
        return "Evento no encontrado", 404

    es_admin = getattr(current_user, 'rol', '') == 'admin' or getattr(current_user, 'email', '') == 'admin'
    es_propietario = getattr(evento, 'get', lambda *args, **kwargs: None)('created_by') in (None, getattr(current_user, 'id', None))

    if not es_admin and not es_propietario:
        flash("No tenés permiso para editar este evento.", "error")
        return redirect(url_for('eventos_organizador'))

    if evento.get('finalizado'):
        flash('Este evento ya finalizó y no se puede editar.', 'error')
        return redirect(url_for('ver_eventos'))

    if request.method == 'POST':
        titulo = request.form.get('titulo', '').strip()
        fecha = request.form.get('fecha', '').strip()
        hora = request.form.get('hora', '').strip()
        descripcion = request.form.get('descripcion', '').strip()
        lugar = request.form.get('lugar', '').strip()
        latitud = request.form.get('latitud', '').strip()
        longitud = request.form.get('longitud', '').strip()
        capacidad_maxima = request.form.get('capacidad_maxima', '').strip()
        categoria = request.form.get('categoria', 'General').strip()

        try:
            capacidad = int(capacidad_maxima)
            if not titulo or not fecha or not hora or not descripcion or not lugar or capacidad <= 0:
                raise ValueError
            latitud = float(latitud) if latitud else None
            longitud = float(longitud) if longitud else None
            if latitud is not None and not -90 <= latitud <= 90:
                raise ValueError
            if longitud is not None and not -180 <= longitud <= 180:
                raise ValueError
        except ValueError:
            flash('La fecha, horario, descripción, lugar y capacidad máxima son obligatorios.', 'error')
            return render_template('editar_evento.html', evento=evento)

        try:
            imagen = save_event_image(request.files.get('imagen')) or evento.get('imagen')
        except ValueError as ex:
            flash(str(ex), 'error')
            return render_template('editar_evento.html', evento=evento)

        try:
            fecha_anterior = str(evento.get('fecha', '')).strip()
            hora_anterior = str(evento.get('hora', '')).strip()
            cursor = db.connection.cursor()
            cursor.execute(
                "UPDATE event SET titulo = %s, fecha = %s, hora = %s, descripcion = %s, lugar = %s, capacidad_maxima = %s, categoria = %s, latitud = %s, longitud = %s, imagen = %s WHERE id = %s",
                (titulo, fecha, hora, descripcion, lugar, capacidad, categoria, latitud, longitud, imagen, evento_id)
            )
            db.connection.commit()

            if fecha_anterior and hora_anterior and (fecha_anterior != fecha or hora_anterior != hora):
                notify_event_change_to_registered_users(evento_id, titulo, fecha_anterior, hora_anterior, fecha, hora, current_user.id)

            flash("Evento actualizado exitosamente.", "success")
            return redirect(url_for('ver_eventos'))
        except Exception as ex:
            flash("Ocurrió un error al actualizar el evento.", "error")
            return render_template('editar_evento.html', evento=evento)

    return render_template('editar_evento.html', evento=evento)

@app.route('/evento/eliminar/<int:evento_id>', methods=['POST'])
@login_required
def eliminar_evento(evento_id):
    if not current_user.is_authenticated or getattr(current_user, 'rol', '') not in ('admin', 'organizador'):
        return redirect(url_for('login'))

    evento = get_event_from_db(evento_id)
    if evento is None:
        return "Evento no encontrado", 404

    if evento.get('finalizado'):
        flash('No se puede eliminar un evento finalizado.', 'error')
        if getattr(current_user, 'rol', '') == 'admin':
            return redirect(url_for('ver_eventos'))
        return redirect(url_for('eventos_organizador'))

    es_admin = getattr(current_user, 'rol', '') == 'admin' or getattr(current_user, 'email', '') == 'admin'
    es_propietario = getattr(evento, 'get', lambda *args, **kwargs: None)('created_by') in (None, getattr(current_user, 'id', None))

    if not es_admin and not es_propietario:
        flash("No tenés permiso para eliminar este evento.", "error")
        return redirect(url_for('eventos_organizador'))
    
    try:
        cursor = db.connection.cursor()
        cursor.execute("DELETE FROM registrados WHERE evento_id = %s", (evento_id,))
        cursor.execute("DELETE FROM event WHERE id = %s", (evento_id,))
        db.connection.commit()
        flash("Evento eliminado exitosamente.", "success")
    except Exception as ex:
        flash("Ocurrió un error al eliminar el evento.", "error")

    if es_admin:
        return redirect(url_for('ver_eventos'))
    return redirect(url_for('eventos_organizador'))

# ============ RUTAS PROTEGIDAS - USUARIOS ============

@app.route('/home')
@login_required
def home():
    ensure_system_event_reminders(current_user.id)
    usuario_display = getattr(current_user, 'username', None) or getattr(current_user, 'email', '')
    solicitud_estado = None
    solicitudes_pendientes = 0
    notificaciones_sin_leer = 0
    
    if getattr(current_user, 'rol', '') == 'estudiante' and getattr(current_user, 'id', 0) != 0:
        solicitud_estado = get_organizer_request_status(current_user.id)
        notificaciones_sin_leer = get_unread_responses_count(current_user.id)
    elif getattr(current_user, 'rol', '') == 'admin':
        solicitudes_pendientes = len(get_pending_organizer_requests())
        notificaciones_sin_leer = get_unread_notifications_count(current_user.id)
    elif getattr(current_user, 'rol', '') == 'organizador':
        notificaciones_sin_leer = get_unread_notifications_count(current_user.id)

    notificaciones_recientes = get_recent_user_notifications(current_user.id, 6)
    cambios_evento_sin_leer = get_unread_event_changes_count(current_user.id)

    return render_template(
        'menu.html',
        usuario=usuario_display,
        solicitud_estado=solicitud_estado,
        solicitudes_pendientes=solicitudes_pendientes,
        notificaciones_sin_leer=notificaciones_sin_leer,
        notificaciones_recientes=notificaciones_recientes,
        cambios_evento_sin_leer=cambios_evento_sin_leer
    )

@app.route('/eventos')
@login_required
def ver_eventos():
    eventos = get_events_from_db()
    busqueda = request.args.get('busqueda', '').strip()
    categoria_seleccionada = request.args.get('categoria', '').strip()
    orden_fecha = request.args.get('orden_fecha', 'recientes').strip()
    orden_ubicacion = request.args.get('orden_ubicacion', '').strip()
    user_latitude = request.args.get('latitud', '').strip()
    user_longitude = request.args.get('longitud', '').strip()
    try:
        radius_km = min(max(float(request.args.get('radio', '10')), 1), 100)
    except ValueError:
        radius_km = 10

    try:
        user_latitude = float(user_latitude) if user_latitude else None
        user_longitude = float(user_longitude) if user_longitude else None
    except ValueError:
        user_latitude = None
        user_longitude = None

    if busqueda:
        busqueda_normalizada = busqueda.casefold()
        eventos = [
            evento for evento in eventos
            if busqueda_normalizada in evento.get('titulo', '').casefold()
        ]

    if categoria_seleccionada:
        eventos = [
            evento for evento in eventos
            if evento.get('categoria', 'General') == categoria_seleccionada
        ]

    if orden_ubicacion == 'cercanos' and user_latitude is not None and user_longitude is not None:
        eventos_cercanos = []
        for evento in eventos:
            if evento['latitud'] is None or evento['longitud'] is None:
                continue
            distancia = distance_in_km(
                user_latitude, user_longitude, evento['latitud'], evento['longitud']
            )
            if distancia <= radius_km:
                evento['distancia_km'] = round(distancia, 1)
                eventos_cercanos.append(evento)
        eventos = eventos_cercanos

    if orden_ubicacion == 'cercanos' and user_latitude is not None and user_longitude is not None:
        eventos.sort(key=lambda evento: evento.get('distancia_km', float('inf')))
    else:
        eventos.sort(
            key=lambda evento: (evento.get('fecha', ''), evento.get('hora', '')),
            reverse=orden_fecha != 'antiguos'
        )

    categorias = sorted({
        evento.get('categoria', 'General')
        for evento in get_events_from_db()
        if evento.get('categoria')
    })

    usuario_display = getattr(current_user, 'username', None) or getattr(current_user, 'email', '')
    return render_template(
        'eventos.html',
        eventos=eventos,
        usuario=usuario_display,
        categorias=categorias,
        busqueda=busqueda,
        categoria_seleccionada=categoria_seleccionada,
        orden_fecha=orden_fecha,
        orden_ubicacion=orden_ubicacion,
        user_latitude=user_latitude,
        user_longitude=user_longitude,
        radius_km=radius_km
    )

@app.route('/evento/<int:evento_id>')
@login_required
def detalle_evento(evento_id):
    evento = get_event_from_db(evento_id)
    if evento is None:
        return "Evento no encontrado", 404
    origin = request.args.get('origin', None)
    user_dni, _ = get_current_user_dni_username()
    registrado = False
    if user_dni:
        registrado = is_user_registered(db, evento_id, user_dni)
    cupos_disponibles = max(evento.get('capacidad_maxima', 0) - evento.get('inscritos_count', 0), 0)
    back_url = url_for('mis_eventos') if origin == 'mis_eventos' else url_for('ver_eventos')
    
    # Verificar si el usuario sigue al organizador
    is_following = False
    if current_user.is_authenticated and evento.get('organizador'):
        is_following = is_user_following(current_user.id, evento.get('organizador', {}).get('id'))
    
    if evento.get('finalizado'):
        flash('Este evento ya finalizó y quedó cerrado para nuevas inscripciones o validaciones.', 'warning')
    return render_template(
        'detalle.html',
        evento=evento,
        registrado=registrado,
        origin=origin,
        back_url=back_url,
        cupos_disponibles=cupos_disponibles,
        is_following=is_following
    )

@app.route('/evento/registrar/<int:evento_id>', methods=['POST'])
@login_required
def registrar_evento(evento_id):
    if request.method == 'POST':
        dni, username = get_current_user_dni_username()
        if not dni:
            flash('No se encontró tu DNI. Por favor, actualiza tu perfil.', 'error')
            return redirect(url_for('detalle_evento', evento_id=evento_id))

        try:
            cursor = db.connection.cursor()
            cursor.execute("SELECT capacidad_maxima, finalizado, titulo, fecha, hora FROM event WHERE id = %s LIMIT 1", (evento_id,))
            evento = cursor.fetchone()
            if not evento:
                flash('Evento no encontrado.', 'error')
                return redirect(url_for('ver_eventos'))

            capacidad_maxima = int(evento[0]) if evento[0] is not None else 0
            finalizado = bool(evento[1])
            evento_titulo = evento[2]
            evento_fecha = evento[3]
            evento_hora = evento[4]
            
            if finalizado:
                flash('Este evento ya finalizó y no acepta más inscripciones.', 'error')
                return redirect(url_for('detalle_evento', evento_id=evento_id))

            cursor.execute("SELECT COUNT(*) FROM registrados WHERE evento_id = %s", (evento_id,))
            inscritos_actuales = int(cursor.fetchone()[0])

            if capacidad_maxima <= 0:
                flash('Este evento no tiene una capacidad máxima válida.', 'error')
                return redirect(url_for('detalle_evento', evento_id=evento_id))

            if inscritos_actuales >= capacidad_maxima:
                flash('El evento ya alcanzó su capacidad máxima.', 'error')
                return redirect(url_for('detalle_evento', evento_id=evento_id))

            cursor.execute(
                "INSERT INTO registrados (evento_id, dni_usuario, nombre_usuario) VALUES (%s, %s, %s)",
                (evento_id, dni, username)
            )
            cursor.execute(
                """
                INSERT INTO mensajes_organizador
                    (organizador_id, remitente_id, evento_id, asunto, mensaje, leido)
                VALUES (%s, NULL, %s, %s, %s, 0)
                """,
                (
                    current_user.id,
                    evento_id,
                    'INSCRIPCION',
                    f'Te has anotado correctamente al evento {evento_titulo}.',
                )
            )
            db.connection.commit()

            registro_id = cursor.lastrowid
            print(f"[DEBUG] Registro insertado id={registro_id} evento={evento_id} dni={dni}")

            qr_path = generate_qr_code(evento_id, dni, username, registro_id)

            if qr_path:
                cursor.execute(
                    "UPDATE registrados SET qr_code = %s WHERE id = %s",
                    (qr_path, registro_id)
                )
                db.connection.commit()

            flash('Te has anotado correctamente al evento. Tu código QR ha sido generado.', 'success')
        except Exception as ex:
            db.connection.rollback()
            print(f"[ERROR] Error registrando usuario en evento {evento_id}: {ex}")
            if 'Duplicate entry' in str(ex):
                flash('Ya te has anotado en este evento.', 'error')
            else:
                flash('Ocurrió un error al anotarte. Intenta nuevamente.', 'error')

    return redirect(url_for('detalle_evento', evento_id=evento_id))

@app.route('/eventos-organizador')
@login_required
def eventos_organizador():
    """Muestra los eventos creados por el organizador autenticado."""
    if not current_user.is_authenticated or getattr(current_user, 'rol', '') not in ('admin', 'organizador'):
        return redirect(url_for('login'))

    user_id = getattr(current_user, 'id', None)
    eventos = []
    if user_id not in (None, 0):
        eventos = get_events_created_by_user(db, user_id)

    return render_template('eventos_organizador.html', eventos=eventos)

@app.route('/mis-eventos')
@login_required
def mis_eventos():
    """Lista los eventos en los que el usuario actual está anotado."""
    dni, username = get_current_user_dni_username()
    print(f"[DEBUG] mis_eventos - current_user.id={getattr(current_user,'id',None)} email={getattr(current_user,'email',None)} dni={dni}")
    if not dni:
        flash('No se encontró tu DNI. Actualiza tu perfil para ver tus inscripciones.', 'error')
        return redirect(url_for('ver_eventos'))

    registros = get_user_registrations(db, dni)
    print(f"[DEBUG] mis_eventos - registros_count={len(registros) if registros is not None else 0}")
    print(f"[DEBUG] mis_eventos - registros={registros}")
    return render_template('mis_eventos.html', registros=registros)


@app.route('/evento/<int:evento_id>/finalizar', methods=['POST'])
@login_required
def finalizar_evento(evento_id):
    if not current_user.is_authenticated or getattr(current_user, 'rol', '') not in ('admin', 'organizador'):
        return redirect(url_for('login'))

    evento = get_event_from_db(evento_id)
    if evento is None:
        return "Evento no encontrado", 404

    es_admin = getattr(current_user, 'rol', '') == 'admin' or getattr(current_user, 'email', '') == 'admin'
    es_propietario = getattr(evento, 'get', lambda *args, **kwargs: None)('created_by') in (None, getattr(current_user, 'id', None))
    if not es_admin and not es_propietario:
        flash('No tenés permiso para finalizar este evento.', 'error')
        return redirect(url_for('eventos_organizador'))

    if evento.get('finalizado'):
        flash('Este evento ya está finalizado.', 'warning')
        return redirect(url_for('ver_eventos'))

    try:
        cursor = db.connection.cursor()
        cursor.execute(
            "SELECT dni_usuario, nombre_usuario FROM registrados WHERE evento_id = %s AND asistido = 1 ORDER BY created_at",
            (evento_id,)
        )
        registrados = cursor.fetchall()

        if not registrados:
            flash('El evento fue finalizado, pero no hay usuarios validados para recibir certificados.', 'warning')
        else:
            for dni_usuario, nombre_usuario in registrados:
                try:
                    cursor2 = db.connection.cursor()
                    cursor2.execute("SELECT email FROM `user` WHERE dni = %s LIMIT 1", (dni_usuario,))
                    usuario = cursor2.fetchone()
                    email_destino = usuario[0] if usuario else None
                    if not email_destino:
                        continue

                    nombre_partes = (nombre_usuario or '').split()
                    nombre = nombre_partes[0] if nombre_partes else ''
                    apellido = ' '.join(nombre_partes[1:]) if len(nombre_partes) > 1 else ''
                    cert_path = generar_certificado(nombre, apellido, dni_usuario, evento['titulo'])

                    msg = Message(subject=f'Certificado de asistencia - {evento["titulo"]}', recipients=[email_destino])
                    msg.body = (
                        f"Hola {nombre_usuario},\n\n"
                        f"Adjuntamos tu certificado de asistencia al evento '{evento['titulo']}'.\n\n"
                        "Saludos,\nEquipo de Gestión de Eventos"
                    )
                    with open(cert_path, 'rb') as file:
                        msg.attach(os.path.basename(cert_path), 'image/png', file.read())
                    mail.send(msg)
                except Exception as ex:
                    print(f"[ERROR] finalizando evento {evento_id}, usuario {dni_usuario}: {ex}")

            flash('Evento finalizado correctamente. Los certificados fueron enviados solo a los usuarios validados.', 'success')

        cursor.execute("UPDATE event SET finalizado = 1 WHERE id = %s", (evento_id,))
        archive_event_history(evento_id)
        db.connection.commit()
    except Exception as ex:
        db.connection.rollback()
        flash(f'No se pudo finalizar el evento: {ex}', 'error')

    if es_admin:
        return redirect(url_for('ver_eventos'))
    return redirect(url_for('eventos_organizador'))


@app.route('/evento/<int:evento_id>/validar-qr')
@login_required
def validar_qr_evento(evento_id):
    """Muestra la vista para validar entrada de un evento mediante QR o DNI."""
    evento = get_event_from_db(evento_id)
    if evento is None:
        return "Evento no encontrado", 404
    if evento.get('finalizado'):
        flash('Este evento ya finalizó y no se puede validar más.', 'error')
        return redirect(url_for('eventos_organizador'))
    return render_template('validar_qr.html', evento=evento, evento_id=evento_id)


@app.route('/api/validar-qr-entrada', methods=['POST'])
@login_required
def validar_qr_entrada():
    """Valida si un usuario está registrado en un evento usando QR o DNI.
    Solo marca asistido y devuelve el email, sin generar certificado aún.
    """
    data = request.get_json(silent=True) or {}
    evento_id = data.get('evento_id')
    qr_data = data.get('qr_data')
    dni = data.get('dni')

    if not evento_id:
        return jsonify({'success': False, 'message': 'No se indicó el evento.'}), 400

    try:
        cursor = db.connection.cursor()
        confirmation_method = 'QR' if qr_data else 'DNI'
        if qr_data:
            import re
            match = re.search(r'\|DNI:(.+?)\|', str(qr_data))
            dni = match.group(1).strip() if match else None

        if not dni:
            return jsonify({'success': False, 'message': 'No se pudo leer el DNI del QR o no se ingresó el DNI.'}), 400

        cursor.execute("SELECT finalizado FROM event WHERE id = %s LIMIT 1", (evento_id,))
        evento_row = cursor.fetchone()
        if evento_row and bool(evento_row[0]):
            return jsonify({'success': False, 'message': 'Este evento ya finalizó y no acepta más validaciones.'}), 403

        cursor.execute(
            "SELECT 1 FROM registrados WHERE evento_id = %s AND dni_usuario = %s LIMIT 1",
            (evento_id, dni)
        )
        existe = cursor.fetchone() is not None

        if existe:
            cursor.execute(
                """
                UPDATE registrados
                SET asistido = 1,
                    confirmado_at = COALESCE(confirmado_at, NOW()),
                    metodo_confirmacion = COALESCE(metodo_confirmacion, %s)
                WHERE evento_id = %s AND dni_usuario = %s
                """,
                (confirmation_method, evento_id, dni)
            )
            db.connection.commit()

            # Obtener email actual del usuario
            try:
                cursor.execute("SELECT email FROM `user` WHERE dni = %s LIMIT 1", (dni,))
                user_row = cursor.fetchone()
                user_email = user_row[0] if user_row else None
            except Exception:
                user_email = None

            print(f"[INFO] Usuario {dni} marcado como asistido en evento {evento_id}. Email: {user_email}")
            
            return jsonify({
                'success': True,
                'message': f'✓ Usuario validado. Email: {user_email or "(no registrado)"}',
                'current_email': user_email,
                'evento_id': evento_id,
                'dni': dni
            })

        return jsonify({'success': False, 'message': 'No se encontró un registro para este usuario en el evento.'})
    except Exception as ex:
        print(f"[ERROR] validar_qr_entrada: {ex}")
        return jsonify({'success': False, 'message': 'Ocurrió un error al validar el QR.'}), 500


@app.route('/api/notificaciones', methods=['GET'])
@login_required
def obtener_notificaciones():
    """Obtiene las notificaciones de mensajes del usuario autenticado."""
    try:
        if getattr(current_user, 'rol', '') not in ('organizador', 'admin'):
            return jsonify({'success': False, 'message': 'No autorizado'}), 403
        
        cursor = db.connection.cursor()
        cursor.execute(
            """
            SELECT m.id, u.username, m.asunto, m.mensaje, m.created_at, m.leido, m.evento_id
            FROM mensajes_organizador m
            LEFT JOIN `user` u ON u.id = m.remitente_id
            WHERE m.organizador_id = %s
            ORDER BY m.created_at DESC
            LIMIT 20
            """,
            (current_user.id,)
        )
        rows = cursor.fetchall()
        
        notificaciones = []
        for row in rows:
            created_at = row[4].strftime('%d/%m/%Y %H:%M') if hasattr(row[4], 'strftime') else str(row[4])
            notificaciones.append({
                'id': row[0],
                'remitente': row[1] or 'Desconocido',
                'asunto': row[2],
                'mensaje': row[3],
                'fecha': created_at,
                'leido': bool(row[5]),
                'evento_id': row[6]
            })
        
        return jsonify({
            'success': True,
            'notificaciones': notificaciones,
            'total': len(notificaciones)
        })
    except Exception as ex:
        print(f"[ERROR] obtener_notificaciones: {ex}")
        return jsonify({'success': False, 'message': str(ex)}), 500


@app.route('/api/enviar-certificados-lote', methods=['POST'])
@login_required
def enviar_certificados_lote():
    """Envía certificados a múltiples usuarios de una vez."""
    data = request.get_json(silent=True) or {}
    evento_id = data.get('evento_id')
    usuarios = data.get('usuarios', [])  # Lista de {dni, email}

    if not evento_id or not usuarios:
        return jsonify({'success': False, 'message': 'Faltan datos requeridos.'}), 400

    results = []
    cursor = db.connection.cursor()

    try:
        # Obtener título del evento
        cursor.execute("SELECT titulo FROM event WHERE id = %s LIMIT 1", (evento_id,))
        evt_row = cursor.fetchone()
        evento_titulo = evt_row[0] if evt_row else f'Evento {evento_id}'
    except Exception:
        evento_titulo = f'Evento {evento_id}'

    for user_data in usuarios:
        dni = user_data.get('dni')
        email_destino = user_data.get('email')

        if not dni or not email_destino:
            results.append({'dni': dni, 'success': False, 'message': 'Datos incompletos'})
            continue

        try:
            cursor.execute(
                "SELECT nombre_usuario FROM registrados WHERE evento_id = %s AND dni_usuario = %s AND asistido = 1 LIMIT 1",
                (evento_id, dni)
            )
            nombre_row = cursor.fetchone()
            if not nombre_row:
                results.append({'dni': dni, 'success': False, 'message': 'Usuario no validado'})
                continue
            nombre_usuario = nombre_row[0] if nombre_row else ''

            # Separar nombre y apellido
            nombre_partes = nombre_usuario.split()
            nombre = nombre_partes[0] if len(nombre_partes) > 0 else ''
            apellido = ' '.join(nombre_partes[1:]) if len(nombre_partes) > 1 else ''

            # Generar certificado
            salida_cert = generar_certificado(nombre, apellido, dni, evento_titulo)

            # Enviar por email
            try:
                subj = f"Certificado de asistencia - {evento_titulo}"
                body = f"Hola {nombre_usuario},\n\nAdjuntamos tu certificado de asistencia al evento '{evento_titulo}'.\n\nSaludos,\nEquipo de Gestión de Eventos"
                msg = Message(subject=subj, recipients=[email_destino])
                msg.body = body
                with open(salida_cert, 'rb') as fp:
                    cert_data = fp.read()
                    msg.attach(os.path.basename(salida_cert), 'image/png', cert_data)
                
                print(f"[INFO] Enviando certificado a {email_destino} (DNI: {dni})")
                mail.send(msg)
                print(f"[INFO] Email enviado a {email_destino}")
                results.append({'dni': dni, 'success': True, 'message': f'Enviado a {email_destino}'})
            except Exception as mail_ex:
                print(f"[ERROR] No se pudo enviar email a {email_destino}: {mail_ex}")
                results.append({'dni': dni, 'success': False, 'message': f'Error: {str(mail_ex)[:50]}'})
        except Exception as ex:
            print(f"[ERROR] Error procesando DNI {dni}: {ex}")
            results.append({'dni': dni, 'success': False, 'message': str(ex)[:50]})

    success_count = sum(1 for r in results if r['success'])
    return jsonify({
        'success': True,
        'message': f'Certificados enviados: {success_count}/{len(usuarios)}',
        'results': results
    })


@app.route('/mis-eventos/cancelar/<int:registro_id>', methods=['POST'])
@login_required
def cancelar_asistencia(registro_id):
    dni, _ = get_current_user_dni_username()
    if not dni:
        flash('No se encontró tu DNI. Actualiza tu perfil.', 'error')
        return redirect(url_for('mis_eventos'))

    try:
        cursor = db.connection.cursor()
        cursor.execute(
            "SELECT e.finalizado, r.evento_id FROM registrados r JOIN event e ON e.id = r.evento_id WHERE r.id = %s AND r.dni_usuario = %s LIMIT 1",
            (registro_id, dni)
        )
        registro = cursor.fetchone()
        if not registro:
            flash('No se encontró tu registro para cancelar.', 'error')
            return redirect(url_for('mis_eventos'))

        finalizado, evento_id = bool(registro[0]), registro[1]
        if finalizado:
            flash('Este evento ya finalizó y no se puede cancelar la asistencia.', 'error')
            return redirect(url_for('mis_eventos'))

        cursor.execute(
            "DELETE FROM registrados WHERE id = %s AND dni_usuario = %s",
            (registro_id, dni)
        )
        deleted = cursor.rowcount
        db.connection.commit()

        if deleted:
            flash('Tu asistencia fue cancelada correctamente.', 'success')
        else:
            flash('No se encontró tu registro para cancelar.', 'error')
    except Exception as ex:
        db.connection.rollback()
        print(f"[ERROR] cancelar_asistencia: {ex}")
        flash('Ocurrió un error al cancelar la asistencia.', 'error')

    return redirect(url_for('mis_eventos'))


@app.route('/registro/<int:registro_id>/qr')
@login_required
def mostrar_qr(registro_id):
    """Muestra la imagen QR asociada al registro (si existe)."""
    try:
        origin = request.args.get('origin', None)
        print(f"[DEBUG] mostrar_qr - solicitado registro_id={registro_id} por user id={getattr(current_user,'id',None)} origin={origin}")
        cursor = db.connection.cursor()
        cursor.execute(
            "SELECT r.qr_code, r.dni_usuario, e.finalizado, r.evento_id FROM registrados r JOIN event e ON e.id = r.evento_id WHERE r.id = %s LIMIT 1",
            (registro_id,)
        )
        r = cursor.fetchone()
        if not r:
            print(f"[ERROR] mostrar_qr - registro {registro_id} no encontrado en DB")
            return "Registro no encontrado", 404
        qr_path, dni, evento_finalizado, evento_id = r[0], r[1], bool(r[2]), r[3]
        print(f"[DEBUG] mostrar_qr - qr_path={qr_path} registro_dni={dni} evento_finalizado={evento_finalizado}")

        current_dni, _ = get_current_user_dni_username()
        
        if getattr(current_user, 'email', '') != 'admin' and str(dni) != str(current_dni):
            print(f"[ERROR] mostrar_qr - intento acceso no autorizado registro {registro_id} por user dni={current_dni}")
            return redirect(url_for('login'))

        if evento_finalizado:
            flash('Este evento ya finalizó, por lo que no se puede consultar ni validar el QR.', 'warning')
            return redirect(url_for('mis_eventos'))

        if not qr_path:
            flash('No se encontró un código QR para este registro.', 'error')
            return redirect(url_for('mis_eventos'))

        back_url = url_for('mis_eventos') if origin == 'mis_eventos' else url_for('ver_eventos')
        return render_template('mostrar_qr.html', qr_path=qr_path, back_url=back_url)
    except Exception as ex:
        print(f"[ERROR] mostrar_qr - excepción: {ex}")
        return "Ocurrió un error", 500

@app.route('/debug-user')
@login_required
def debug_user():
    """Ruta temporal para depuración del usuario actual"""
    dni, username = get_current_user_dni_username()
    info = {
        'id': getattr(current_user, 'id', 'N/A'),
        'username': getattr(current_user, 'username', 'N/A'),
        'email': getattr(current_user, 'email', 'N/A'),
        'dni': dni,
        'telefono': getattr(current_user, 'telefono', 'N/A'),
    }
    
    registros_bd = []
    if dni:
        registros_bd = get_user_registrations(db, dni)
    
    return f"""
    <h2>Debug - Información del Usuario</h2>
    <pre>
    {info}
    </pre>
    <h2>Registros en BD (DNI={dni})</h2>
    <pre>
    {registros_bd}
    </pre>
    <hr />
    <a href="{url_for('debug_registros')}">Ver todos los registros</a> | 
    <a href="{url_for('mis_eventos')}">Volver a Mis Eventos</a>
    """

@app.route('/debug-registros')
@login_required
def debug_registros():
    """Muestra todos los registros en la tabla registrados"""
    try:
        cursor = db.connection.cursor()
        cursor.execute("SELECT id, evento_id, dni_usuario, nombre_usuario, qr_code, created_at FROM registrados ORDER BY created_at DESC LIMIT 20")
        rows = cursor.fetchall()
        
        html = "<h2>Últimos 20 Registros en BD</h2><table border='1' cellpadding='5'>"
        html += "<tr><th>ID</th><th>Evento</th><th>DNI</th><th>Nombre</th><th>QR</th><th>Fecha</th></tr>"
        for r in rows:
            html += f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td><td>{r[3]}</td><td>{r[4]}</td><td>{r[5]}</td></tr>"
        html += "</table><hr />"
        html += f"<a href='{url_for('debug_user')}'>Ver info del usuario</a>"
        return html
    except Exception as ex:
        return f"Error: {ex}"

@app.route('/evento/contactar-organizador', methods=['POST'])
@login_required
def enviar_contacto_organizador():
    """Envía un mensaje al organizador de un evento (guardado en BD, no email)"""
    evento_id = request.form.get('evento_id')
    organizador_id = request.form.get('organizador_id')
    asunto = request.form.get('asunto', '').strip()
    mensaje = request.form.get('mensaje', '').strip()
    
    if not evento_id or not organizador_id or not asunto or not mensaje:
        flash('Por favor completa todos los campos requeridos.', 'error')
        return redirect(url_for('detalle_evento', evento_id=evento_id))
    
    try:
        cursor = db.connection.cursor()
        remitente_id = getattr(current_user, 'id', None)
        
        # Guardar el mensaje en la BD
        cursor.execute(
            """
            INSERT INTO mensajes_organizador 
            (organizador_id, remitente_id, evento_id, asunto, mensaje, leido)
            VALUES (%s, %s, %s, %s, %s, 0)
            """,
            (organizador_id, remitente_id, evento_id, asunto, mensaje)
        )
        db.connection.commit()
        
        flash('✓ Tu mensaje ha sido enviado al organizador. Se notificará dentro de la plataforma.', 'success')
    except Exception as ex:
        print(f"[ERROR] enviar_contacto_organizador: {ex}")
        flash('Ocurrió un error al procesar tu solicitud.', 'error')
        db.connection.rollback()
    
    return redirect(url_for('detalle_evento', evento_id=evento_id))

@app.route('/logout')
@login_required
def logout():
    session.pop('_flashes', None)
    logout_user()
    return redirect(url_for('login'))

@app.route('/soporte')
def soporte():
    """Página de soporte y reporte de problemas"""
    return render_template('soporte.html')

@app.route('/enviar-ticket', methods=['POST'])
def enviar_ticket():
    nombre_usuario = request.form.get('nombre', '').strip()
    legajo_usuario = request.form.get('legajo', '').strip()
    email_usuario = request.form.get('email', '').strip()
    prioridad = request.form.get('prioridad')
    categoria = request.form.get('categoria')
    mensaje = request.form.get('descripcion', '').strip()

    if not re.fullmatch(r"[A-Za-zÁÉÍÓÚáéíóúÑñÜü' -]+", nombre_usuario):
        flash('El nombre solo puede contener letras, espacios, apóstrofes y guiones.', 'error')
        return redirect(url_for('soporte'))
    if not re.fullmatch(r'\d{1,8}', legajo_usuario):
        flash('El Legajo o DNI debe contener solo números y hasta 8 dígitos.', 'error')
        return redirect(url_for('soporte'))
    
    ticket_id = int(time.time())

    msg = MIMEMultipart()
    msg['From'] = GMAIL_USER
    msg['To'] = GMAIL_USER
    
    msg['Subject'] = f"TICKET #{ticket_id} [{categoria}] - De: {nombre_usuario}"

    cuerpo_correo = f"""
NUEVO TICKET DE SOPORTE: #{ticket_id}

Nombre: {nombre_usuario}
Legajo/DNI: {legajo_usuario}
Correo: {email_usuario}
Categoría: {categoria}
Prioridad: {prioridad}

Descripción del problema:
{mensaje}

__________________________________________
Sistema de Gestión de Eventos
UTN Facultad Regional San Francisco
"""

    msg.attach(MIMEText(cuerpo_correo, 'plain'))

    file = request.files.get('adjunto')
    if file and file.filename != '':
        try:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(file.read())
            encoders.encode_base64(part)
            part.add_header(
                'Content-Disposition',
                f'attachment; filename={file.filename}',
            )
            msg.attach(part)
        except Exception as file_error:
            print("Error al adjuntar archivo:", file_error)

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_PASS)
        server.send_message(msg)
        server.quit()

        return render_template('ticket_enviado.html', ticket_id=ticket_id)

    except Exception as e:
        print("Error:", e)
        return render_template('ticket_error.html', error=e), 500

# ============ RUTAS DE SEGUIMIENTO Y NOTIFICACIONES ============

def is_user_following(seguidor_id, seguido_id):
    """Verifica si un usuario sigue a otro"""
    try:
        cursor = db.connection.cursor()
        cursor.execute(
            "SELECT 1 FROM seguidores WHERE seguidor_id = %s AND seguido_id = %s LIMIT 1",
            (seguidor_id, seguido_id)
        )
        return cursor.fetchone() is not None
    except Exception:
        return False

@app.route('/usuario/<int:user_id>/seguir', methods=['POST'])
@login_required
def seguir_usuario(user_id):
    """Seguir a un usuario"""
    if user_id == getattr(current_user, 'id', None):
        flash('No puedes seguirte a ti mismo.', 'error')
        return redirect(request.referrer or url_for('home'))
    
    try:
        cursor = db.connection.cursor()
        cursor.execute(
            "INSERT IGNORE INTO seguidores (seguidor_id, seguido_id) VALUES (%s, %s)",
            (getattr(current_user, 'id', None), user_id)
        )
        db.connection.commit()
        flash('✓ Ahora sigues a este usuario.', 'success')
    except Exception as ex:
        print(f"[ERROR] seguir_usuario: {ex}")
        flash('Ocurrió un error.', 'error')
    
    return redirect(request.referrer or url_for('home'))

@app.route('/usuario/<int:user_id>/dejar-de-seguir', methods=['POST'])
@login_required
def dejar_de_seguir(user_id):
    """Dejar de seguir a un usuario"""
    try:
        cursor = db.connection.cursor()
        cursor.execute(
            "DELETE FROM seguidores WHERE seguidor_id = %s AND seguido_id = %s",
            (getattr(current_user, 'id', None), user_id)
        )
        db.connection.commit()
        flash('✓ Dejaste de seguir a este usuario.', 'success')
    except Exception as ex:
        print(f"[ERROR] dejar_de_seguir: {ex}")
        flash('Ocurrió un error.', 'error')
    
    return redirect(request.referrer or url_for('home'))

def get_message_replies(mensaje_id):
    """Obtiene todas las respuestas a un mensaje"""
    try:
        cursor = db.connection.cursor()
        cursor.execute(
            """
                 SELECT r.id, r.autor_id, r.respuesta, r.created_at,
                     u.username, u.foto_perfil, r.leido_destinatario
            FROM respuestas_organizador r
                 LEFT JOIN `user` u ON u.id = COALESCE(r.autor_id, r.organizador_id)
            WHERE r.mensaje_id = %s
            ORDER BY r.created_at ASC
            """,
            (mensaje_id,)
        )
        respuestas = cursor.fetchall()
        
        replies = []
        for resp in respuestas:
            replies.append({
                'id': resp[0],
                'autor_id': resp[1],
                'respuesta': resp[2],
                'created_at': resp[3].strftime('%d/%m/%Y %H:%M') if hasattr(resp[3], 'strftime') else str(resp[3]),
                'autor_nombre': resp[4] or 'Usuario',
                'autor_foto': resp[5],
                'leida': bool(resp[6])
            })
        return replies
    except Exception as ex:
        print(f"[WARN] Error obteniendo respuestas para mensaje {mensaje_id}: {ex}")
        return []

@app.route('/mis-notificaciones')
@login_required
def mis_notificaciones():
    """Muestra mensajes recibidos por organizadores o respuestas del organizador al remitente."""
    ensure_system_event_reminders(current_user.id)
    es_organizador = getattr(current_user, 'rol', '') in ('admin', 'organizador')
    chat_abierto_id = request.args.get('chat', type=int)

    try:
        cursor = db.connection.cursor()
        user_id = getattr(current_user, 'id', None)
        if es_organizador and chat_abierto_id:
            cursor.execute(
                """
                UPDATE mensajes_organizador
                SET leido = 1
                WHERE organizador_id = %s AND remitente_id = %s
                """,
                (user_id, chat_abierto_id)
            )
            cursor.execute(
                """
                UPDATE respuestas_organizador r
                INNER JOIN mensajes_organizador m ON m.id = r.mensaje_id
                SET r.leido_destinatario = 1
                WHERE m.organizador_id = %s AND m.remitente_id = %s
                  AND r.destinatario_id = %s
                """,
                (user_id, chat_abierto_id, user_id)
            )
            db.connection.commit()
        if es_organizador:
            cursor.execute(
                """
              SELECT m.id, m.remitente_id, m.evento_id, m.asunto, m.mensaje, m.created_at, m.leido,
                  CASE
                    WHEN m.remitente_id IS NULL THEN 'Sistema'
                    WHEN m.remitente_id = %s THEN destinatario.username
                    ELSE remitente.username
                  END AS remitente_nombre,
                  CASE
                    WHEN m.remitente_id IS NULL THEN NULL
                    WHEN m.remitente_id = %s THEN destinatario.foto_perfil
                    ELSE remitente.foto_perfil
                  END AS remitente_foto,
                  e.titulo AS evento_titulo
                FROM mensajes_organizador m
              LEFT JOIN `user` remitente ON remitente.id = m.remitente_id
              LEFT JOIN `user` destinatario ON destinatario.id = m.organizador_id
                LEFT JOIN event e ON e.id = m.evento_id
                            LEFT JOIN chats_eliminados ce
                                ON ce.usuario_id = %s
                             AND ce.contacto_id = CASE
                                        WHEN m.remitente_id = %s THEN m.organizador_id
                                        ELSE m.remitente_id
                                    END
                             AND m.created_at <= ce.eliminado_at
                            WHERE (m.organizador_id = %s OR m.remitente_id = %s)
                                AND (
                                    ce.id IS NULL
                                    OR EXISTS (
                                        SELECT 1
                                        FROM respuestas_organizador r
                                        WHERE r.mensaje_id = m.id
                                          AND r.created_at > ce.eliminado_at
                                    )
                                )
                ORDER BY m.created_at DESC
                """,
                            (user_id, user_id, user_id, user_id, user_id, user_id)
            )
        else:
            cursor.execute(
                """
                SELECT m.id, m.remitente_id, m.evento_id, m.asunto, m.mensaje, m.created_at, m.leido,
                       u.username AS remitente_nombre, u.foto_perfil AS remitente_foto, e.titulo AS evento_titulo
                FROM mensajes_organizador m
                LEFT JOIN `user` u ON u.id = m.remitente_id
                LEFT JOIN event e ON e.id = m.evento_id
                WHERE m.remitente_id = %s

                UNION ALL

                SELECT m.id, m.remitente_id, m.evento_id, m.asunto, m.mensaje, m.created_at, m.leido,
                       'Sistema' AS remitente_nombre, NULL AS remitente_foto, e.titulo AS evento_titulo
                FROM mensajes_organizador m
                LEFT JOIN event e ON e.id = m.evento_id
                WHERE m.organizador_id = %s AND m.remitente_id IS NULL
                ORDER BY created_at DESC
                """,
                (user_id, user_id)
            )
        notificaciones = cursor.fetchall()
        
        if es_organizador:
            cursor.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM mensajes_organizador
                     WHERE organizador_id = %s AND leido = 0)
                    +
                    (SELECT COUNT(*) FROM respuestas_organizador
                     WHERE destinatario_id = %s AND leido_destinatario = 0)
                """,
                (user_id, user_id)
            )
        else:
            cursor.execute(
                """
                SELECT 
                    (SELECT COUNT(*) FROM respuestas_organizador WHERE destinatario_id = %s AND leido_destinatario = 0)
                    +
                    (SELECT COUNT(*) FROM mensajes_organizador WHERE organizador_id = %s AND remitente_id IS NULL AND leido = 0)
                """,
                (user_id, user_id)
            )
        no_leidas_count = cursor.fetchone()[0]
        
        notifs = []
        for n in notificaciones:
            mensaje_id = n[0]
            replies = get_message_replies(mensaje_id)
            created_dt = n[5]
            remitente_id = n[1]
            es_mensaje_propio = es_organizador and remitente_id == user_id
            nombre_contacto = n[7] or 'Usuario anónimo'
            foto_contacto = n[8]
            remitente_nombre = 'Vos' if es_mensaje_propio else nombre_contacto
            if remitente_id is None or remitente_nombre in ('Usuario anónimo', 'Anónimo', 'Usuario anonimo'):
                remitente_nombre = 'Sistema'
                remitente_foto = None
            else:
                remitente_foto = None if es_mensaje_propio else foto_contacto

            notif = {
                'id': mensaje_id,
                'remitente_id': remitente_id,
                'evento_id': n[2],
                'asunto': n[3],
                'mensaje': n[4],
                'created_at': created_dt.strftime('%d/%m/%Y %H:%M') if hasattr(created_dt, 'strftime') else str(created_dt),
                'created_sort': created_dt if hasattr(created_dt, 'timestamp') else datetime.now(),
                'leido': bool(n[6]),
                'remitente_nombre': remitente_nombre,
                'remitente_foto': remitente_foto,
                'es_propio': es_mensaje_propio,
                'chat_nombre': nombre_contacto,
                'chat_foto': foto_contacto,
                'evento_titulo': n[9] or f'Evento {n[2]}',
                'respuestas': replies
            }
            notifs.append(notif)

        notifs.sort(key=lambda x: (x['remitente_nombre'] != 'Sistema', -x['created_sort'].timestamp()))

        chats = []
        if es_organizador:
            chats_by_user = {}
            for notif in notifs:
                cursor.execute(
                    "SELECT organizador_id, remitente_id FROM mensajes_organizador WHERE id = %s",
                    (notif['id'],)
                )
                participantes = cursor.fetchone()
                chat_key = (
                    participantes[0] if participantes and participantes[1] == user_id
                    else notif['remitente_id']
                ) if notif['remitente_id'] is not None else 'sistema'
                if chat_key not in chats_by_user:
                    chats_by_user[chat_key] = {
                        'usuario_id': chat_key if chat_key != 'sistema' else None,
                        'nombre': notif['chat_nombre'] if notif['es_propio'] else notif['remitente_nombre'],
                        'foto': notif['chat_foto'] if notif['es_propio'] else notif['remitente_foto'],
                        'mensajes': []
                    }
                    chats.append(chats_by_user[chat_key])
                chats_by_user[chat_key]['mensajes'].append(notif)
        
        return render_template(
            'notificaciones.html',
            notificaciones=notifs,
            chats=chats,
            no_leidas_count=no_leidas_count,
            es_organizador=es_organizador
        )
    except Exception as ex:
        print(f"[ERROR] mis_notificaciones: {ex}")
        flash('Ocurrió un error al cargar las notificaciones.', 'error')
        return redirect(url_for('home'))

@app.route('/notificacion/<int:notif_id>/marcar-leida', methods=['POST'])
@login_required
def marcar_notificacion_leida(notif_id):
    """Marca una notificación como leída"""
    try:
        cursor = db.connection.cursor()
        cursor.execute(
            "UPDATE mensajes_organizador SET leido = 1 WHERE id = %s AND organizador_id = %s",
            (notif_id, getattr(current_user, 'id', None))
        )
        db.connection.commit()
    except Exception as ex:
        print(f"[ERROR] marcar_notificacion_leida: {ex}")
    
    return redirect(url_for('mis_notificaciones'))

@app.route('/notificacion/<int:notif_id>/eliminar', methods=['POST'])
@login_required
def eliminar_notificacion_sistema(notif_id):
    """Elimina solo una notificacion automatica del usuario actual."""
    try:
        cursor = db.connection.cursor()
        cursor.execute(
            """
            DELETE FROM respuestas_organizador
            WHERE mensaje_id = %s
            """,
            (notif_id,)
        )
        cursor.execute(
            """
            DELETE FROM mensajes_organizador
            WHERE id = %s
              AND organizador_id = %s
              AND remitente_id IS NULL
            """,
            (notif_id, getattr(current_user, 'id', None))
        )
        if cursor.rowcount == 0:
            db.connection.rollback()
            flash('No se encontro esa notificacion.', 'error')
        else:
            db.connection.commit()
            flash('Notificacion eliminada.', 'success')
    except Exception as ex:
        db.connection.rollback()
        print(f"[ERROR] eliminar_notificacion_sistema: {ex}")
        flash('No se pudo eliminar la notificacion.', 'error')
    return redirect(url_for('mis_notificaciones'))


@app.route('/notificaciones/cambios-evento/marcar-todas-leidas', methods=['POST'])
@login_required
def marcar_todos_los_cambios_evento_leidos():
    """Marca como leídos todos los cambios de eventos del usuario actual."""
    try:
        cursor = db.connection.cursor()
        cursor.execute(
            """
            UPDATE mensajes_organizador
            SET leido = 1
            WHERE organizador_id = %s
              AND remitente_id IS NULL
              AND asunto = 'Cambio de evento'
              AND leido = 0
            """,
            (current_user.id,)
        )
        db.connection.commit()
    except Exception as ex:
        db.connection.rollback()
        print(f"[ERROR] marcar_todos_los_cambios_evento_leidos: {ex}")
    return redirect(url_for('home'))


@app.route('/chat/<int:usuario_id>/eliminar', methods=['POST'])
@login_required
def eliminar_chat(usuario_id):
    """Oculta el chat solo para el organizador que lo elimina."""
    if getattr(current_user, 'rol', '') not in ('admin', 'organizador'):
        flash('No tienes permiso para eliminar chats.', 'error')
        return redirect(url_for('home'))

    try:
        cursor = db.connection.cursor()
        cursor.execute(
            """
            SELECT id
            FROM mensajes_organizador
            WHERE (organizador_id = %s AND remitente_id = %s)
               OR (organizador_id = %s AND remitente_id = %s)
            LIMIT 1
            """,
            (current_user.id, usuario_id, usuario_id, current_user.id)
        )
        if cursor.fetchone() is None:
            flash('No se encontró ese chat.', 'error')
            return redirect(url_for('mis_notificaciones'))

        cursor.execute(
            """
            INSERT INTO chats_eliminados (usuario_id, contacto_id, eliminado_at)
            VALUES (%s, %s, NOW())
            ON DUPLICATE KEY UPDATE eliminado_at = NOW()
            """,
            (current_user.id, usuario_id)
        )
        db.connection.commit()
        flash('Chat eliminado para vos. El receptor conserva la conversación.', 'success')
    except Exception as ex:
        db.connection.rollback()
        print(f"[ERROR] eliminar_chat: {ex}")
        flash('No se pudo eliminar el chat.', 'error')
    return redirect(url_for('mis_notificaciones'))

@app.route('/notificaciones/sistema/eliminar', methods=['POST'])
@login_required
def eliminar_notificaciones_sistema():
    """Elimina las notificaciones automáticas del sistema del usuario actual."""
    if getattr(current_user, 'rol', '') not in ('admin', 'organizador'):
        flash('No tienes permiso para eliminar este chat.', 'error')
        return redirect(url_for('home'))

    try:
        cursor = db.connection.cursor()
        cursor.execute(
            "DELETE FROM mensajes_organizador WHERE organizador_id = %s AND remitente_id IS NULL",
            (current_user.id,)
        )
        cursor.execute(
            "DELETE FROM recordatorios_eventos WHERE usuario_id = %s",
            (current_user.id,)
        )
        db.connection.commit()
        flash('Chat del sistema eliminado.', 'success')
    except Exception as ex:
        db.connection.rollback()
        print(f"[ERROR] eliminar_notificaciones_sistema: {ex}")
        flash('No se pudo eliminar el chat del sistema.', 'error')
    return redirect(url_for('mis_notificaciones'))

@app.route('/chat/<int:usuario_id>/marcar-leido', methods=['POST'])
@login_required
def marcar_chat_leido(usuario_id):
    """Marca como leídos todos los mensajes y respuestas de un chat."""
    if getattr(current_user, 'rol', '') not in ('admin', 'organizador'):
        flash('No tienes permiso para marcar este chat.', 'error')
        return redirect(url_for('home'))

    try:
        cursor = db.connection.cursor()
        cursor.execute(
            "UPDATE mensajes_organizador SET leido = 1 WHERE organizador_id = %s AND remitente_id = %s",
            (current_user.id, usuario_id)
        )
        cursor.execute(
            """
            UPDATE respuestas_organizador
            SET leido_destinatario = 1
            WHERE destinatario_id = %s
              AND mensaje_id IN (
                SELECT id FROM mensajes_organizador
                WHERE organizador_id = %s AND remitente_id = %s
              )
            """,
            (current_user.id, current_user.id, usuario_id)
        )
        db.connection.commit()
    except Exception as ex:
        db.connection.rollback()
        print(f"[ERROR] marcar_chat_leido: {ex}")
        flash('No se pudo marcar el chat como leído.', 'error')
    return redirect(url_for('mis_notificaciones', chat=usuario_id))

@app.route('/respuesta/<int:respuesta_id>/marcar-leida', methods=['POST'])
@login_required
def marcar_respuesta_leida(respuesta_id):
    """Marca como leída una respuesta dirigida al usuario actual."""
    try:
        cursor = db.connection.cursor()
        cursor.execute(
            """
            UPDATE respuestas_organizador
            SET leido_destinatario = 1
            WHERE id = %s AND destinatario_id = %s
            """,
            (respuesta_id, current_user.id)
        )
        db.connection.commit()
    except Exception as ex:
        print(f"[ERROR] marcar_respuesta_leida: {ex}")
        db.connection.rollback()
    return redirect(url_for('mis_notificaciones'))

@app.route('/notificacion/<int:mensaje_id>/responder', methods=['POST'])
@login_required
def responder_mensaje(mensaje_id):
    """El organizador responde a un mensaje"""
    if getattr(current_user, 'rol', '') not in ('admin', 'organizador'):
        flash('No tienes permiso para responder.', 'error')
        return redirect(url_for('home'))
    
    respuesta = request.form.get('respuesta', '').strip()
    if not respuesta:
        flash('La respuesta no puede estar vacía.', 'error')
        return redirect(url_for('mis_notificaciones'))
    
    chat_user_id = None
    try:
        cursor = db.connection.cursor()
        # Verificar que el mensaje pertenece al organizador actual
        cursor.execute(
            "SELECT id, remitente_id FROM mensajes_organizador WHERE id = %s AND organizador_id = %s",
            (mensaje_id, current_user.id)
        )
        mensaje = cursor.fetchone()
        if not mensaje:
            flash('No tienes permiso para responder este mensaje.', 'error')
            return redirect(url_for('mis_notificaciones'))
        chat_user_id = mensaje[1]
        
        # Guardar respuesta
        cursor.execute(
            """
            INSERT INTO respuestas_organizador
            (mensaje_id, organizador_id, destinatario_id, autor_id, respuesta, leido_destinatario)
            VALUES (%s, %s, %s, %s, %s, 0)
            """,
            (mensaje_id, current_user.id, mensaje[1], current_user.id, respuesta)
        )
        cursor.execute(
            "UPDATE mensajes_organizador SET leido = 1 WHERE id = %s AND organizador_id = %s",
            (mensaje_id, current_user.id)
        )
        cursor.execute(
            """
            UPDATE respuestas_organizador
            SET leido_destinatario = 1
            WHERE destinatario_id = %s AND mensaje_id = %s
            """,
            (current_user.id, mensaje_id)
        )
        db.connection.commit()
        flash('✓ Respuesta enviada correctamente.', 'success')
    except Exception as ex:
        print(f"[ERROR] responder_mensaje: {ex}")
        flash('Ocurrió un error al enviar la respuesta.', 'error')
        db.connection.rollback()
    
    return redirect(url_for('mis_notificaciones', chat=chat_user_id))

@app.route('/notificacion/<int:mensaje_id>/responder-usuario', methods=['POST'])
@login_required
def responder_usuario(mensaje_id):
    """Agrega un mensaje del estudiante al mismo hilo de conversación."""
    respuesta = request.form.get('respuesta', '').strip()
    if not respuesta:
        flash('El mensaje no puede estar vacío.', 'error')
        return redirect(url_for('mis_notificaciones'))

    chat_user_id = None
    try:
        cursor = db.connection.cursor()
        cursor.execute(
            """
            SELECT organizador_id FROM mensajes_organizador
            WHERE id = %s AND remitente_id = %s
            """,
            (mensaje_id, current_user.id)
        )
        mensaje = cursor.fetchone()
        if not mensaje:
            flash('No tienes permiso para responder este mensaje.', 'error')
            return redirect(url_for('mis_notificaciones'))
        chat_user_id = current_user.id

        cursor.execute(
            """
            INSERT INTO respuestas_organizador
            (mensaje_id, organizador_id, destinatario_id, autor_id, respuesta, leido_destinatario)
            VALUES (%s, %s, %s, %s, %s, 0)
            """,
            (mensaje_id, mensaje[0], mensaje[0], current_user.id, respuesta)
        )
        cursor.execute(
            """
            UPDATE respuestas_organizador
            SET leido_destinatario = 1
            WHERE mensaje_id = %s AND destinatario_id = %s AND autor_id <> %s
            """,
            (mensaje_id, current_user.id, current_user.id)
        )
        db.connection.commit()
        flash('Mensaje enviado correctamente.', 'success')
    except Exception as ex:
        print(f"[ERROR] responder_usuario: {ex}")
        db.connection.rollback()
        flash('Ocurrió un error al enviar el mensaje.', 'error')
    return redirect(url_for('mis_notificaciones', chat=chat_user_id))

def get_unread_notifications_count(user_id):
    """Obtiene mensajes y respuestas nuevas dirigidas al organizador."""
    try:
        cursor = db.connection.cursor()
        cursor.execute(
            """
            SELECT (
                (SELECT COUNT(*) FROM mensajes_organizador WHERE organizador_id = %s AND leido = 0)
                +
                (SELECT COUNT(*) FROM respuestas_organizador WHERE destinatario_id = %s AND leido_destinatario = 0)
            )
            """,
            (user_id, user_id)
        )
        count = cursor.fetchone()[0]
        return count
    except Exception:
        return 0

def get_unread_responses_count(user_id):
    """Obtiene respuestas y recordatorios del sistema dirigidos al usuario."""
    try:
        cursor = db.connection.cursor()
        cursor.execute(
            """
            SELECT 
                (SELECT COUNT(*) FROM respuestas_organizador WHERE destinatario_id = %s AND leido_destinatario = 0)
                +
                (SELECT COUNT(*) FROM mensajes_organizador WHERE organizador_id = %s AND remitente_id IS NULL AND leido = 0)
            """,
            (user_id, user_id)
        )
        return cursor.fetchone()[0]
    except Exception:
        return 0

@app.route('/perfil')
@login_required
def perfil_usuario():
    """Muestra el perfil del usuario con opción de subir foto"""
    try:
        cursor = db.connection.cursor()
        user_id = getattr(current_user, 'id', None)
        
        cursor.execute(
            "SELECT id, username, email, dni, telefono, foto_perfil FROM `user` WHERE id = %s LIMIT 1",
            (user_id,)
        )
        user_data = cursor.fetchone()
        
        if not user_data:
            flash('No se encontraron los datos de tu perfil.', 'error')
            return redirect(url_for('home'))
        
        usuario = {
            'id': user_data[0],
            'username': user_data[1],
            'email': user_data[2],
            'dni': user_data[3],
            'telefono': user_data[4],
            'foto_perfil': user_data[5]
        }
        
        return render_template('perfil.html', usuario=usuario)
    except Exception as ex:
        print(f"[ERROR] perfil_usuario: {ex}")
        flash('Ocurrió un error al cargar tu perfil.', 'error')
        return redirect(url_for('home'))

@app.route('/perfil/actualizar', methods=['POST'])
@login_required
def actualizar_perfil():
    """Actualiza el nombre y, opcionalmente, la foto del usuario."""
    nombre = request.form.get('username')

    foto = request.files.get('foto')
    foto_path = None
    if foto and foto.filename:
        allowed_extensions = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
        extension = foto.filename.rsplit('.', 1)[-1].lower() if '.' in foto.filename else ''
        if extension not in allowed_extensions:
            flash('Formato de imagen no permitido. Usa JPG, PNG, GIF o WEBP.', 'error')
            return redirect(url_for('home'))

        filename = f'perfil_{current_user.id}_{uuid.uuid4().hex}.{extension}'
        profile_photos_dir = os.path.join(app.static_folder, 'perfil')
        os.makedirs(profile_photos_dir, exist_ok=True)
        foto.save(os.path.join(profile_photos_dir, filename))
        foto_path = f'perfil/{filename}'

    try:
        cursor = db.connection.cursor()
        if foto_path and nombre:
            cursor.execute(
                "UPDATE `user` SET username = %s, foto_perfil = %s WHERE id = %s",
                (nombre.strip(), foto_path, current_user.id)
            )
        elif foto_path:
            cursor.execute(
                "UPDATE `user` SET foto_perfil = %s WHERE id = %s",
                (foto_path, current_user.id)
            )
        else:
            flash('Selecciona una foto para actualizar tu perfil.', 'error')
            return redirect(url_for('home'))
        db.connection.commit()
        flash('Perfil actualizado correctamente.', 'success')
    except Exception as ex:
        db.connection.rollback()
        print(f"[ERROR] actualizar_perfil: {ex}")
        flash('No se pudo actualizar el perfil.', 'error')

    return redirect(url_for('home'))

@app.route('/perfil/subir-foto', methods=['POST'])
@login_required
def subir_foto_perfil():
    """Sube la foto de perfil del usuario"""
    try:
        if 'foto' not in request.files:
            flash('No se seleccionó ningún archivo.', 'error')
            return redirect(request.referrer or url_for('home'))
        
        file = request.files['foto']
        if file.filename == '':
            flash('No se seleccionó ningún archivo.', 'error')
            return redirect(request.referrer or url_for('home'))
        
        # Validar extensión
        allowed_extensions = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
        if not ('.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in allowed_extensions):
            flash('Formato de imagen no permitido. Usa JPG, PNG, GIF o WEBP.', 'error')
            return redirect(request.referrer or url_for('home'))
        
        # Guardar imagen
        extension = file.filename.rsplit('.', 1)[1].lower()
        filename = f'perfil_{current_user.id}_{uuid.uuid4().hex}.{extension}'
        PROFILE_PHOTOS_DIR = os.path.join(app.static_folder, 'perfil')
        os.makedirs(PROFILE_PHOTOS_DIR, exist_ok=True)
        file.save(os.path.join(PROFILE_PHOTOS_DIR, filename))
        
        # Actualizar BD con ruta de foto
        cursor = db.connection.cursor()
        cursor.execute(
            "UPDATE `user` SET foto_perfil = %s WHERE id = %s",
            (f'perfil/{filename}', current_user.id)
        )
        db.connection.commit()
        
        flash('✓ Foto de perfil actualizada correctamente.', 'success')
    except Exception as ex:
        print(f"[ERROR] subir_foto_perfil: {ex}")
        flash('Error al subir la foto de perfil.', 'error')
    
    return redirect(request.referrer or url_for('home'))

@app.route('/api/procesar-recordatorios', methods=['GET', 'POST'])
def procesar_recordatorios():
    """Procesa los recordatorios pendientes de envío.
    Esta ruta puede ser llamada por un script externo o un scheduler.
    Sin requerimiento de login para facilitar llamadas automáticas.
    """
    try:
        # Verificar si hay un token de autorización (opcional, para mayor seguridad)
        auth_token = request.args.get('token') or request.form.get('token')
        # Puedes agregar validación de token aquí si lo deseas
        
        cantidad_procesados = process_pending_event_reminders()
        
        return jsonify({
            'success': True,
            'message': f'Se procesaron {cantidad_procesados} recordatorios pendientes',
            'records_processed': cantidad_procesados
        })
    except Exception as ex:
        print(f"[ERROR] procesar_recordatorios: {ex}")
        return jsonify({
            'success': False,
            'message': str(ex)
        }), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)


